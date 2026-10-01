"""Eksport 'na telefon': KMZ (Locus Map / Guru Maps) z biezacej analizy albo zapisanej migawki.

Uzycie:
  python scripts/eksport_telefon.py [--nazwa "Zawadzkie"] [--migawka <id z trips/index.json>]
                                    [--telefon-dir KATALOG]

Do pliku trafia tylko najlepsze 5% wydzielen (wg R), 5 rejonow i parkingi.

Wynik: <telefon_dir>/borowik_<obszar>_<data>.kmz (telefon_dir z local_config.json, domyslnie
dane_telefon/ obok niego). Opis formatu: pipeline/phone_kmz.py, instrukcja: docs/TELEFON.md."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from launcher.trip_archive import read_index, slugify  # noqa: E402
from pipeline.local_config import resolve_telefon_dir  # noqa: E402
from pipeline.phone_kmz import export_kmz, load_source  # noqa: E402

MB = 1024 * 1024


def _fmt_mb(size_bytes: int) -> str:
    return f"{size_bytes / MB:.2f} MB"


def _area_name(args, source: dict, trips_dir: pathlib.Path) -> str:
    if args.nazwa:
        return args.nazwa
    if args.migawka:
        entry = next((e for e in read_index(trips_dir / "index.json") if e.get("id") == args.migawka), None)
        return entry["name"] if entry and entry.get("name") else args.migawka
    manifest = source.get("manifest") or {}
    if "lat" in manifest and "lon" in manifest:
        return f"{manifest['lat']:.2f}N {manifest['lon']:.2f}E"
    return "analiza"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Eksport KMZ na telefon (Locus Map / Guru Maps).")
    parser.add_argument("--nazwa", help="nazwa obszaru do nazwy pliku (domyslnie: nazwa migawki albo wspolrzedne)")
    parser.add_argument("--migawka", help="id zapisanej migawki (frontend/public/data/trips/<id>); brak = biezaca analiza")
    parser.add_argument("--telefon-dir", help="katalog wyjsciowy (domyslnie telefon_dir z local_config.json)")
    parser.add_argument("--data-dir", default=str(ROOT / "frontend" / "public" / "data"))
    args = parser.parse_args(argv)

    data_dir = pathlib.Path(args.data_dir)
    trips_dir = data_dir / "trips"
    source_dir = trips_dir / args.migawka if args.migawka else data_dir
    if args.migawka and not source_dir.is_dir():
        print(f"BLAD: nie ma migawki '{args.migawka}' w {trips_dir}.")
        return 1
    try:
        source = load_source(source_dir)
    except ValueError as exc:
        print(f"BLAD: {exc}")
        return 1

    day = source.get("day") or (source.get("manifest") or {}).get("day") or "bez-daty"
    area = _area_name(args, source, trips_dir)
    out_dir = resolve_telefon_dir(args.telefon_dir)
    path = out_dir / f"borowik_{slugify(area)}_{day}.kmz"

    print(f"Zrodlo: {'migawka ' + args.migawka if args.migawka else 'biezaca analiza'} ({day}), obszar: {area}")
    print("Wybieram najlepsze 5% wydzielen, upraszczam ich geometrie (ok. 3 m) i buduje KMZ...")
    try:
        result = export_kmz(source, path, title=f"Borowik · {area} · {day}")
    except (ValueError, OSError) as exc:
        print(f"BLAD: {exc}")
        return 1

    print(f"Zapisano: {result.path}")
    print(f"Wydzielenia w masce: {result.stand_count}; w pliku (najlepsze 5%): {result.exported_count}; "
          f"rejony: {result.region_count}; parkingi: {result.parking_count}")
    print(f"Rozmiar KMZ: {_fmt_mb(result.size_bytes)}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # launcher czyta potok w kodowaniu systemowym
    sys.exit(main())
