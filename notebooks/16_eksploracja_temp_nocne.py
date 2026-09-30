"""EKSPLORACYJNIE (nie decyzyjnie): czy nocne temperatury niosa informacje o dniach z rekordami B. edulis
ponad to, co juz jest w F? Bez sieci: zamrozony zbior GBIF z 2.5 (notebooks/output/walidacja/2_5_zbior_zamrozony.csv)
i lokalny E-OBS. Bez dostrajania parametrow F; jedyny wariant "F z nocami" ma parametry ustawione z gory
(z odrzuconego modelu fali: zimna noc < 5 C, wspolczynnik 0,5) i nie jest optymalizowany.

Schemat jak w 2.5 (tlo a): ranga dnia z rekordem wsrod dni +-15 d w tej samej komorce i roku; 0,5 = brak
informacji, > 0,5 = wyzsza wartosc cechy w dniu znaleziska niz w dniach kontrolnych.
Druga czesc: wrazliwosc na prawdziwych dniach sezonu (15.08-10.11, 1992-2025) w komorce Kieleczki --
ile dni zmienia klase F i jak zmienia sie ranking dni w sezonie, gdyby F uwzglednial zimne noce.

Run: .venv/Scripts/python.exe notebooks/16_eksploracja_temp_nocne.py
"""
import json
import pathlib
from datetime import date, timedelta

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from pipeline import validation_stats as vs
from pipeline.eobs import EobsStore
from pipeline.eobs_fruiting import CellClimate, variant_scores
from pipeline.habitat import load_profile

OUT = pathlib.Path("notebooks/output/walidacja")
WINDOW = 15
COLD_NIGHT_C = 5.0          # z odrzuconego modelu fali (profil flush.cold_night_c)
COLD_NIGHT_FACTOR = 0.5     # j.w. (flush.cold_night_factor)
CLASS_EDGES = (0.2, 0.45, 0.7)   # fruiting_classes z profilu


def night_features(daily: pd.DataFrame) -> pd.DataFrame:
    tn = daily["tn"].to_numpy(float)
    tx = daily["tx"].to_numpy(float)
    n = len(daily)

    def win(arr, size, fn):
        out = np.full(n, np.nan)
        out[size - 1:] = fn(sliding_window_view(arr, size))
        return out

    tn_mean3 = win(tn, 3, lambda v: v.mean(axis=1))
    tn_mean7 = win(tn, 7, lambda v: v.mean(axis=1))
    tn_mean14 = win(tn, 14, lambda v: v.mean(axis=1))
    cold7 = win(tn, 7, lambda v: (v < COLD_NIGHT_C).mean(axis=1))          # udzial zimnych nocy (<5 C) w 7 dobach
    cold7_8 = win(tn, 7, lambda v: (v < 8.0).mean(axis=1))
    older = pd.Series(tn_mean7).shift(3).to_numpy()                        # srednia TN z dni d-9..d-3
    change = tn_mean3 - older                                              # < 0 = ochlodzenie nocy
    dtr7 = win(tx - tn, 7, lambda v: v.mean(axis=1))
    return pd.DataFrame({
        "tn_mean3": tn_mean3, "tn_mean7": tn_mean7, "tn_mean14": tn_mean14, "cold_share7": cold7,
        "cool_share7_lt8": cold7_8, "tn_cooling": change, "dtr7": dtr7,
    }, index=daily.index)


def klass(value: float) -> int:
    return int(np.searchsorted(CLASS_EDGES, value, side="right"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    profile = load_profile("profiles/boletus_edulis.yaml")
    df = pd.read_csv("notebooks/output/walidacja/2_5_zbior_zamrozony.csv")
    store, climates, nights = EobsStore("cache"), {}, {}
    feats = ["tn_mean3", "tn_mean7", "tn_mean14", "cold_share7", "cool_share7_lt8", "tn_cooling", "dtr7"]
    rows = []
    for _, r in df.iterrows():
        cell = r["cell"]
        if cell not in climates:
            climates[cell] = CellClimate(store, r["lat"], r["lon"])
            nights[cell] = night_features(store.daily(*store.cell(r["lat"], r["lon"]), date(1990, 12, 1), date(2025, 12, 31)))
        cc, nf = climates[cell], nights[cell]
        d0 = date.fromisoformat(r["day"])
        vals = {}
        for k in range(-WINDOW, WINDOW + 1):
            ts = pd.Timestamp(d0 + timedelta(days=k))
            if ts not in cc.features.index or cc.features.loc[ts].isna().any() or nf.loc[ts].isna().any():
                continue
            f = variant_scores(cc.features.loc[ts], ts.dayofyear, cc.climatology(ts.dayofyear), profile)["F_bez_G_season"]
            share = float(nf.loc[ts, "cold_share7"])
            vals[ts] = {"F": f, "F_noc": f * (1.0 - (1.0 - COLD_NIGHT_FACTOR) * share), **nf.loc[ts].to_dict()}
        ts0 = pd.Timestamp(d0)
        if ts0 not in vals or len(vals) < 10:
            continue
        find = vals[ts0]
        ctrl = [v for t, v in vals.items() if t != ts0]
        rec = {"year": int(r["year"]), "cell": cell, "month": int(r["month"])}
        for name in ["F", "F_noc"] + feats:
            rec[name] = vs.rank_of(find[name], np.array([c[name] for c in ctrl]))
        rows.append(rec)
    res = pd.DataFrame(rows)

    def summarize(frame: pd.DataFrame) -> dict:
        out = {"n": len(frame), "lat": int(frame["year"].nunique())}
        for name in ["F", "F_noc"] + feats:
            v = frame[name].to_numpy()
            lo_y, hi_y = vs.cluster_bootstrap_mean(v, frame["year"])
            lo_c, hi_c = vs.cluster_bootstrap_mean(v, frame["cell"])
            out[name] = {"srednia_ranga": round(float(v.mean()), 3), "ci95": [round(min(lo_y, lo_c), 3), round(max(hi_y, hi_c), 3)]}
        d = (frame["F_noc"] - frame["F"]).to_numpy()
        lo_y, hi_y = vs.cluster_bootstrap_mean(d, frame["year"])
        lo_c, hi_c = vs.cluster_bootstrap_mean(d, frame["cell"])
        out["F_noc_minus_F"] = {"srednia": round(float(d.mean()), 4), "ci95": [round(min(lo_y, lo_c), 4), round(max(hi_y, hi_c), 4)]}
        return out

    result = {"wszystkie_miesiace": summarize(res), "sezon_VIII_XI": summarize(res[res["month"].between(8, 11)])}

    # --- wrazliwosc na dniach sezonu w komorce Kieleczki ---
    lat, lon = 50.527, 18.605
    cc = CellClimate(store, lat, lon)
    nf = night_features(store.daily(*store.cell(lat, lon), date(1990, 12, 1), date(2025, 12, 31)))
    recs = []
    for ts in cc.features.index:
        if not (1992 <= ts.year <= 2025) or not ((ts.month, ts.day) >= (8, 15) and (ts.month, ts.day) <= (11, 10)):
            continue
        if cc.features.loc[ts].isna().any() or nf.loc[ts].isna().any():
            continue
        f = variant_scores(cc.features.loc[ts], ts.dayofyear, cc.climatology(ts.dayofyear), profile)["F_bez_G_season"]
        share = float(nf.loc[ts, "cold_share7"])
        recs.append({"ts": ts, "year": ts.year, "F": f, "F_noc": f * (1.0 - (1.0 - COLD_NIGHT_FACTOR) * share),
                     "cold_share7": share, "tn_mean7": float(nf.loc[ts, "tn_mean7"]), "tn_mean7_vs_tmean20": float(nf.loc[ts, "tn_mean7"])})
    s = pd.DataFrame(recs)
    s["kl"] = s["F"].map(klass)
    s["kl_noc"] = s["F_noc"].map(klass)
    per_year = []
    for y, g in s.groupby("year"):
        if len(g) < 40:
            continue
        top = max(3, int(round(0.2 * len(g))))
        a = set(g.nlargest(top, "F").index)
        b = set(g.nlargest(top, "F_noc").index)
        per_year.append({"rho": float(g["F"].corr(g["F_noc"], method="spearman")), "top20_wspolne": len(a & b) / top})
    py = pd.DataFrame(per_year)
    tmean20 = cc.features["tmean20"]
    joined = s.set_index("ts")
    result["wrazliwosc_Kieleczka"] = {
        "dni": len(s), "lat": int(s["year"].nunique()),
        "udzial_dni_ze_zmiana_klasy": round(float((s["kl"] != s["kl_noc"]).mean()), 3),
        "udzial_dni_klasy_dobre_lub_lepsze_przed": round(float((s["kl"] >= 2).mean()), 3),
        "udzial_dni_klasy_dobre_lub_lepsze_po": round(float((s["kl_noc"] >= 2).mean()), 3),
        "srednia_F": round(float(s["F"].mean()), 3), "srednia_F_noc": round(float(s["F_noc"].mean()), 3),
        "mediana_udzialu_zimnych_nocy_7d": round(float(s["cold_share7"].median()), 3),
        "korelacja_tn_mean7_z_tmean20": round(float(pd.Series(joined["tn_mean7"]).corr(tmean20.reindex(joined.index))), 3),
        "ranking_dni_w_roku_spearman_mediana": round(float(py["rho"].median()), 3),
        "ranking_dni_w_roku_spearman_min": round(float(py["rho"].min()), 3),
        "top20_proc_dni_wspolne_mediana": round(float(py["top20_wspolne"].median()), 3),
    }
    (OUT / "16_temp_nocne.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
