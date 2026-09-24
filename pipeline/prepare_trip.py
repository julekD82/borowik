import argparse
from datetime import date

MIN_RADIUS_KM = 10.0
MAX_RADIUS_KM = 50.0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prepare_trip",
        description="Przygotuj wyjazd: policz rejony poszukiwan prawdziwkow dla podanej lokalizacji.",
    )
    parser.add_argument("--lat", type=float, required=True, help="Szerokosc geograficzna (WGS84)")
    parser.add_argument("--lon", type=float, required=True, help="Dlugosc geograficzna (WGS84)")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Etykieta dnia w nazwach plikow wynikowych (YYYY-MM-DD), domyslnie dzisiaj. "
             "Nie zmienia okna pogodowego (zawsze 'teraz' -- patrz docs/projekt-borowik.md).",
    )
    parser.add_argument(
        "--radius-km", type=float, default=25.0,
        help=f"Deklarowany promien poszukiwan ({MIN_RADIUS_KM:.0f}-{MAX_RADIUS_KM:.0f} km). "
             "Obecnie tylko walidowany -- przetwarzany jest jeden kafel 10x10 km wokol punktu "
             "(patrz docs/projekt-borowik.md sec.8.1).",
    )
    parser.add_argument("--profile", type=str, default="profiles/boletus_edulis.yaml")
    parser.add_argument("--out-dir", type=str, default="notebooks/output")
    parser.add_argument("--cache-dir", type=str, default="cache")
    args = parser.parse_args(argv)
    if not (MIN_RADIUS_KM <= args.radius_km <= MAX_RADIUS_KM):
        parser.error(f"--radius-km must be between {MIN_RADIUS_KM:.0f} and {MAX_RADIUS_KM:.0f}")
    if args.date is not None:
        try:
            date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"--date must be YYYY-MM-DD, got {args.date!r}")
    return args
