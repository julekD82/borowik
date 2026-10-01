"""scripts/eksport_telefon.py: wybor zrodla (biezaca analiza / migawka), nazwa pliku, komunikaty."""
import importlib.util
import json
import pathlib
import zipfile

import pytest

from tests.test_phone_kmz import _dataset

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_script():
    spec = importlib.util.spec_from_file_location("eksport_telefon", ROOT / "scripts" / "eksport_telefon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_source(directory, data):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "scores.json").write_text(json.dumps(data["scores"]), encoding="utf-8")
    (directory / "stands.geojson").write_text(json.dumps(data["stands"]), encoding="utf-8")
    (directory / "regions.json").write_text(json.dumps(data["regions"]), encoding="utf-8")
    (directory / "access_points.json").write_text(json.dumps(data["access_points"]), encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps(data["manifest"]), encoding="utf-8")


def test_current_analysis_uses_place_name_and_day_in_file_name(tmp_path, capsys):
    script = _load_script()
    data_dir, out = tmp_path / "data", tmp_path / "telefon"
    _write_source(data_dir, _dataset())
    code = script.main(["--data-dir", str(data_dir), "--telefon-dir", str(out), "--nazwa", "Zawadzkie 30"])
    assert code == 0
    target = out / "borowik_zawadzkie-30_2026-09-30.kmz"
    assert target.exists()
    with zipfile.ZipFile(target) as z:
        assert z.namelist() == ["doc.kml"]
    text = capsys.readouterr().out
    assert "borowik_zawadzkie-30_2026-09-30.kmz" in text and "MB" in text


def test_without_place_name_file_name_falls_back_to_coordinates(tmp_path):
    script = _load_script()
    data_dir, out = tmp_path / "data", tmp_path / "telefon"
    _write_source(data_dir, _dataset())
    script.main(["--data-dir", str(data_dir), "--telefon-dir", str(out)])
    assert [p.name for p in out.iterdir()] == ["borowik_50-60n-18-40e_2026-09-30.kmz"]


def test_snapshot_is_read_from_trips_dir_and_named_after_index_entry(tmp_path):
    script = _load_script()
    data_dir, trips, out = tmp_path / "data", tmp_path / "data" / "trips", tmp_path / "telefon"
    _write_source(trips / "kieleczka-2026-09-28", _dataset(n=40))
    (trips / "index.json").write_text(json.dumps([
        {"id": "kieleczka-2026-09-28", "name": "Kieleczka", "radius_km": 20, "day": "2026-09-28",
         "lat": 50.6, "lon": 18.4, "saved_at": "x"}]), encoding="utf-8")
    code = script.main(["--data-dir", str(data_dir), "--telefon-dir", str(out), "--migawka", "kieleczka-2026-09-28"])
    assert code == 0
    assert [p.name for p in out.iterdir()] == ["borowik_kieleczka_2026-09-30.kmz"]


def test_unknown_snapshot_returns_error_and_writes_nothing(tmp_path, capsys):
    script = _load_script()
    code = script.main(["--data-dir", str(tmp_path), "--telefon-dir", str(tmp_path / "out"), "--migawka", "nie-ma"])
    assert code == 1
    assert "nie-ma" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_missing_current_analysis_returns_error(tmp_path, capsys):
    script = _load_script()
    code = script.main(["--data-dir", str(tmp_path / "pusto"), "--telefon-dir", str(tmp_path / "out")])
    assert code == 1
    assert "scores.json" in capsys.readouterr().out


def test_reports_masked_and_exported_counts_and_size(tmp_path, capsys):
    script = _load_script()
    data_dir, out = tmp_path / "data", tmp_path / "telefon"
    _write_source(data_dir, _dataset())
    assert script.main(["--data-dir", str(data_dir), "--telefon-dir", str(out), "--nazwa", "x"]) == 0
    text = capsys.readouterr().out
    assert "Wydzielenia w masce: 100" in text and "w pliku (najlepsze 5%): 5" in text and "MB" in text
