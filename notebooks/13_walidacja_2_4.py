"""Faza 2.4: kontrola przestrzenna H na rekordach GBIF, wg docs/WALIDACJA_REGULY.md
i docs/WALIDACJA_IMPLEMENTACJA.md. JEDEN przebieg analizy glownej; dodatki po zobaczeniu
wynikow oznaczac jako eksploracyjne w raporcie. Bez zmiany wag H.

Run: .venv/Scripts/python.exe notebooks/13_walidacja_2_4.py
"""
import json
import pathlib
import random
import time

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from shapely.geometry import Point

from pipeline import gbif_client as gb
from pipeline import validation_stats as vs
from pipeline.bdl import fetch_bdl
from pipeline.bdl_packages import load_packages
from pipeline.habitat import load_profile
from pipeline.rdlp import fetch_rdlp_boundaries_cached, resolve_rdlp_layer
from pipeline.spatial_check import record_h
from pipeline.tiles import _TO_2180

OUT = pathlib.Path("notebooks/output/walidacja")
WFS_CACHE = pathlib.Path(".cache/gbif_inventory/h_records.json")
UNC = "0,100"
MAIN_FROM_YEAR = 2021
MIN_POS, MIN_OBSERVERS = 100, 30
BG_FACTOR = 5
UNKNOWN_LIMIT = 0.20
SEED = vs.SEED
YEARS = range(2015, 2027)
MONTHS_B = range(7, 12)
MAX_RANDOM_OFFSET = 20000  # glebsze offsety GBIF odpowiadaja bardzo wolno
PARALLEL = 8              # rownolegle zapytania GBIF (tylko przyspieszenie)
N_PAGES_B = 400            # stron po 300 rekordow na krolestwo (tlo b)


def observer_of(r) -> str:
    o = r.get("observer")
    return str(o).strip() if o is not None and str(o).strip() else f"anon_{r['key']}"


# ---- pule kandydatow -------------------------------------------------------------------------------------------
def positives() -> list[dict]:
    return [gb.slim(r) for r in gb.fetch_all({**gb.BASE, **gb.BOLETUS, "coordinateUncertaintyInMeters": UNC})]


def fungi_pool() -> list[dict]:
    out = []
    for year in YEARS:
        out += [gb.slim(r) for r in gb.fetch_all(
            {**gb.BASE, "taxonKey": gb.FUNGI_TAXON_KEY, "coordinateUncertaintyInMeters": UNC, "year": year})]
    return [r for r in out if r["species"] != "Boletus edulis"]


def nonfungal_pool(kingdom_key: int, rng: random.Random, n_pages: int) -> list[dict]:
    """Losowe strony po 300 rekordow z komorek (rok x miesiac VII-XI), waga = liczebnosc komorki; 5 losowych rekordow / strone."""
    cells = []
    for year in YEARS:
        for month in MONTHS_B:
            p = {**gb.BASE, "taxonKey": kingdom_key, "coordinateUncertaintyInMeters": UNC, "year": year, "month": month}
            c = gb.count(p)
            if c:
                cells.append((p, c))
    total = sum(c for _, c in cells)
    picks = rng.choices(range(len(cells)), weights=[c for _, c in cells], k=n_pages)
    requests_list, seen = [], set()
    for ci in picks:  # losowania najpierw (deterministyczne), pobieranie potem rownolegle
        p, c = cells[ci]
        offset = rng.randrange(0, max(1, min(c, MAX_RANDOM_OFFSET) // gb.PAGE)) * gb.PAGE
        if (ci, offset) not in seen:
            seen.add((ci, offset))
            requests_list.append({**p, "limit": gb.PAGE, "offset": offset})
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        pages = list(pool.map(lambda q: gb.query(q)["results"], requests_list))
    out = []
    for results in pages:
        for r in rng.sample(results, min(5, len(results))):
            out.append(gb.slim(r))
    print(f"  kingdom {kingdom_key}: {len(out)} kandydatow ({total} rekordow w komorkach)", flush=True)
    return out


_KATOWICE = None


def _katowice(rdlp):
    global _KATOWICE
    if _KATOWICE is None:
        _KATOWICE = rdlp[rdlp["region_cd"] == "02"].geometry.union_all()
    return _KATOWICE


# ---- H rekordu z WFS ---------------------------------------------------------------------------------------------
def load_cache() -> dict:
    return json.loads(WFS_CACHE.read_text(encoding="utf-8")) if WFS_CACHE.exists() else {}


def compute(rec: dict, rdlp, profile, packages, cache: dict) -> dict:
    key = str(rec["key"])
    if key in cache:
        return cache[key]
    layer = resolve_rdlp_layer(rec["lat"], rec["lon"], rdlp)
    if layer is None:
        cache[key] = {"forest": False, "status": "poza_rdlp"}
        return cache[key]
    e, n = _TO_2180.transform(rec["lon"], rec["lat"])
    r = max(float(rec["unc"] or 0), 10.0)
    try:
        stands = fetch_bdl(layer, (n - r - 5, e - r - 5, n + r + 5, e + r + 5))
        res = record_h(stands, e, n, r, profile, packages)
        region02 = bool(_katowice(rdlp).contains(Point(e, n)))
        cache[key] = {"forest": res.forest, "h": res.h, "masked": res.masked, "unknown": res.unknown_code,
                      "main_stand": res.main_stand, "h_pkg": res.h_package, "katowice": region02, "status": "ok"}
    except Exception as exc:  # zapis bledu, rekord wypada z analizy (liczony w raporcie)
        cache[key] = {"forest": False, "status": f"blad: {str(exc)[:80]}"}
    time.sleep(0.15)
    return cache[key]


def fill(pool: list[dict], quota: int, rdlp, profile, packages, cache, rng) -> list[dict]:
    """Przetwarzaj kandydatow (losowa kolejnosc) az do `quota` rekordow w lesie D-STAN."""
    pool = pool[:]
    rng.shuffle(pool)
    kept, done = [], 0
    for rec in pool:
        info = compute(rec, rdlp, profile, packages, cache)
        done += 1
        if info.get("forest"):
            kept.append({**rec, **info})
        if done % 50 == 0:
            WFS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            WFS_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        if len(kept) >= quota:
            break
    WFS_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return kept


# ---- analiza -----------------------------------------------------------------------------------------------------
def prepare(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["observer_id"] = [observer_of(r) for r in records]
    real = ~df["observer_id"].str.startswith("anon_")
    kept = df[real].drop_duplicates(["observer_id", "main_stand", "year"])
    return pd.concat([kept, df[~real]]).reset_index(drop=True)


def auc_stat(d: pd.DataFrame) -> float:
    return vs.auc(d.loc[d["pos"], "h"].to_numpy(), d.loc[~d["pos"], "h"].to_numpy())


def analyse(pos: pd.DataFrame, bg: pd.DataFrame) -> dict:
    both = pd.concat([pos.assign(pos=True), bg.assign(pos=False)], ignore_index=True)
    a = auc_stat(both)
    lo, hi = vs.cluster_bootstrap(auc_stat, both, "observer_id")
    return {"auc": a, "ci95": [lo, hi], "n_pos": len(pos), "n_tlo": len(bg),
            "obserwatorow_pos": int(pos["observer_id"].nunique())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    profile = load_profile("profiles/boletus_edulis.yaml")
    rdlp = fetch_rdlp_boundaries_cached(pathlib.Path("cache"))
    packages = load_packages(pathlib.Path("BDL"))
    cache = load_cache()

    pos_raw = positives()
    print(f"Pozytywy: {len(pos_raw)}", flush=True)
    pos = [{**r, **compute(r, rdlp, profile, packages, cache)} for r in pos_raw]
    WFS_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    pos_forest = [r for r in pos if r.get("forest")]
    quota = BG_FACTOR * len(pos_forest)
    print(f"Pozytywy w lesie D-STAN: {len(pos_forest)}; limit tla: {quota}", flush=True)

    print("Tlo (a): inne grzyby", flush=True)
    bg_a = fill(fungi_pool(), quota, rdlp, profile, packages, cache, rng)
    print("Tlo (b): rosliny + zwierzeta, VII-XI", flush=True)
    half = quota // 2
    cand_plants = nonfungal_pool(gb.PLANTAE_TAXON_KEY, rng, n_pages=N_PAGES_B)
    cand_animals = nonfungal_pool(gb.ANIMALIA_TAXON_KEY, rng, n_pages=N_PAGES_B)
    bg_b = (fill(cand_plants, half, rdlp, profile, packages, cache, rng)
            + fill(cand_animals, quota - half, rdlp, profile, packages, cache, rng))

    pos_df, a_df, b_df = prepare(pos_forest), prepare(bg_a), prepare(bg_b)
    for name, d in (("pozytywy", pos_df), ("tlo_a", a_df), ("tlo_b", b_df)):
        d.to_csv(OUT / f"2_4_zbior_{name}.csv", index=False)  # zamrozenie przed liczeniem AUC

    unknown_share = float(pos_df["unknown"].mean()) if len(pos_df) else 0.0
    skip_unknown = unknown_share > UNKNOWN_LIMIT
    if skip_unknown:
        pos_df, a_df, b_df = (d[~d["unknown"]] for d in (pos_df, a_df, b_df))
    summary = {
        "pozytywy_wszystkie_rekordy": len(pos_raw), "pozytywy_w_lesie_dstan": len(pos_forest),
        "po_deduplikacji": int(len(prepare(pos_forest))),
        "odsetek_nieznany_kod": unknown_share, "pominieto_nieznany_kod": bool(skip_unknown),
        "w_wydzieleniach_niespelniajacych_maski_H0": int(pos_df["masked"].sum()),
    }
    for label, min_year in (("glowna_od_2021", MAIN_FROM_YEAR), ("wariant_wszystkie_lata", 0)):
        p, a, b = (d[d["year"] >= min_year] for d in (pos_df, a_df, b_df))
        enough = len(p) >= MIN_POS and p["observer_id"].nunique() >= MIN_OBSERVERS
        res = {"tlo_a": analyse(p, a), "tlo_b": analyse(p, b)}
        res["wynik"] = (vs.verdict({k: tuple(v["ci95"]) for k, v in res.items()}) if enough
                        else "brak wniosku (za mala proba)")
        summary[label] = res

    # wariant z paczkami BDL, tylko RDLP Katowice, opisowo
    kat = {n: d[d["katowice"] & d["h_pkg"].notna()] for n, d in (("pos", pos_df), ("a", a_df), ("b", b_df))}
    summary["katowice_paczki_opisowo"] = {
        "n_pos": len(kat["pos"]),
        "auc_wfs_a": vs.auc(kat["pos"]["h"], kat["a"]["h"]), "auc_paczki_a": vs.auc(kat["pos"]["h_pkg"], kat["a"]["h_pkg"]),
        "auc_wfs_b": vs.auc(kat["pos"]["h"], kat["b"]["h"]), "auc_paczki_b": vs.auc(kat["pos"]["h_pkg"], kat["b"]["h_pkg"]),
        "n_tlo_a": len(kat["a"]), "n_tlo_b": len(kat["b"]),
    }
    (OUT / "2_4_wynik.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
