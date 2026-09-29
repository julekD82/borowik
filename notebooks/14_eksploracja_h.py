"""Faza 2 — analiza EKSPLORACYJNA (nie wchodzi do decyzji wg docs/WALIDACJA_REGULY.md).

Na tych samych, ZAMROZONYCH rekordach i tlach co analiza glowna 2.4 (pliki
notebooks/output/walidacja/2_4_zbior_*.csv, rok >= 2021, bez pomijania nieznanych kodow)
liczy AUC osobno dla skladowych H (S_host, S_site, S_age) i prostych wskaznikow
(udzial sosny+swierka, binarnie panujacy SO/SW, sam wiek), oraz liste kodow
nieznanych profilowi. Atrybuty wydzielen odtwarzane z BDL WFS (male zapytania per
rekord, cache .cache/gbif_inventory/stand_attrs.json) -- zbiory nie zawieraly atrybutow.
Sanity check: H odtworzone z atrybutow musi zgadzac sie z H w zamrozonym CSV.

Run: .venv/Scripts/python.exe notebooks/14_eksploracja_h.py
"""
import json
import pathlib
import time
from collections import Counter

import numpy as np
import pandas as pd
from shapely.geometry import Point

from pipeline import validation_stats as vs
from pipeline.age_update import update_age
from pipeline.bdl import fetch_bdl
from pipeline.habitat import compute_habitat, load_profile, passes_mask, score_age, score_host, score_site
from pipeline.rdlp import fetch_rdlp_boundaries_cached, resolve_rdlp_layer
from pipeline.spatial_check import ANALYSIS_YEAR, MIN_BUFFER_M
from pipeline.tiles import _TO_2180

OUT = pathlib.Path("notebooks/output/walidacja")
ATTRS = pathlib.Path(".cache/gbif_inventory/stand_attrs.json")
FROM_YEAR = 2021
PINE_SPRUCE = {"SO", "SW"}
FIELDS = ["adr_for", "area_type", "spec_age", "a_year", "species_cd", "part_cd", "site_type"]


def load_sets() -> dict[str, pd.DataFrame]:
    sets = {n: pd.read_csv(OUT / f"2_4_zbior_{n}.csv") for n in ("pozytywy", "tlo_a", "tlo_b")}
    return {n: d[d["year"] >= FROM_YEAR].reset_index(drop=True) for n, d in sets.items()}


def fetch_attrs(df: pd.DataFrame, rdlp, cache: dict) -> None:
    for i, r in df.iterrows():
        key = str(r["key"])
        if key in cache:
            continue
        layer = resolve_rdlp_layer(r["lat"], r["lon"], rdlp)
        e, n = _TO_2180.transform(r["lon"], r["lat"])
        rad = max(float(r["unc"] or 0), MIN_BUFFER_M)
        stands = fetch_bdl(layer, (n - rad - 5, e - rad - 5, n + rad + 5, e + rad + 5))
        buf = Point(e, n).buffer(rad)
        rows = []
        for _, s in stands.iterrows():
            if s.get("area_type") != "D-STAN":
                continue
            area = s.geometry.intersection(buf).area
            if area > 0:
                rows.append({"area": area, **{f: (None if pd.isna(s.get(f)) else s.get(f)) for f in FIELDS}})
        cache[key] = rows
        time.sleep(0.1)
        if len(cache) % 100 == 0:
            ATTRS.write_text(json.dumps(cache, default=str), encoding="utf-8")
            print(f"  WFS {len(cache)}", flush=True)
    ATTRS.write_text(json.dumps(cache, default=str), encoding="utf-8")


def record_metrics(stands: list[dict], profile: dict) -> dict | None:
    """Skladowe wazone powierzchnia (maska -> 0, jak H); None gdy brak lasu."""
    total = sum(s["area"] for s in stands)
    if not stands or total <= 0:
        return None
    acc = dict.fromkeys(["h", "s_host", "s_site", "s_age", "pine_spruce_share", "pine_spruce_dom", "age"], 0.0)
    unknown = []
    for s in stands:
        w = s["area"] / total
        row = {k: (None if s[k] is None else s[k]) for k in FIELDS}
        age, _ = update_age(row["spec_age"], row["a_year"], ANALYSIS_YEAR, True)
        row["spec_age"] = age
        acc["age"] += w * (age if age is not None else 0.0)
        if not passes_mask(row, profile):
            continue  # skladowe = 0 dla wydzielen poza maska
        part = row["part_cd"] if row["part_cd"] is not None else 10
        acc["s_host"] += w * score_host(row["species_cd"], part, profile)
        acc["s_site"] += w * score_site(row["site_type"], profile)[0]
        s_age = score_age(age, profile)
        acc["s_age"] += w * (s_age or 0.0)
        h = compute_habitat(row, profile)
        acc["h"] += w * (h or 0.0)
        is_ps = row["species_cd"] in PINE_SPRUCE
        acc["pine_spruce_dom"] += w * (1.0 if is_ps else 0.0)
        acc["pine_spruce_share"] += w * ((float(part) / 10.0) if is_ps else 0.0)
        if row["site_type"] not in profile["site_scores"]:
            unknown.append(("siedlisko", row["site_type"]))
        if row["species_cd"] not in profile["host_affinity"]:
            unknown.append(("gatunek", row["species_cd"]))
    acc["unknown"] = unknown
    return acc


def auc_ci(pos: pd.DataFrame, bg: pd.DataFrame, col: str) -> dict:
    both = pd.concat([pos.assign(pos=True), bg.assign(pos=False)], ignore_index=True)

    def stat(d):
        return vs.auc(d.loc[d["pos"], col].to_numpy(), d.loc[~d["pos"], col].to_numpy())
    lo, hi = vs.cluster_bootstrap(stat, both, "observer_id", n_boot=1000)
    return {"auc": stat(both), "ci95": [lo, hi]}


def main() -> None:
    profile = load_profile("profiles/boletus_edulis.yaml")
    rdlp = fetch_rdlp_boundaries_cached(pathlib.Path("cache"))
    sets = load_sets()
    cache = json.loads(ATTRS.read_text(encoding="utf-8")) if ATTRS.exists() else {}
    for name, d in sets.items():
        print(f"{name}: {len(d)} rekordow", flush=True)
        fetch_attrs(d, rdlp, cache)

    frames, unknown_counts, unknown_records = {}, {}, {}
    max_h_diff = 0.0
    for name, d in sets.items():
        rows, unk_rec = [], Counter()
        unk_stands = Counter()
        for _, r in d.iterrows():
            m = record_metrics(cache[str(r["key"])], profile)
            if m is None:
                continue
            max_h_diff = max(max_h_diff, abs(m["h"] - r["h"]))
            for kind, code in set(m["unknown"]):
                unk_rec[(kind, code)] += 1
            rows.append({**{k: v for k, v in m.items() if k != "unknown"}, "observer_id": r["observer_id"]})
        frames[name] = pd.DataFrame(rows)
        unknown_counts[name] = unk_rec
    result = {"kontrola_H_maks_roznica_do_zamrozonego": max_h_diff,
              "liczebnosc": {n: len(f) for n, f in frames.items()}, "auc": {}, "nieznane_kody": {}}
    for col in ("h", "s_host", "s_site", "s_age", "pine_spruce_share", "pine_spruce_dom", "age"):
        result["auc"][col] = {bg: auc_ci(frames["pozytywy"], frames[bg], col) for bg in ("tlo_a", "tlo_b")}
    for name, c in unknown_counts.items():
        result["nieznane_kody"][name] = [{"rodzaj": k[0], "kod": k[1], "rekordow": n} for k, n in c.most_common()]
    (OUT / "eksploracja_H.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
