import numpy as np
import pandas as pd
import pytest

from pipeline.weather import (
    make_grid,
    fetch_weather_raw,
    compute_weather_features,
    climatology_window_values,
    percentile_rank,
)


def test_make_grid_covers_bbox_with_points_in_lat_lon():
    bbox = (486000.0, 380000.0, 496000.0, 390000.0)  # 10x10 km
    grid = make_grid(bbox, spacing_m=5000.0)
    assert len(grid) >= 4  # at least a 2x2 grid over 10km with 5km spacing
    for lat, lon in grid:
        assert 40.0 < lat < 60.0
        assert 10.0 < lon < 25.0


def test_fetch_weather_raw_uses_injected_call_api():
    calls = []

    def fake_call_api(lat, lon, past_days):
        calls.append((lat, lon, past_days))
        dates = pd.date_range("2026-06-25", periods=3, freq="D")
        return {
            "date": dates,
            "precipitation_mm": [1.0, 2.0, 3.0],
            "tmean_c": [12.0, 13.0, 14.0],
            "tmin_c": [8.0, 9.0, 10.0],
            "tmax_c": [16.0, 17.0, 18.0],
            "et0_mm": [1.5, 1.6, 1.7],
            "soil_moisture": [0.3, 0.31, 0.32],
        }

    df = fetch_weather_raw([(50.5, 18.6), (50.55, 18.65)], past_days=3, call_api=fake_call_api)

    assert len(calls) == 2
    assert len(df) == 6
    assert set(df.columns) >= {"lat", "lon", "date", "precipitation_mm", "tmean_c", "tmin_c", "tmax_c", "et0_mm", "soil_moisture"}


def _synthetic_daily_df():
    dates = pd.date_range("2026-05-01", periods=30, freq="D")
    return pd.DataFrame({
        "lat": [50.5] * 30,
        "lon": [18.6] * 30,
        "date": dates,
        "precipitation_mm": [1.0] * 30,
        "tmean_c": [13.0] * 30,
        "tmin_c": [5.0] * 30,
        "tmax_c": [20.0] * 30,
        "et0_mm": [1.0] * 30,
        "soil_moisture": [0.4] * 30,
    })


def test_compute_weather_features_windows():
    feat = compute_weather_features(_synthetic_daily_df())
    row = feat.iloc[0]
    assert row["p5"] == pytest.approx(5.0)
    assert row["p7"] == pytest.approx(7.0)
    assert row["p14"] == pytest.approx(14.0)
    assert row["p30"] == pytest.approx(30.0)
    assert row["tmean20"] == pytest.approx(13.0)
    assert row["tmin3"] == pytest.approx(5.0)
    assert row["days_since_p10"] >= 29  # no day ever reached 10mm
    assert row["dry_spell_days"] == 0  # 1mm/day never below 1mm threshold


def test_percentile_rank_of_median_like_value():
    historical = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    assert percentile_rank(30.0, historical) == pytest.approx(0.5, abs=0.15)
    assert percentile_rank(5.0, historical) == pytest.approx(0.0, abs=0.05)
    assert percentile_rank(55.0, historical) == pytest.approx(1.0, abs=0.05)


def test_climatology_window_values_filters_by_point_and_doy_window():
    clim_df = pd.DataFrame({
        "lat": [50.5, 50.5, 50.5, 50.5, 60.0],
        "lon": [18.6, 18.6, 18.6, 18.6, 18.6],
        "date": pd.to_datetime(["2000-08-10", "2000-08-20", "2000-09-15", "2005-08-12", "2000-08-11"]),
        "cwb26": [1.0, 2.0, 99.0, 3.0, 100.0],
    })
    # target day_of_year ~ Aug 15 (227), window 15 days -> Aug 1..Aug 30 roughly
    from datetime import date
    doy = date(2026, 8, 15).timetuple().tm_yday
    values = climatology_window_values(clim_df, lat=50.5, lon=18.6, day_of_year=doy, column="cwb26", window_days=15)
    assert 1.0 in values and 2.0 in values and 3.0 in values
    assert 99.0 not in values   # outside +/-15 day window (Sep 15)
    assert 100.0 not in values  # wrong point (lat 60.0)
