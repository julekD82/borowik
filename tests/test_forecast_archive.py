from datetime import datetime, timezone

import pandas as pd

from pipeline.forecast_archive import archive_forecast, archive_path
from pipeline.weather import fetch_weather_raw

NOW = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


def _frame(lat, lon, precip):
    dates = pd.date_range("2026-09-26", periods=5, freq="D", tz="Europe/Warsaw").tz_convert("UTC")
    return pd.DataFrame({
        "date": dates, "precipitation_mm": precip, "tmean_c": 10.0, "tmin_c": 5.0, "tmax_c": 15.0,
        "et0_mm": 2.0, "soil_moisture": 0.2, "lat": lat, "lon": lon,
    })


def test_archive_keeps_only_forecast_rows_with_issue_time(tmp_path):
    path = archive_forecast(_frame(50.5, 18.6, [0, 1, 2, 3, 4]), tmp_path, forecast_days=3, now=NOW)
    saved = pd.read_parquet(path)
    assert path == archive_path(tmp_path, NOW.astimezone().date())
    assert len(saved) == 3  # 28, 29, 30.09 only -- past days are not a forecast
    assert list(saved["precipitation_mm"]) == [2, 3, 4]
    assert (saved["fetched_at"] == NOW.isoformat()).all()
    assert (saved["forecast_days"] == 3).all()


def test_second_run_same_day_does_not_overwrite_existing_points(tmp_path):
    archive_forecast(_frame(50.5, 18.6, [0, 1, 2, 3, 4]), tmp_path, 3, now=NOW)
    later = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)
    path = archive_forecast(
        pd.concat([_frame(50.5, 18.6, [9, 9, 9, 9, 9]), _frame(50.6, 18.7, [1, 1, 1, 1, 1])]),
        tmp_path, 3, now=later)
    saved = pd.read_parquet(path)
    old = saved[saved["lat"] == 50.5]
    assert list(old["precipitation_mm"]) == [2, 3, 4]
    assert (old["fetched_at"] == NOW.isoformat()).all()
    assert len(saved[saved["lat"] == 50.6]) == 3


def test_fetch_weather_raw_with_cache_dir_writes_archive_outside_weather_cache(tmp_path):
    calls = []

    def fake_call_api(points, past_days, forecast_days=1):
        calls.append(points)
        today = pd.Timestamp.now(tz="Europe/Warsaw").normalize()
        dates = pd.date_range(today - pd.Timedelta(days=2), periods=4, freq="D").tz_convert("UTC")
        return [{"date": dates, "precipitation_mm": [0.0] * 4, "tmean_c": [10.0] * 4,
                 "tmin_c": [5.0] * 4, "tmax_c": [15.0] * 4, "et0_mm": [2.0] * 4,
                 "soil_moisture": [0.2] * 4} for _ in points]

    fetch_weather_raw([(50.5, 18.6)], past_days=2, forecast_days=2, call_api=fake_call_api, cache_dir=tmp_path)
    archived = list((tmp_path / "archiwum_prognoz").glob("prognoza_*.parquet"))
    assert len(archived) == 1
    assert not str(archived[0]).startswith(str(tmp_path / "weather_points"))
