"""Faza 2 — analiza EKSPLORACYJNA wieku (nie wchodzi do decyzji wg docs/WALIDACJA_REGULY.md).

(a) Rozklad wieku wydzielen (po przeliczeniu na 2026) dla pozytywow 2.4 i obu tel, na tych samych
    zamrozonych rekordach (od 2021 r.), atrybuty z .cache/gbif_inventory/stand_attrs.json
    (patrz notebooks/14_eksploracja_h.py). Osobno sosna i swierk jako panujacy, gdy w klasie >= 20 rekordow.
(b) Przelacznik habitat.age_mode = neutral: AUC(H) na zamrozonych danych oraz, offline, wplyw na R
    i rejony w przebiegu Kieleczki (docs/porownania/faza1_6) wzgledem trybu curve.

Run: .venv/Scripts/python.exe notebooks/15_eksploracja_wiek.py
"""
import copy
import importlib.util
import json
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pipeline.age_update import update_age
from pipeline.habitat import load_profile
from pipeline.regions import group_into_regions
from pipeline.spatial_check import ANALYSIS_YEAR

spec = importlib.util.spec_from_file_location("expl14", "notebooks/14_eksploracja_h.py")
e14 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e14)

OUT = pathlib.Path("notebooks/output/walidacja")
KIELECZKA = pathlib.Path("docs/porownania/faza1_6")
EDGES = [-np.inf, 12, 20, 40, 60, 80, 100, 120.0001, np.inf]
LABELS = ["<12", "12-20", "20-40", "40-60", "60-80", "80-100", "100-120", ">120"]
MIN_CLASS_N = 20


def record_age(stands: list[dict]) -> tuple[float | None, str | None]:
    """Wiek wazony powierzchnia (po przeliczeniu na 2026) i gatunek panujacy najwiekszego wydzielenia."""
    total = sum(s["area"] for s in stands)
    if not stands or total <= 0:
        return None, None
    age = 0.0
    for s in stands:
        a, _ = update_age(s["spec_age"], s["a_year"], ANALYSIS_YEAR, True)
        age += s["area"] / total * (a if a is not None else 0.0)
    return age, max(stands, key=lambda s: s["area"])["species_cd"]


def age_distribution(sets: dict, cache: dict) -> dict:
    out = {}
    for name, d in sets.items():
        rows = []
        for _, r in d.iterrows():
            age, sp = record_age(cache[str(r["key"])])
            if age is not None:
                rows.append({"age": age, "species": sp})
        f = pd.DataFrame(rows)
        f["klasa"] = pd.cut(f["age"], EDGES, labels=LABELS, right=False)
        block = {"n": len(f), "mediana": float(f["age"].median()),
                 "q1": float(f["age"].quantile(0.25)), "q3": float(f["age"].quantile(0.75)),
                 "klasy": {}}
        for lab in LABELS:
            sub = f[f["klasa"] == lab]
            entry = {"n": len(sub), "udzial_proc": round(100 * len(sub) / len(f), 1)}
            for sp in ("SO", "SW"):
                n_sp = int((sub["species"] == sp).sum())
                entry[sp] = n_sp if n_sp >= MIN_CLASS_N else f"<{MIN_CLASS_N} (n={n_sp})"
            block["klasy"][lab] = entry
        for sp in ("SO", "SW"):
            sub = f[f["species"] == sp]
            block[f"{sp}_n"] = len(sub)
            if len(sub) >= MIN_CLASS_N:
                block[f"{sp}_mediana_q1_q3"] = [float(sub["age"].median()), float(sub["age"].quantile(0.25)),
                                                float(sub["age"].quantile(0.75))]
        out[name] = block
    return out


def neutral_auc(sets: dict, cache: dict, profile: dict) -> dict:
    neutral = copy.deepcopy(profile)
    neutral["habitat"] = {"age_mode": "neutral"}
    frames = {}
    for name, d in sets.items():
        rows = []
        for _, r in d.iterrows():
            m = e14.record_metrics(cache[str(r["key"])], neutral)
            if m is not None:
                rows.append({"h": m["h"], "observer_id": r["observer_id"]})
        frames[name] = pd.DataFrame(rows)
    return {bg: e14.auc_ci(frames["pozytywy"], frames[bg], "h") for bg in ("tlo_a", "tlo_b")}


def kieleczka(profile: dict) -> dict:
    """R (curve = odtworzone i porownane z eksportem; neutral = S_age = 1) i rejony, offline."""
    diag = pd.read_parquet(KIELECZKA / "diagnostics_2026-09-28.parquet")
    scores = pd.DataFrame(json.loads((KIELECZKA / "scores_2026-09-28.json").read_text(encoding="utf-8")))
    df = diag.merge(scores[["stand_id", "R", "tie_break", "area_ha"]], on="stand_id", how="inner")
    w, alpha = profile["weights"], profile["pressure"]["alpha_default"]
    mask = df["mask"].astype(bool) & df["S_age"].notna()
    df["R_curve"] = np.where(mask, 100 * df["H"] * df["F_loc"] * (1 - alpha * df["P"]), 0.0)
    h_neutral = (df["S_host"] ** w["host"]) * (df["S_site"] ** w["site"])  # S_age = 1
    df["R_neutral"] = np.where(mask, 100 * h_neutral * df["F_loc"] * (1 - alpha * df["P"]), 0.0)
    res = {"stands": len(df), "w_masce": int(mask.sum()),
           "kontrola_R_curve_vs_eksport_maks_roznica": float((df["R_curve"] - df["R"]).abs().max()),
           "H_mediana_curve_neutral": [float(df.loc[mask, "H"].median()), float(h_neutral[mask].median())]}
    m = df[mask]
    res["spearman_R_w_masce"] = float(spearmanr(m["R_curve"], m["R_neutral"]).statistic)

    def top(col, big=False):
        d = df[df["area_ha"] >= 0.5] if big else df
        return set(d.sort_values(col, ascending=False).head(20)["stand_id"])
    res["top20_wspolnych_wszystkie"] = len(top("R_curve") & top("R_neutral"))
    res["top20_wspolnych_ge_0_5_ha"] = len(top("R_curve", True) & top("R_neutral", True))

    geo = gpd.read_parquet(KIELECZKA / "stands_mvp.parquet")
    geo = geo.merge(df[["stand_id", "R_curve", "R_neutral", "tie_break", "mask"]], on="stand_id", how="inner")
    if geo.crs is None or geo.crs.to_epsg() != 2180:
        geo = geo.to_crs(2180)
    regions = {}
    for label, col in (("curve", "R_curve"), ("neutral", "R_neutral")):
        g = geo.copy()
        g["R_final"] = g[col]
        g["mask_full"] = g["mask"].astype(bool)
        regions[label] = group_into_regions(g, profile)
    saved = json.loads((KIELECZKA / "regions_2026-09-28.json").read_text(encoding="utf-8"))
    saved_ids = [set(r["stand_ids"]) for r in saved]
    res["rejony_zapisane_liczba"] = len(saved)
    res["rejony_curve_odtworzone_liczba"] = len(regions["curve"])
    res["rejony_curve_wspolne_wydzielenia_z_zapisanymi"] = [
        len(set(regions["curve"].iloc[i]["stand_ids"]) & saved_ids[i]) if i < len(saved_ids) else None
        for i in range(len(regions["curve"]))]
    curve_sets = [set(x) for x in regions["curve"]["stand_ids"]]
    neutral_sets = [set(x) for x in regions["neutral"]["stand_ids"]]
    res["rejony_neutral_liczba"] = len(neutral_sets)
    res["rejony_wspolne_wydzielenia_curve_vs_neutral"] = [
        max((len(c & n) for n in neutral_sets), default=0) for c in curve_sets]
    res["rejony_curve_rozmiary"] = [len(c) for c in curve_sets]
    res["rejony_neutral_rozmiary"] = [len(n) for n in neutral_sets]
    res["rejony_wspolne_wydzielenia_lacznie"] = len(set().union(*curve_sets) & set().union(*neutral_sets))
    res["rejony_wydzielen_curve_lacznie"] = len(set().union(*curve_sets))
    return res


def main() -> None:
    profile = load_profile("profiles/boletus_edulis.yaml")
    sets = e14.load_sets()
    cache = json.loads(e14.ATTRS.read_text(encoding="utf-8"))
    result = {
        "a_rozklad_wieku": age_distribution(sets, cache),
        "b_auc_H_neutral": neutral_auc(sets, cache, profile),
        "b_kieleczka_offline": kieleczka(profile),
    }
    (OUT / "eksploracja_wiek.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
