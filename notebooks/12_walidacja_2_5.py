"""Faza 2.5: kontrola czasowa F na rekordach GBIF (E-OBS), wg docs/WALIDACJA_REGULY.md
i docs/WALIDACJA_IMPLEMENTACJA.md. JEDEN przebieg analizy glownej; wszystko dodane po
zobaczeniu wynikow ma byc oznaczone jako eksploracyjne (w raporcie, nie tutaj).

Bez dostrajania parametrow F. Zbior rekordow zamrazany do CSV przed liczeniem F.
Run: .venv/Scripts/python.exe notebooks/12_walidacja_2_5.py
"""
import json
import math
import pathlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline import gbif_client as gb
from pipeline import validation_stats as vs
from pipeline.eobs import EobsStore
from pipeline.eobs_fruiting import VARIANTS, CellClimate, variant_scores
from pipeline.habitat import load_profile

OUT = pathlib.Path("notebooks/output/walidacja")
MIN_RECORDS, MIN_YEARS = 150, 5
WINDOW = 15
FUNGI_RADIUS_KM = 20.0
MIN_FUNGI_DAYS = 3
MAX_YEAR = 2025  # E-OBS v33.0e konczy sie 2025-12-31
MIN_YEAR = 1992  # klimatologia 1991-2020 + 26 dni wstecz


def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def load_records() -> tuple[pd.DataFrame, dict]:
    raw = [gb.slim(r) for r in gb.fetch_all({**gb.BASE, **gb.BOLETUS})]
    stats = {"gbif_rekordow": len(raw)}
    df = pd.DataFrame(raw)
    df = df[df["date"].notna() & (df["date"].str.len() >= 10) & ~df["date"].str.contains("/", na=False)]
    stats["z_pelna_data"] = len(df)
    df = df[df["unc"].notna() & (df["unc"] <= 1000)]
    stats["niepewnosc_le_1000"] = len(df)
    df = df.assign(day=df["date"].str[:10])
    stats["rok_2026_wykluczone"] = int((df["year"] > MAX_YEAR).sum())
    df = df[(df["year"] <= MAX_YEAR) & (df["year"] >= MIN_YEAR)].copy()
    stats["w_zakresie_eobs"] = len(df)
    return df.reset_index(drop=True), stats


def dedupe_1km(df: pd.DataFrame) -> pd.DataFrame:
    """Ten sam obserwator + ten sam dzien + do 1 km = jeden rekord (rekordy bez obserwatora zostaja)."""
    keep = []
    seen: dict[tuple, list[tuple[float, float]]] = {}
    for i, r in df.iterrows():
        obs = r["observer"]
        if obs is None or (isinstance(obs, float) and math.isnan(obs)) or not str(obs).strip():
            keep.append(i)
            continue
        pts = seen.setdefault((str(obs).strip(), r["day"]), [])
        if any(haversine_km(r["lat"], r["lon"], la, lo) <= 1.0 for la, lo in pts):
            continue
        pts.append((r["lat"], r["lon"]))
        keep.append(i)
    return df.loc[keep].reset_index(drop=True)


def other_fungi_days(lat: float, lon: float, day: date) -> set[str]:
    params = {**gb.BASE, "geometry": gb.circle_wkt(lat, lon, FUNGI_RADIUS_KM),
              "eventDate": f"{day - timedelta(days=WINDOW)},{day + timedelta(days=WINDOW)}",
              "coordinateUncertaintyInMeters": "0,1000"}
    fungi = gb.facet_dates({**params, "taxonKey": gb.FUNGI_TAXON_KEY})
    edulis = gb.facet_dates({**params, **gb.BOLETUS})
    return {d for d, n in fungi.items() if n - edulis.get(d, 0) > 0}


def ci(values, df, col):
    lo_y, hi_y = vs.cluster_bootstrap_mean(values, df["year"])
    lo_c, hi_c = vs.cluster_bootstrap_mean(values, df[col])
    return vs.union_ci([(lo_y, hi_y), (lo_c, hi_c)])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    profile = load_profile("profiles/boletus_edulis.yaml")
    df, stats = load_records()
    df = dedupe_1km(df)
    stats["po_deduplikacji"] = len(df)
    df["cell"] = [f"{round(la * 10 - 0.5) / 10 + 0.05:.2f}_{round(lo * 10 - 0.5) / 10 + 0.05:.2f}"
                  for la, lo in zip(df["lat"], df["lon"])]
    df.to_csv(OUT / "2_5_zbior_zamrozony.csv", index=False)  # ZAMROZENIE przed liczeniem F

    store, climates = EobsStore("cache"), {}
    rows, no_weather = [], 0
    for i, r in df.iterrows():
        d0 = date.fromisoformat(r["day"])
        cell = r["cell"]
        if cell not in climates:
            climates[cell] = CellClimate(store, r["lat"], r["lon"])
        cc = climates[cell]
        days = [d0 + timedelta(days=k) for k in range(-WINDOW, WINDOW + 1)]
        scores = {}
        for d in days:
            ts = pd.Timestamp(d)
            if ts not in cc.features.index:
                continue
            feat = cc.features.loc[ts]
            if feat.isna().any():
                continue
            doy = ts.dayofyear
            scores[d.isoformat()] = variant_scores(feat, doy, cc.climatology(doy), profile)
        if r["day"] not in scores or len(scores) < 10:
            no_weather += 1
            continue
        find = scores[r["day"]]
        controls = {k: v for k, v in scores.items() if k != r["day"]}
        rec = {"key": r["key"], "day": r["day"], "year": r["year"], "cell": cell, "observer": r["observer"],
               "n_controls_a": len(controls)}
        for v in VARIANTS:
            rec[f"a_{v}"] = vs.rank_of(find[v], np.array([c[v] for c in controls.values()]))
        fungi_days = other_fungi_days(r["lat"], r["lon"], d0) - {r["day"]}
        ctrl_b = {k: v for k, v in controls.items() if k in fungi_days}
        rec["n_controls_b"] = len(ctrl_b)
        for v in VARIANTS:
            rec[f"b_{v}"] = (vs.rank_of(find[v], np.array([c[v] for c in ctrl_b.values()]))
                             if len(ctrl_b) >= MIN_FUNGI_DAYS else np.nan)
        rows.append(rec)
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(df)}", flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "2_5_rangi.csv", index=False)
    stats["bez_pogody_lub_okna"] = no_weather
    n_a, years = len(res), int(res["year"].nunique())
    sub_b = res[res["n_controls_b"] >= MIN_FUNGI_DAYS]
    stats.update({"N_tlo_a": n_a, "lat_tlo_a": years, "N_tlo_b": len(sub_b),
                  "pominiete_w_tle_b": n_a - len(sub_b)})

    summary = {"liczebnosc": stats, "warianty": {}}
    for v in VARIANTS:
        summary["warianty"][v] = {}
        for bg, frame in (("a", res), ("b", sub_b)):
            vals = frame[f"{bg}_{v}"].to_numpy()
            summary["warianty"][v][bg] = {
                "srednia_ranga": float(vals.mean()), "ci95": ci(vals, frame, "cell"), "n": len(frame)}
    diff = {}
    for bg, frame in (("a", res), ("b", sub_b)):
        d = (frame[f"{bg}_F_bez_G_season"] - frame[f"{bg}_sam_kalendarz"]).to_numpy()
        diff[bg] = {"srednia_roznica": float(d.mean()), "ci95": ci(d, frame, "cell")}
    summary["roznica_F_bez_G_minus_kalendarz"] = diff

    enough = n_a >= MIN_RECORDS and years >= MIN_YEARS
    main_cis = {bg: tuple(summary["warianty"]["F_bez_G_season"][bg]["ci95"]) for bg in ("a", "b")}
    summary["wynik_glowny"] = vs.verdict(main_cis) if enough else "brak wniosku (za mala proba)"
    summary["dodatkowa_czerwona_flaga"] = bool(all(diff[bg]["ci95"][1] < 0 for bg in ("a", "b")))
    (OUT / "2_5_wynik.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
