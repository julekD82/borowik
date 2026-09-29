"""Plan 2.2: codzienny zapis prognozy dla kilku stalych punktow (harmonogram Windows, 6:00).

Uzycie: python scripts/zapisz_prognoze.py [--punkty plik.json]
Punkty (max 10): dane_terenowe/punkty_prognozy.json (prywatne, poza repo); gdy brak --
scripts/punkty_prognozy.example.json. Zapis trafia do cache/archiwum_prognoz/ przez
pipeline.weather.fetch_weather_raw (ten sam mechanizm co przy analizie).
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAX_POINTS = 10
FORECAST_DAYS = 16


def load_points(path: pathlib.Path) -> list[tuple[str, float, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    points = [(p["nazwa"], float(p["lat"]), float(p["lon"])) for p in raw]
    if not points:
        raise ValueError("Pusta lista punktow")
    if len(points) > MAX_POINTS:
        raise ValueError(f"Za duzo punktow ({len(points)}); limit {MAX_POINTS}")
    return points


def default_points_path() -> pathlib.Path:
    private = ROOT / "dane_terenowe" / "punkty_prognozy.json"
    return private if private.exists() else ROOT / "scripts" / "punkty_prognozy.example.json"


def main(argv=None, call_api=None) -> int:
    parser = argparse.ArgumentParser(description="Zapisz prognoze Open-Meteo do archiwum prognoz.")
    parser.add_argument("--punkty", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)
    from pipeline.weather import fetch_weather_raw
    path = args.punkty or default_points_path()
    points = load_points(path)
    print(f"Punkty z {path.name}: {', '.join(n for n, _, _ in points)}")
    kwargs = {"call_api": call_api} if call_api else {}
    fetch_weather_raw([(lat, lon) for _, lat, lon in points], past_days=1, forecast_days=FORECAST_DAYS,
                      cache_dir=ROOT / "cache", **kwargs)
    print("Zapisano do cache/archiwum_prognoz/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
