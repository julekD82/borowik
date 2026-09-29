"""Faza 4 (poprawka do 1.3): sciezka do paczek BDL z lokalnej konfiguracji, tak by
CLI i launcher (ktory nie przekazuje --bdl-packages-dir) uzywaly paczek."""
import json
import pathlib

import pytest

from pipeline import prepare_trip
from pipeline.local_config import resolve_bdl_packages_dir, load_local_config


def _cfg(tmp_path, data):
    p = tmp_path / "local_config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_explicit_cli_value_wins_over_env_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv("BOROWIK_BDL_DIR", str(tmp_path / "env"))
    cfg = _cfg(tmp_path, {"bdl_packages_dir": str(tmp_path / "cfg")})
    assert resolve_bdl_packages_dir(tmp_path / "cli", tmp_path / "cache", cfg) == tmp_path / "cli"


def test_env_then_config_then_legacy_cache_default(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, {"bdl_packages_dir": str(tmp_path / "cfg")})
    monkeypatch.delenv("BOROWIK_BDL_DIR", raising=False)
    assert resolve_bdl_packages_dir(None, tmp_path / "cache", cfg) == tmp_path / "cfg"
    monkeypatch.setenv("BOROWIK_BDL_DIR", str(tmp_path / "env"))
    assert resolve_bdl_packages_dir(None, tmp_path / "cache", cfg) == tmp_path / "env"
    monkeypatch.delenv("BOROWIK_BDL_DIR")
    assert resolve_bdl_packages_dir(None, tmp_path / "cache", tmp_path / "brak.json") == tmp_path / "cache" / "bdl_packages"


def test_relative_config_path_is_relative_to_the_config_file(tmp_path, monkeypatch):
    monkeypatch.delenv("BOROWIK_BDL_DIR", raising=False)
    cfg = _cfg(tmp_path, {"bdl_packages_dir": "BDL"})
    assert resolve_bdl_packages_dir(None, tmp_path / "cache", cfg) == tmp_path / "BDL"


def test_broken_config_is_ignored_not_fatal(tmp_path):
    p = tmp_path / "local_config.json"
    p.write_text("{nie json", encoding="utf-8")
    assert load_local_config(p) == {}


def test_main_run_as_the_launcher_does_uses_the_configured_packages_dir(tmp_path, monkeypatch):
    """Launcher wola: python -m pipeline.prepare_trip --lat --lon --radius-km (bez --bdl-packages-dir)."""
    seen = {}
    monkeypatch.delenv("BOROWIK_BDL_DIR", raising=False)
    monkeypatch.setattr("pipeline.local_config.LOCAL_CONFIG_PATH", _cfg(tmp_path, {"bdl_packages_dir": "BDL"}))
    monkeypatch.setattr(prepare_trip, "run_trip_preparation", lambda **kw: seen.update(kw) or {
        "mask_passing": 0, "stand_count": 0, "region_count": 0, "forecast_days": 1,
        "scores_path": "", "stands_path": "", "geojson_path": "", "regions_path": "", "details_path": "",
        "gdos_failed_tile_count": 0, "osm_failed_tile_count": 0, "tile_count": 1})
    prepare_trip.main(["--lat", "50.5269", "--lon", "18.605", "--radius-km", "25"])
    assert seen["bdl_packages_dir"] == tmp_path / "BDL"
