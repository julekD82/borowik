"""Poprawka 4: F panelu warunkow dla dnia dzisiejszego (agregacja median_f_stands) ma zgadzac sie
z mediana F wydzielen w masce z mapy -- panel liczy opad tak jak wydzielenia (radar scalony z modelem
per wydzielenie, zagregowany do punktow), a percentyl wzgledem historii swojej komorki klimatologii."""
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.conditions_timeline import build_conditions_timeline
from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc, _nearest_climatology_cell
from pipeline.prepare_trip import (
    apply_point_precip, conditions_point_weights, stand_precip_to_points, truncate_trailing_days,
)
from pipeline.weather import make_grid

PROFILE = load_profile("profiles/boletus_edulis.yaml")
BBOX = (486000.0, 380000.0, 506000.0, 400000.0)
TODAY = date.today()
N_STANDS = 80


def _stands():
    rng = np.random.default_rng(3)
    xs, ys = rng.uniform(486500, 505500, N_STANDS), rng.uniform(380500, 399500, N_STANDS)
    return gpd.GeoDataFrame({
        "adr_for": [f"S-{i}" for i in range(N_STANDS)], "a_year": [2026] * N_STANDS,
        "area_type": ["D-STAN"] * N_STANDS,
        "site_type": rng.choice(["BMSW", "LMW", "BS", "LSW"], N_STANDS),
        "species_cd": rng.choice(["SO", "BK", "DB"], N_STANDS), "part_cd": [10] * N_STANDS,
        "spec_age": rng.integers(30, 100, N_STANDS),
        "geometry": [box(y, x, y + rng.uniform(80, 400), x + rng.uniform(80, 400)) for x, y in zip(xs, ys)],
    }, crs="EPSG:2180")


def _weather_full(points, days=60, ahead=6):
    dates = pd.date_range(end=pd.Timestamp(TODAY) + pd.Timedelta(days=ahead), periods=days + ahead, freq="D", tz="UTC")
    rows = []
    for pi, (lat, lon) in enumerate(points):
        for i, d in enumerate(dates):
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": float((i * 5 + pi) % 9) * 0.8,
                         "tmean_c": 11.0 + 0.05 * pi + 0.02 * i, "tmin_c": 5.0 + 0.1 * pi,
                         "tmax_c": 16.0, "et0_mm": 1.5 + 0.01 * i, "soil_moisture": 0.3})
    return pd.DataFrame(rows)


def _clim(points, *_):
    rng = np.random.default_rng(11)
    rows = []
    for k, (lat, lon) in enumerate(points):
        for d in pd.date_range("2000-01-01", periods=500, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": float(rng.normal(-5 + 6 * k, 14)), "soil_moisture": 0.3})
    return pd.DataFrame(rows)


def test_panel_today_matches_the_median_of_the_map_within_tolerance():
    stands = _stands()
    stands["stand_id"] = stands["adr_for"] + "@" + stands["a_year"].astype(str)
    grid = make_grid(BBOX, spacing_m=5000.0)
    clim_pts = make_grid(BBOX, spacing_m=20000.0)
    full = _weather_full(grid)

    # opad wydzielen: model punktu + per-wydzielenie odchylenie (jak radar 1 km), do dnia dzisiejszego
    from pipeline.prepare_trip import nearest_weather_point_per_stand
    nearest = nearest_weather_point_per_stand(stands, grid)
    rng = np.random.default_rng(5)
    rows = []
    for sid in stands["stand_id"]:
        lat, lon = nearest[sid]
        base = full[(full["lat"] == lat) & (full["lon"] == lon)][["date", "precipitation_mm"]].copy()
        base["precipitation_mm"] = base["precipitation_mm"] * rng.uniform(0.5, 1.5) + rng.uniform(0, 1.5)
        base["stand_id"] = sid
        base["radar_frac"] = 1.0
        rows.append(base)
    stand_precip_full = pd.concat(rows, ignore_index=True)
    stand_precip = truncate_trailing_days(stand_precip_full, 6)

    scored = run_poc(
        layer="X", bbox_2180=BBOX, profile=PROFILE, bdl_fetcher=lambda *_: stands.copy(),
        weather_fetcher=lambda pts, past_days, forecast_days=1: full[
            (full["date"] <= pd.Timestamp(TODAY, tz="UTC")) & full["lat"].isin([p[0] for p in pts])],
        climatology_fetcher=_clim, grid_spacing_m=5000.0, climatology_grid_spacing_m=20000.0,
        past_days=60, target_date=TODAY, stand_precip_daily=stand_precip)
    map_median = float(scored.loc[scored["mask"], "F"].median())

    daily = apply_point_precip(full, stand_precip_to_points(stand_precip_full, scored))
    clim_df = _clim(clim_pts)
    cells = _nearest_climatology_cell(grid, clim_pts, "EPSG:2180")
    prof = {**PROFILE, "conditions": {**PROFILE["conditions"], "aggregation": "median_f_stands"}}
    tl = build_conditions_timeline(daily, grid, clim_df, clim_pts, TODAY, prof,
                                   point_weights=conditions_point_weights(scored), point_clim_cells=cells)
    # bez poprawki (opad samego modelu, pula komorek klimatologii) panel rozjezdza sie z mapa
    old = build_conditions_timeline(full, grid, clim_df, clim_pts, TODAY, prof, point_weights=conditions_point_weights(scored))
    assert abs(old["days"][0]["F"] - map_median) > 0.02
    assert tl["days"][0]["F"] == pytest.approx(map_median, abs=0.02)
    assert tl["days"][0]["F"] == tl["days"][0]["F_by_aggregation"]["median_f_stands"]
