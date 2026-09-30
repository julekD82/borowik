"""Lokalna konfiguracja maszyny (poza repozytorium): `local_config.json` w katalogu repo,
wpisany w .gitignore. Obecnie jeden klucz:

  {"bdl_packages_dir": "BDL",      # sciezka bezwzgledna albo wzgledem tego pliku
   "telefon_dir": "dane_telefon"}  # gdzie zapisywac KMZ "na telefon" (np. folder synchronizowany z Dyskiem/OneDrive)

Powod (Faza 4, poprawka do 1.3): launcher wola `python -m pipeline.prepare_trip --lat --lon
--radius-km` bez --bdl-packages-dir, a domyslny katalog `<cache>/bdl_packages` nie istnial,
wiec kazdy przebieg mial 100% skladu z WFS. Kolejnosc: parametr CLI > zmienna srodowiskowa
BOROWIK_BDL_DIR > local_config.json > `<cache>/bdl_packages`."""
import json
import os
from pathlib import Path

LOCAL_CONFIG_PATH = Path(__file__).resolve().parent.parent / "local_config.json"


def load_local_config(path: Path | None = None) -> dict:
    path = Path(path or LOCAL_CONFIG_PATH)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_bdl_packages_dir(cli_value, cache_dir: Path, config_path: Path | None = None) -> Path:
    if cli_value:
        return Path(cli_value)
    env = os.environ.get("BOROWIK_BDL_DIR")
    if env:
        return Path(env)
    config_path = Path(config_path or LOCAL_CONFIG_PATH)
    configured = load_local_config(config_path).get("bdl_packages_dir")
    if configured:
        p = Path(configured)
        return p if p.is_absolute() else config_path.parent / p
    return Path(cache_dir) / "bdl_packages"


def resolve_telefon_dir(cli_value, config_path: Path | None = None) -> Path:
    """Katalog eksportu KMZ na telefon: parametr CLI > `telefon_dir` z local_config.json >
    `dane_telefon/` obok local_config.json (w .gitignore)."""
    if cli_value:
        return Path(cli_value)
    config_path = Path(config_path or LOCAL_CONFIG_PATH)
    configured = load_local_config(config_path).get("telefon_dir")
    if configured:
        p = Path(configured)
        return p if p.is_absolute() else config_path.parent / p
    return config_path.parent / "dane_telefon"
