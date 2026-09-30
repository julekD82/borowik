"""Plan 2.6: pobierz E-OBS 0,1 st. (TG/TN/TX/RR) przyciete do Polski do cache/eobs/.

Uzycie: python scripts/pobierz_eobs.py [--okresy 1980-1994 1995-2010 2011-2025] [--obszary PL BI]
(--obszary: klucze z pipeline.eobs.REGIONS; domyslnie PL; BI = okolice Bielefeld, plan 2.8)
Ok. 1 GB na plik (12 plikow), surowe pliki sa kasowane po konwersji; wznawialne.
Licencja: tylko niekomercyjne badania i edukacja.
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.eobs import PERIODS, REGIONS, VARIABLES, fetch_chunk  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--okresy", nargs="+", default=PERIODS)
    parser.add_argument("--obszary", nargs="+", default=["PL"], choices=sorted(REGIONS))
    args = parser.parse_args(argv)
    for period in args.okresy:
        for var in VARIABLES:
            print(f"E-OBS {var} {period} ...", flush=True)
            print(f"  -> {fetch_chunk(ROOT / 'cache', var, period, args.obszary)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
