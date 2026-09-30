"""Trwaly zapis zamrozonych zbiorow walidacji 2.4/2.5 (decyzja wlasciciela 30.09.2026).

- KOPIUJE oryginaly z notebooks/output/walidacja/ do dane_walidacyjne/gbif_2_4_2_5/ (w .gitignore: zawieraja
  nazwy obserwatorow GBIF); oryginaly zostaja na miejscu, bo notatniki 12-16 czytaja tamte sciezki.
- Zapisuje kopie z pseudonimami (obs_001, obs_002, ... wspolne dla wszystkich plikow) do
  dane_walidacyjne/gbif_2_4_2_5_pseudonimy/ (commitowane); tabela przypisan tylko lokalnie
  (dane_walidacyjne/gbif_2_4_2_5/przypisania_obserwatorow.csv).
- Istniejace kopie oryginalow sa tylko weryfikowane (SHA-256), nie nadpisywane.

Uzycie: python scripts/kopiuj_zbiory_gbif.py
"""
import hashlib
import pathlib
import shutil
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "notebooks" / "output" / "walidacja"
FILES = ["2_4_zbior_pozytywy.csv", "2_4_zbior_tlo_a.csv", "2_4_zbior_tlo_b.csv", "2_5_zbior_zamrozony.csv"]
OBSERVER_COLS = ("observer", "observer_id")
ANON_PREFIX = "anon_"  # observer_id = anon_<klucz GBIF> dla rekordow bez obserwatora (nie jest to dana osobowa)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pseudonymize(frames: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Zastap obserwatorow kolejnymi numerami obs_001... (kolejnosc pierwszego wystapienia: pliki w podanej
    kolejnosci, wiersze od gory). Puste wartosci i identyfikatory 'anon_...' zostaja bez zmian."""
    mapping: dict[str, str] = {}

    def is_person(v) -> bool:
        return isinstance(v, str) and v.strip() != "" and not v.startswith(ANON_PREFIX)

    for df in frames.values():
        for _, row in df.iterrows():
            for col in OBSERVER_COLS:
                if col in df.columns and is_person(row[col]) and row[col] not in mapping:
                    mapping[row[col]] = f"obs_{len(mapping) + 1:03d}"
    out = {}
    for name, df in frames.items():
        df = df.copy()
        for col in OBSERVER_COLS:
            if col in df.columns:
                df[col] = [mapping[v] if is_person(v) else v for v in df[col]]
        out[name] = df
    return out, mapping


def main() -> int:
    orig_dir = ROOT / "dane_walidacyjne" / "gbif_2_4_2_5"
    pub_dir = ROOT / "dane_walidacyjne" / "gbif_2_4_2_5_pseudonimy"
    orig_dir.mkdir(parents=True, exist_ok=True)
    pub_dir.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name in FILES:
        src, dst = SRC / name, orig_dir / name
        if dst.exists():
            if src.exists() and sha256(src) != sha256(dst):
                raise RuntimeError(f"{name}: kopia rozni sie od pliku w {SRC}")
        else:
            shutil.copy2(src, dst)
        print(f"{name}: SHA-256 {sha256(dst)}", flush=True)
        frames[name] = pd.read_csv(dst, dtype=str, keep_default_na=False, na_values=[""])
    pub, mapping = pseudonymize(frames)
    for name, df in pub.items():
        df.to_csv(pub_dir / name, index=False, lineterminator="\n")
        print(f"  pseudonimy -> {pub_dir / name} (SHA-256 {sha256(pub_dir / name)})", flush=True)
    pd.DataFrame({"obserwator": list(mapping), "pseudonim": list(mapping.values())}).to_csv(
        orig_dir / "przypisania_obserwatorow.csv", index=False, lineterminator="\n")
    print(f"{len(mapping)} obserwatorow; przypisania tylko lokalnie: {orig_dir / 'przypisania_obserwatorow.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
