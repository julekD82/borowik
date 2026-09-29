"""Faza 4.3/4.5: skladniki pogody i oznaczenia niepewnosci to WYLACZNIE prezentacja --
F, F_loc i R (run_poc) nie moga sie zmienic. Wartosci przypiete sa policzone na kodzie
sprzed Fazy 4 (commit c907883) na wejsciu ponizej; kazda zmiana wzoru F/R je zlamie."""
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc

PROFILE = load_profile("profiles/boletus_edulis.yaml")
BBOX = (486000.0, 380000.0, 496000.0, 390000.0)


def _bdl(layer, bbox):
    return gpd.GeoDataFrame({
        "adr_for": ["A-1", "A-2", "A-3"], "a_year": [2026] * 3,
        "area_type": ["D-STAN"] * 3, "site_type": ["BMSW", "LMW", "BS"],
        "species_cd": ["SO", "BK", "SO"], "part_cd": [10, 8, 10], "spec_age": [60, 80, 45],
        "geometry": [box(380100, 486100, 380200, 486200), box(380300, 486300, 380400, 486400),
                     box(384100, 490100, 384200, 490200)],
    }, crs="EPSG:2180")


def _weather(points, past_days, forecast_days=1):
    rows = []
    dates = pd.date_range("2026-08-01", periods=60, freq="D")
    for pi, (lat, lon) in enumerate(points):
        for i, d in enumerate(dates):
            rows.append({"lat": lat, "lon": lon, "date": d,
                         "precipitation_mm": float((i * 7 + pi * 3) % 11) * 0.9,
                         "tmean_c": 9.0 + 0.1 * i + 0.3 * pi, "tmin_c": 4.0 - 0.15 * i + 0.2 * pi + (-3 if i >= 58 else 0),
                         "tmax_c": 16.0, "et0_mm": 1.0 + 0.02 * i, "soil_moisture": 0.3})
    return pd.DataFrame(rows)


def _clim(points, start_year, end_year):
    rows = []
    rng = np.random.default_rng(7)
    for lat, lon in points:
        for d in pd.date_range("2000-01-01", periods=400, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": float(rng.normal(20, 15)), "soil_moisture": 0.3})
    return pd.DataFrame(rows)


def _run(profile=PROFILE, target=date(2026, 9, 29)):
    return run_poc(layer="X", bbox_2180=BBOX, profile=profile, bdl_fetcher=_bdl, weather_fetcher=_weather,
                   climatology_fetcher=_clim, grid_spacing_m=5000.0, past_days=60, target_date=target)


PIN_F = [0.17061042364340695, 0.17061042364340695, 0.16002963427084538]
PIN_FLOC = [0.17061042364340695, 0.1450188600968959, 0.16002963427084538]
PIN_R = [17.061042364340693, 11.520456883185826, 12.101098403195707]


def test_f_floc_r_are_pinned_to_the_pre_faza4_values():
    r = _run()
    assert r["F"].tolist() == pytest.approx(PIN_F, abs=1e-9)
    assert r["F_loc"].tolist() == pytest.approx(PIN_FLOC, abs=1e-9)
    assert r["R"].tolist() == pytest.approx(PIN_R, abs=1e-9)


def test_ui_thresholds_do_not_change_f_or_r():
    prof = {**PROFILE, "ui": {"forecast_uncertain_from_day": 1, "forecast_indicative_from_day": 2}}
    a, b = _run(), _run(prof)
    assert a["F"].tolist() == b["F"].tolist()
    assert a["R"].tolist() == b["R"].tolist()
