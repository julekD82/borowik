import math
from datetime import date

import geopandas as gpd
import pandas as pd

from pipeline.habitat import (
    compute_habitat, passes_mask, score_site, score_host, score_age, score_host_composition,
)
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting,
    apply_moisture_modulation, compute_ranking, moisture_percentile, moisture_multiplier,
)
from pipeline.weather import (
    make_grid, compute_weather_features, climatology_window_values, percentile_rank,
)
from pipeline.phenology import compute_g_season

# Default weather grid spacing, and the climatology grid's own (see run_poc /
# _nearest_climatology_cell for why climatology is coarser). Both are defined
# at the CLI's default 25km search radius (pipeline/prepare_trip.py's
# REFERENCE_RADIUS_KM) -- prepare_trip.py scales both proportionally to the
# actual radius requested, so total point count (and so API cost) stays
# roughly constant across the whole 10-50km range instead of growing with
# the search area. Exposed as module constants so callers that print
# progress or scale spacing (pipeline/prepare_trip.py) share one number.
WEATHER_GRID_SPACING_M = 5000.0
CLIMATOLOGY_GRID_SPACING_M = 20000.0


def _nearest_weather_row(centroid, weather_feat_gdf):
    idx = weather_feat_gdf.geometry.distance(centroid).idxmin()
    return weather_feat_gdf.loc[idx]


def _points_gdf(points: list[tuple[float, float]], crs) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"lat": [p[0] for p in points], "lon": [p[1] for p in points]},
        geometry=gpd.points_from_xy([p[1] for p in points], [p[0] for p in points]),
        crs="EPSG:4326",
    ).to_crs(crs)


def _nearest_climatology_cell(grid_points, climatology_grid_points, crs) -> dict:
    """Map each weather grid point (lat, lon) to its nearest climatology
    grid point (lat, lon). Climatology's 30-year archive is far more
    expensive per point than a live weather call (Open-Meteo's own
    weighting formula scales with days-range/14 x variables/10, so a
    30-year pull already weighs ~235 "calls" per point -- see
    docs/CODEX-HANDOFF.md for the derivation) but varies smoothly over a
    few km, so it's fetched on a coarser grid than weather and several
    weather cells share one climatology cell."""
    weather_gdf = _points_gdf(grid_points, crs)
    clim_gdf = _points_gdf(climatology_grid_points, crs)
    joined = gpd.sjoin_nearest(weather_gdf, clim_gdf, lsuffix="w", rsuffix="c")
    return {
        (row["lat_w"], row["lon_w"]): (row["lat_c"], row["lon_c"])
        for _, row in joined.iterrows()
    }


def run_poc(layer: str, bbox_2180: tuple, profile: dict,
             bdl_fetcher, weather_fetcher, climatology_fetcher,
             grid_spacing_m: float = WEATHER_GRID_SPACING_M, past_days: int = 92,
             climatology_grid_spacing_m: float = CLIMATOLOGY_GRID_SPACING_M,
             target_date: date | None = None, package_index: dict | None = None) -> gpd.GeoDataFrame:
    """Score every wydzielenie in the tile and return the stands GeoDataFrame
    with mask/H/F/F_loc/R columns added.

    Diagnostic counts for the silent-fallback paths (codes missing from the
    profile, empty climatology windows, non-finite H) are attached to the
    returned frame as `.attrs["diagnostics"]` rather than added to the
    signature, so callers that only want the scores are unaffected. The
    unknown-code counts are restricted to mask-passing stands, since the tile
    also holds non-stand polygons with no site_type/species_cd at all.

    `target_date` (plan 2.1 step A3, spec §3.3/§5.4): defaults to today,
    unchanged pre-A3 behaviour. When it's in the future, weather windows are
    fetched through that date (forecast_days below) -- pipeline.weather.
    compute_weather_features's windows already end on the last fetched row,
    so no separate "end date" logic is needed once forecast_days is right
    -- and climatology percentiles are looked up for target_date's day of
    year, not today's (validated against a real forecast API request 2026-
    09-24, see pipeline.weather._default_open_meteo_call's docstring; CLI
    validation of target_date itself -- past dates, >16 days ahead -- lives
    in pipeline.prepare_trip.parse_args, not here).

    `package_index` (plan 2.1 step B2): optional `adr_for ->
    pipeline.bdl_packages.PackageComposition` map (pipeline.bdl_packages.
    load_packages). A stand whose `adr_for` is present gets S_host from its
    real DRZEW-storey species composition instead of the WFS
    panujący+part_cd fallback -- `None` (the default) or a miss for this
    particular stand reproduces the exact pre-B2 behaviour."""
    target_date = target_date or date.today()
    # Open-Meteo's forecast_days counts today as day 1, so N days ahead
    # needs forecast_days = N+1. max(1, ...) is a defensive floor for a
    # direct caller (tests, notebooks) passing a past target_date without
    # going through prepare_trip's CLI validation -- not a silent fallback
    # for the CLI's own user-facing --date, which is rejected before it
    # ever reaches here.
    forecast_days = max(1, (target_date - date.today()).days + 1)

    stands = bdl_fetcher(layer, bbox_2180)
    stands["stand_id"] = stands["adr_for"] + "@" + stands["a_year"].astype(str)

    grid_points = make_grid(bbox_2180, spacing_m=grid_spacing_m)
    weather_daily = weather_fetcher(grid_points, past_days, forecast_days=forecast_days)
    weather_feat = compute_weather_features(weather_daily)
    # compute_weather_features (Task 6) doesn't carry today's soil_moisture
    # through to its output row (it's a windowed-features table, not a daily
    # snapshot) — pull the latest day's soil_moisture per point straight from
    # the raw daily fetch and merge it in, so pct_sm below compares a real
    # reading against climatology instead of a hardcoded placeholder.
    latest_sm = (
        weather_daily.sort_values("date")
        .groupby(["lat", "lon"], as_index=False)
        .last()[["lat", "lon", "soil_moisture"]]
    )
    weather_feat = weather_feat.merge(latest_sm, on=["lat", "lon"], how="left")
    weather_feat_gdf = gpd.GeoDataFrame(
        weather_feat,
        geometry=gpd.points_from_xy(weather_feat["lon"], weather_feat["lat"]),
        crs="EPSG:4326",
    ).to_crs(stands.crs)

    climatology_grid_points = make_grid(bbox_2180, spacing_m=climatology_grid_spacing_m)
    clim_df = climatology_fetcher(climatology_grid_points, 1991, 2020)
    weather_to_clim_cell = _nearest_climatology_cell(grid_points, climatology_grid_points, stands.crs)
    # Percentiles are for the TRIP date's day of year, not today's --
    # otherwise a forecast fetched for next week would still be compared
    # against this week's climatology window (plan 2.1 step A3).
    target_doy = target_date.timetuple().tm_yday
    # Plan 2.1 "Zmiana 1": one G_season value per run (it depends only on
    # target_date, not on any per-stand attribute), reused for every stand
    # below -- same "compute once, same value for every stand" shape as
    # forecast_days.
    g_season = compute_g_season(target_doy, profile)
    # Many stands share a weather cell, and many weather cells share a
    # (coarser) climatology cell. Avoid rescanning the whole 30-year archive
    # for every stand when the search spans dozens of tiles: the climatology
    # window is cached per climatology cell, but the percentiles themselves
    # per WEATHER point -- each point ranks its own cwb26/soil_moisture
    # against its cell's history (caching percentiles per cell gave every
    # weather point in a 16 km cell the first point's M, found 2026-09-27).
    climate_cells = dict(tuple(clim_df.groupby(["lat", "lon"])))
    history_by_cell = {}
    percentiles_by_point = {}

    h_values, f_values, f_loc_values, mask_values, r_values = [], [], [], [], []
    s_host_values, s_site_values, s_age_values = [], [], []
    s_host_source_values, s_host_package_date_values = [], []
    sklad_niepelny_values = []
    m_values, t_values, k_frost_values = [], [], []
    rain_radar_coverage_values = []
    # Plan wdrozenia 1.2 (diagnostics export): percentile/multiplier
    # intermediates and the weather-point/climatology-cell identity each
    # stand was scored against, so scores.json's H/F/P/R aren't the only
    # auditable trail.
    pct_cwb26_values, pct_sm_values, pct_m_values, q_values = [], [], [], []
    weather_lat_values, weather_lon_values = [], []
    climatology_lat_values, climatology_lon_values = [], []
    # Cheap diagnostics for the three paths that otherwise degrade silently to
    # a plausible-looking number (see spec review: 59% of stands were hitting
    # the unknown-code fallback unnoticed).
    unknown_site_count = 0
    unknown_species_count = 0
    empty_climatology_count = 0
    nan_h_count = 0
    package_index = package_index or {}
    package_stand_count = 0
    package_unknown_species_count = 0
    incomplete_composition_count = 0
    for _, row in stands.iterrows():
        mask = passes_mask(row, profile)
        if mask:
            # Only mask-passing stands matter here: the BDL tile also contains
            # roads/meadows/clearings whose site_type and species_cd are NaN by
            # design, and those would drown out the real profile gaps.
            if row.get("site_type") not in profile["site_scores"]:
                unknown_site_count += 1
            if row.get("species_cd") not in profile["host_affinity"]:
                unknown_species_count += 1

        # plan 2.1 step B2: a real BDL package's full DRZEW composition
        # replaces the WFS panujący+part_cd fallback when this stand's
        # adr_for is covered by one.
        package = package_index.get(row.get("adr_for"))
        if package is not None:
            s_host, unk = score_host_composition(package.species, profile)
            s_host_source, s_host_package_date = "paczka", package.package_date
            package_stand_count += 1
            package_unknown_species_count += unk
            sklad_niepelny = package.sklad_niepelny
            if sklad_niepelny:
                incomplete_composition_count += 1
        else:
            s_host = score_host(row["species_cd"], row.get("part_cd", 10), profile)
            s_host_source, s_host_package_date = "wfs", None
            sklad_niepelny = False

        h = compute_habitat(row, profile, s_host=s_host)
        if h is not None and not math.isfinite(h):
            nan_h_count += 1
        _s_site, moisture_cls = score_site(row["site_type"], profile)
        s_age = score_age(row.get("spec_age"), profile)

        centroid = row.geometry.centroid
        wrow = _nearest_weather_row(centroid, weather_feat_gdf)
        rain_radar_coverage_values.append(float(wrow.get("rain_radar_coverage", 0.0)))

        point = (wrow["lat"], wrow["lon"])
        # Looked up unconditionally (not just on a percentiles_by_point cache
        # miss) -- plan 1.2's diagnostics export needs this stand's actual
        # climatology cell every time, not whichever cell the last cache-miss
        # iteration happened to leave in this loop-local variable.
        cell = weather_to_clim_cell[point]
        if point not in percentiles_by_point:
            if cell not in history_by_cell:
                history = climate_cells.get(cell, clim_df.iloc[:0])
                history_by_cell[cell] = (
                    climatology_window_values(history, *cell, target_doy, "cwb26"),
                    climatology_window_values(history, *cell, target_doy, "soil_moisture"),
                )
            cwb26_hist, sm_hist = history_by_cell[cell]
            percentiles_by_point[point] = (
                percentile_rank(wrow["cwb26"], cwb26_hist),
                percentile_rank(wrow["soil_moisture"], sm_hist),
                len(cwb26_hist) == 0 or len(sm_hist) == 0,
            )
        pct_cwb26, pct_sm, empty_window = percentiles_by_point[point]
        if empty_window:
            # percentile_rank falls back to a neutral 0.5 on an empty window.
            empty_climatology_count += 1

        m = score_moisture(pct_cwb26, pct_sm, profile)
        # heat_penalty_p5_mm means a 5-day precipitation sum (spec §4.3), not p1.
        t = score_temperature(wrow["tmean20"], wrow["tmean5"], wrow["p5"], profile)
        k_frost = score_frost(wrow["tmin3"], profile)
        f = compute_fruiting(m, t, k_frost, g_season=g_season)
        pct_m = moisture_percentile(pct_cwb26, pct_sm, profile)
        q = moisture_multiplier(pct_m, moisture_cls, profile)
        f_loc = apply_moisture_modulation(f, moisture_cls, pct_m, profile)
        r = compute_ranking(mask, h, f_loc)

        pct_cwb26_values.append(pct_cwb26)
        pct_sm_values.append(pct_sm)
        pct_m_values.append(pct_m)
        q_values.append(q)
        weather_lat_values.append(point[0])
        weather_lon_values.append(point[1])
        climatology_lat_values.append(cell[0])
        climatology_lon_values.append(cell[1])

        mask_values.append(mask)
        h_values.append(h)
        f_values.append(f)
        f_loc_values.append(f_loc)
        r_values.append(r)
        s_host_values.append(s_host)
        s_site_values.append(_s_site)
        s_age_values.append(s_age)
        s_host_source_values.append(s_host_source)
        s_host_package_date_values.append(s_host_package_date)
        sklad_niepelny_values.append(sklad_niepelny)
        m_values.append(m)
        t_values.append(t)
        k_frost_values.append(k_frost)

    stands["mask"] = mask_values
    stands["H"] = h_values
    stands["F"] = f_values
    stands["F_loc"] = f_loc_values
    stands["R"] = r_values
    stands["S_host"] = s_host_values
    stands["S_site"] = s_site_values
    stands["S_age"] = s_age_values
    stands["s_host_source"] = s_host_source_values
    stands["s_host_package_date"] = s_host_package_date_values
    stands["sklad_niepelny"] = sklad_niepelny_values
    stands["M"] = m_values
    stands["T"] = t_values
    stands["K_frost"] = k_frost_values
    stands["rain_radar_coverage"] = rain_radar_coverage_values
    stands["pct_CWB26"] = pct_cwb26_values
    stands["pct_SM"] = pct_sm_values
    stands["pct_m"] = pct_m_values
    stands["q"] = q_values
    stands["weather_point_lat"] = weather_lat_values
    stands["weather_point_lon"] = weather_lon_values
    stands["climatology_cell_lat"] = climatology_lat_values
    stands["climatology_cell_lon"] = climatology_lon_values
    # Same forecast_days for every stand in the run (one weather fetch, one
    # target_date) -- exported per stand anyway (spec §3.3: "Oznaczyć w UI,
    # ile dni okna pochodzi z prognozy"), matching how every other weather-
    # derived column already flows through to scores_{day}.json.
    stands["forecast_days"] = forecast_days
    stands["G_season"] = g_season
    stands.attrs["diagnostics"] = {
        "stand_count": len(stands),
        "mask_passing_count": int(sum(mask_values)),
        "unknown_site_count": unknown_site_count,
        "unknown_species_count": unknown_species_count,
        "empty_climatology_count": empty_climatology_count,
        "nan_h_count": nan_h_count,
        "forecast_days": forecast_days,
        "package_stand_count": package_stand_count,
        "package_unknown_species_count": package_unknown_species_count,
        "incomplete_composition_count": incomplete_composition_count,
        "g_season": g_season,
        "radar_coverage_mean": float(sum(rain_radar_coverage_values) / len(rain_radar_coverage_values)) if rain_radar_coverage_values else 0.0,
    }
    return stands
