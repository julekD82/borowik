"""Plan 2.1: sprawdz zapisy wyjsc. Uzycie: python scripts/sprawdz_dane_terenowe.py [katalog]"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.field_data import summary_lines, validate  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Walidacja plikow z dane_terenowe/ (bez analizy skutecznosci).")
    parser.add_argument("katalog", nargs="?", default=str(ROOT / "dane_terenowe"))
    parser.add_argument("--trips-dir", default=str(ROOT / "frontend" / "public" / "data" / "trips"))
    args = parser.parse_args(argv)
    report = validate(pathlib.Path(args.katalog), pathlib.Path(args.trips_dir))
    print("\n".join(summary_lines(report)))
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
