"""Plan 2.8: pobierz dane monitoringu Boletus edulis z Bielefeld (Zenodo) do cache/bielefeld/.

Uzycie: python scripts/pobierz_bielefeld.py
- V1.2 (doi 10.5281/zenodo.20591123, zip ok. 713 kB) -- wersja uzywana w analizie,
- wersja pierwsza (doi 10.5281/zenodo.17881359, Data_ready.csv ok. 100 kB) -- tylko do porownania.
Pierwsze pobranie sprawdza MD5 podane przez Zenodo i zapisuje SHA-256 w cache/bielefeld/SHA256SUMS;
kolejne uruchomienia NIE pobieraja ponownie, tylko weryfikuja SHA-256 (niezgodnosc = blad).
Na koniec zapisuje tabele do dane_walidacyjne/bielefeld/ (pipeline.bielefeld.write_validation_tables).
Licencja danych: CC BY 4.0 (Brejon Lamartiniere & Hoffman).
"""
import argparse
import hashlib
import pathlib
import sys
import zipfile

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.bielefeld import AUTHORS_CSV, write_validation_tables  # noqa: E402

# (plik lokalny, URL, md5 z API Zenodo)
FILES = [
    ("Boletus_fruiting_triggers-V1.2.zip",
     "https://zenodo.org/api/records/20591123/files/ebrejonl/Boletus_fruiting_triggers-V1.2.zip/content",
     "a5299db56022af2620635a36274e811f"),
    ("v1_Data_ready.csv",
     "https://zenodo.org/api/records/17881359/files/Data_ready.csv/content",
     "703a8d90c033197431cd7b6fd6743be5"),
]
SUMS_FILE = "SHA256SUMS"


def file_hash(path: pathlib.Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_sums(path: pathlib.Path) -> dict[str, str]:
    """Plik w formacie sha256sum: '<hash>  <nazwa>'."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            out[name.strip()] = digest
    return out


def write_sums(path: pathlib.Path, sums: dict[str, str]) -> None:
    path.write_text("".join(f"{sums[k]}  {k}\n" for k in sorted(sums)), encoding="utf-8")


def ensure_file(dest: pathlib.Path, url: str, md5: str, sums: dict[str, str], get=requests.get) -> str:
    """Zwraca SHA-256 pliku. Istniejacy plik jest tylko weryfikowany wzgledem sums (bez sieci);
    nowy jest pobierany, sprawdzany wzgledem MD5 z Zenodo i dopisywany do sums."""
    name = dest.name
    if dest.exists() and name in sums:
        digest = file_hash(dest, "sha256")
        if digest != sums[name]:
            raise RuntimeError(f"{name}: SHA-256 {digest} rozni sie od zapisanego {sums[name]}")
        return digest
    resp = get(url, timeout=120)
    resp.raise_for_status()
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(resp.content)
    got_md5 = file_hash(tmp, "md5")
    if got_md5 != md5:
        tmp.unlink()
        raise RuntimeError(f"{name}: MD5 {got_md5} rozni sie od podanego przez Zenodo {md5}")
    tmp.replace(dest)
    sums[name] = file_hash(dest, "sha256")
    return sums[name]


def unpack(zip_path: pathlib.Path, out_dir: pathlib.Path) -> list[str]:
    """Rozpakuj zip (idempotentnie); zwraca liste plikow w archiwum."""
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = (out_dir / member).resolve()
            if not str(target).startswith(str(out_dir.resolve())):
                raise RuntimeError(f"niebezpieczna sciezka w zipie: {member}")
        zf.extractall(out_dir)
        return zf.namelist()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=pathlib.Path, default=ROOT / "cache" / "bielefeld")
    parser.add_argument("--dane", type=pathlib.Path, default=ROOT / "dane_walidacyjne" / "bielefeld",
                        help="katalog trwalego zapisu tabel (owocniki dzienne, pogoda autorow)")
    args = parser.parse_args(argv)
    cache = args.cache
    cache.mkdir(parents=True, exist_ok=True)
    sums_path = cache / SUMS_FILE
    sums = read_sums(sums_path)
    for name, url, md5 in FILES:
        digest = ensure_file(cache / name, url, md5, sums)
        print(f"{name}: SHA-256 {digest}", flush=True)
    write_sums(sums_path, sums)
    members = unpack(cache / FILES[0][0], cache / "V1.2")
    print(f"Rozpakowano {len(members)} pozycji do {cache / 'V1.2'}", flush=True)
    csv = next(m for m in members if m.endswith(AUTHORS_CSV))
    for name, path in write_validation_tables(pd.read_csv(cache / "V1.2" / csv), args.dane).items():
        print(f"{name}: {path} (SHA-256 {file_hash(pathlib.Path(path), 'sha256')})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
