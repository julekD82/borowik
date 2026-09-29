"""Plan 2.3 (uzupelnienie): ile rekordow B. edulis (niepewnosc <= 100 m, GBIF PL)
lezy w lesie z danymi BDL -- male zapytania WFS (bufor 150 m) per rekord,
a nie pelne kafle 10x10 km (359 kafli = zbedne obciazenie publicznego WFS).

Wejscie: .cache/gbif_inventory/edulis_le100.json (patrz raport 2.3).
Wynik: notebooks/output/gbif_edulis_forest_coverage.json. Bez testow skutecznosci.
Run: .venv/Scripts/python.exe notebooks/11_gbif_edulis_forest_coverage.py
"""
import json
import pathlib
import time
from collections import Counter

from pipeline.bdl import fetch_bdl
from pipeline.rdlp import fetch_rdlp_boundaries_cached, resolve_rdlp_layer
from pipeline.tiles import _TO_2180

SRC = pathlib.Path(".cache/gbif_inventory/edulis_le100.json")
CACHE = pathlib.Path(".cache/gbif_inventory/edulis_le100_bdl.json")
OUT = pathlib.Path("notebooks/output/gbif_edulis_forest_coverage.json")
HALF_M = 150.0


def classify(rec: dict, rdlp) -> dict:
    layer = resolve_rdlp_layer(rec["lat"], rec["lon"], rdlp)
    if layer is None:
        return {"status": "poza_rdlp"}
    e, n = _TO_2180.transform(rec["lon"], rec["lat"])
    frame = fetch_bdl(layer, (n - HALF_M, e - HALF_M, n + HALF_M, e + HALF_M))
    if not len(frame):
        return {"status": "brak_wydzielen"}
    types = sorted(set(frame["area_type"].astype(str))) if "area_type" in frame.columns else []
    return {"status": "las_d_stan" if "D-STAN" in types else "inne_wydzielenia", "typy": types}


def main() -> None:
    records = json.loads(SRC.read_text(encoding="utf-8"))
    done = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    rdlp = fetch_rdlp_boundaries_cached(pathlib.Path("cache"))
    for i, rec in enumerate(records, 1):
        key = str(rec["key"])
        if key in done:
            continue
        try:
            done[key] = classify(rec, rdlp)
        except Exception as exc:  # zapis czesciowy, wznowienie z cache
            done[key] = {"status": "blad", "blad": str(exc)[:200]}
        if i % 20 == 0:
            CACHE.write_text(json.dumps(done), encoding="utf-8")
            print(f"{i}/{len(records)}", flush=True)
        time.sleep(0.2)
    CACHE.write_text(json.dumps(done), encoding="utf-8")
    counts = Counter(v["status"] for v in done.values())
    forest_obs = {r["by"] for r in records if done[str(r["key"])]["status"] == "las_d_stan"}
    result = {"rekordow": len(records), "status": dict(counts), "obserwatorow_w_lesie_d_stan": len(forest_obs)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
