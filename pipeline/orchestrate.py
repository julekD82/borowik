from datetime import date

import geopandas as gpd
import pandas as pd

from pipeline.habitat import compute_habitat, passes_mask, score_site
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting,
    apply_moisture_modulation, compute_ranking,
)
from pipeline.weather import (
    make_grid, compute_weather_features, climatology_window_values, percentile_rank,
)


def _nearest_weather_row(centroid, weather_feat_gdf):
    idx = weather_feat_gdf.geometry.distance(centroid).idxmin()
    return weather_feat_gdf.loc[idx]


def run_poc(layer: str, bbox_2180: tuple, profile: dict,
             bdl_fetcher, weather_fetcher, climatology_fetcher,
             grid_spacing_m: float = 5000.0, past_days: int = 92) -> gpd.GeoDataFrame:
    stands = bdl_fetcher(layer, bbox_2180)
    stands["stand_id"] = stands["adr_for"] + "@" + stands["a_year"].astype(str)

    grid_points = make_grid(bbox_2180, spacing_m=grid_spacing_m)
    weather_daily = weather_fetcher(grid_points, past_days)
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

    clim_df = climatology_fetcher(grid_points, 1991, 2020)
    today_doy = date.today().timetuple().tm_yday

    h_values, f_values, f_loc_values, mask_values, r_values = [], [], [], [], []
    for _, row in stands.iterrows():
        mask = passes_mask(row, profile)
        h = compute_habitat(row, profile)
        _s_site, moisture_cls = score_site(row["site_type"], profile)

        centroid = row.geometry.centroid
        wrow = _nearest_weather_row(centroid, weather_feat_gdf)

        cwb26_hist = climatology_window_values(clim_df, wrow["lat"], wrow["lon"], today_doy, "cwb26")
        sm_hist = climatology_window_values(clim_df, wrow["lat"], wrow["lon"], today_doy, "soil_moisture")
        pct_cwb26 = percentile_rank(wrow["cwb26"], cwb26_hist)
        pct_sm = percentile_rank(wrow["soil_moisture"], sm_hist)

        m = score_moisture(pct_cwb26, pct_sm, profile)
        t = score_temperature(wrow["tmean20"], wrow["tmean5"], wrow["p1"], profile)
        k_frost = score_frost(wrow["tmin3"], profile)
        f = compute_fruiting(m, t, k_frost, g_season=1.0)
        pct_m = (pct_cwb26 + pct_sm) / 2.0
        f_loc = apply_moisture_modulation(f, moisture_cls, pct_m, profile)
        r = compute_ranking(mask, h, f_loc)

        mask_values.append(mask)
        h_values.append(h)
        f_values.append(f)
        f_loc_values.append(f_loc)
        r_values.append(r)

    stands["mask"] = mask_values
    stands["H"] = h_values
    stands["F"] = f_values
    stands["F_loc"] = f_loc_values
    stands["R"] = r_values
    return stands
