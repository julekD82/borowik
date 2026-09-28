import importlib.util
import json
import pathlib

import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "zapisz_prognoze", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "zapisz_prognoze.py")
zp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zp)


def test_load_points_limits_and_shape(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps([{"nazwa": "A", "lat": 50.1, "lon": 18.2}]), encoding="utf-8")
    assert zp.load_points(f) == [("A", 50.1, 18.2)]
    f.write_text(json.dumps([{"nazwa": str(i), "lat": 50, "lon": 18} for i in range(11)]), encoding="utf-8")
    with pytest.raises(ValueError):
        zp.load_points(f)


def test_main_writes_archive_for_every_point(tmp_path, monkeypatch):
    monkeypatch.setattr(zp, "ROOT", tmp_path)
    pts = tmp_path / "p.json"
    pts.write_text(json.dumps([{"nazwa": "A", "lat": 50.1, "lon": 18.2}, {"nazwa": "B", "lat": 50.2, "lon": 18.3}]),
                   encoding="utf-8")

    def fake_call(points, past_days, forecast_days=1):
        today = pd.Timestamp.now(tz="Europe/Warsaw").normalize()
        d = pd.date_range(today, periods=3, freq="D").tz_convert("UTC")
        return [{"date": d, "precipitation_mm": [0.0] * 3, "tmean_c": [10.0] * 3, "tmin_c": [5.0] * 3,
                 "tmax_c": [15.0] * 3, "et0_mm": [2.0] * 3, "soil_moisture": [0.2] * 3} for _ in points]

    assert zp.main(["--punkty", str(pts)], call_api=fake_call) == 0
    files = list((tmp_path / "cache" / "archiwum_prognoz").glob("prognoza_*.parquet"))
    assert len(files) == 1
    assert pd.read_parquet(files[0])["lat"].nunique() == 2
