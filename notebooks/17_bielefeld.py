"""Plan 2.8, etap 3 -- analiza danych z Bielefeld wg ZATWIERDZONYCH regul docs/WALIDACJA_BIELEFELD.md
(commit b33412e, przed analiza). JEDEN przebieg analizy glownej; wszystko inne w wyniku jest oznaczone jako
opisowe/eksploracyjne. Model produkcyjny bez zmian.

A. Wagi opadu w czasie: K1 (regula wlasciciela) vs K0 (obecne), K2/K3 opisowo.
   (a) wzor aplikacji (F bez G_season z E-OBS): ranga F dnia z owocnikami wsrod dni +-15 (1.08-30.11, ten sam rok);
   (b) NB1 na tygodniach, rok jako efekt staly, log-wiarygodnosc "zostaw jeden rok";
   warunek 3: 2.5 na zamrozonym zbiorze GBIF z K1 vs K0 w obu tlach.
   Opisowo: profil opoznienia (opad w przedzialach 0-4 ... 30-34 dni wstecz).
B. Eksploracyjnie: TX/TN/zakres dobowy ponad srednia dobowa.

Bez sieci: dane_walidacyjne/bielefeld/, cache/eobs/*_BI.npz i *_PL.npz, cache zapytan GBIF (.cache/gbif_inventory).
Run: .venv/Scripts/python.exe notebooks/17_bielefeld.py
"""
import importlib.util
import json
import pathlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline import bielefeld as bf
from pipeline import validation_stats as vs
from pipeline.eobs import EobsStore
from pipeline.eobs_fruiting import CellClimate, precip_weights, variant_scores
from pipeline.habitat import load_profile

OUT = pathlib.Path("notebooks/output/walidacja")
DATA = pathlib.Path("dane_walidacyjne/bielefeld")
WINDOW = 15
KINDS = ("K0", "K1", "K2", "K3")
MIN_DAYS, MIN_YEARS = 100, 8
LAG_BINS = [(a, a + 4) for a in range(0, 35, 5)]


def load_counts() -> pd.DataFrame:
    d = pd.read_csv(DATA / "owocniki_dzienne.csv", parse_dates=["data"])
    d = d[d["stanowisko"] == "All"].set_index("data").sort_index()
    return d[["nowe_owocniki"]].rename(columns={"nowe_owocniki": "y"})


def f_series(cc: CellClimate, days: pd.DatetimeIndex, profile: dict) -> pd.Series:
    out = {}
    for ts in days:
        feat = cc.features.loc[ts]
        if feat.isna().any():
            continue
        out[ts] = variant_scores(feat, ts.dayofyear, cc.climatology(ts.dayofyear), profile)["F_bez_G_season"]
    return pd.Series(out)


def ranks_a(F: dict[str, pd.Series], counts: pd.DataFrame) -> pd.DataFrame:
    """Ranga F dnia z owocnikami wsrod dni kontrolnych +-15 dni (ten sam rok, okres monitoringu)."""
    rows = []
    for d0, n in counts[counts["y"] > 0]["y"].items():
        ctrl = [d0 + timedelta(days=k) for k in range(-WINDOW, WINDOW + 1) if k != 0]
        ctrl = [c for c in ctrl if c in counts.index and c.year == d0.year]
        rec = {"data": d0, "rok": d0.year, "owocniki": int(n), "n_kontrolnych": len(ctrl)}
        for k, f in F.items():
            vals = f.reindex(ctrl).dropna().to_numpy()
            rec[k] = vs.rank_of(float(f[d0]), vals) if d0 in f.index and len(vals) >= 10 else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def mean_ci(values, clusters) -> dict:
    v = np.asarray(values, float)
    lo, hi = vs.cluster_bootstrap_mean(v, clusters)
    return {"srednia": round(float(v.mean()), 4), "ci95": [round(lo, 4), round(hi, 4)], "n": int(len(v))}


def model_frame(daily: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    """Dzienne predyktory dla dni monitoringu (z pelnej serii E-OBS, bez luk)."""
    tg, rr, tn, tx = daily["tg"], daily["rr"], daily["tn"], daily["tx"]
    feats = {"T20": tg.rolling(20).mean()}
    for k in KINDS:
        feats[f"P_{k}"] = bf.weighted_precip(rr, precip_weights(k))
    for a, b in LAG_BINS:
        feats[f"P_lag_{a}_{b}"] = rr.shift(a).rolling(b - a + 1).mean()
    feats["TX_mean5"] = tx.rolling(5).mean()
    feats["TX_gt20_n7"] = (tx > 20.0).astype(float).where(tx.notna()).rolling(7).sum()
    feats["TN_mean7"] = tn.rolling(7).mean()
    feats["DTR_mean7"] = (tx - tn).rolling(7).mean()
    f = pd.DataFrame(feats).reindex(counts.index)
    f["y"] = counts["y"]
    f["rok"] = f.index.year
    f["tydzien"] = bf.week_block(f.index)
    if f.drop(columns=["y"]).isna().any().any():
        raise ValueError("braki pogody w dniach monitoringu")
    return f


def design(f: pd.DataFrame, precip_cols: list[str], extra: list[str] = ()) -> np.ndarray:
    return np.column_stack([f[c] for c in precip_cols] + [f["T20"], f["T20"] ** 2] + [f[c] for c in extra])


def loyo_ll(f: pd.DataFrame, X: np.ndarray, weekly: bool = True) -> pd.Series:
    res = bf.loyo(f["y"].to_numpy(), X, f["rok"].to_numpy(), f["tydzien"].to_numpy() if weekly else None)
    if not res["converged"].all():
        print("UWAGA: brak zbieznosci w", res.loc[~res["converged"], "grupa"].tolist())
    return res.set_index("grupa")["ll"]


def check_2_5(profile: dict) -> dict:
    """Warunek 3: 2.5 na zamrozonym zbiorze, F bez G_season z K1 vs K0, oba tla (jak notebooks/12)."""
    spec = importlib.util.spec_from_file_location("nb12", "notebooks/12_walidacja_2_5.py")
    nb12 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb12)
    df = pd.read_csv(OUT / "2_5_zbior_zamrozony.csv")
    store = EobsStore("cache")
    climates: dict[tuple[str, str], CellClimate] = {}
    cache_before = len(list(pathlib.Path(".cache/gbif_inventory").glob("*.json")))
    rows = []
    for _, r in df.iterrows():
        d0 = date.fromisoformat(r["day"])
        days = [d0 + timedelta(days=k) for k in range(-WINDOW, WINDOW + 1)]
        scores = {}
        for kind in ("K0", "K1"):
            key = (r["cell"], kind)
            if key not in climates:
                climates[key] = CellClimate(store, r["lat"], r["lon"], precip_weights(kind))
            cc = climates[key]
            s = {}
            for d in days:
                ts = pd.Timestamp(d)
                if ts not in cc.features.index or cc.features.loc[ts].isna().any():
                    continue
                s[d.isoformat()] = variant_scores(cc.features.loc[ts], ts.dayofyear, cc.climatology(ts.dayofyear),
                                                  profile)["F_bez_G_season"]
            scores[kind] = s
        if any(r["day"] not in s or len(s) < 10 for s in scores.values()):
            continue
        fungi = nb12.other_fungi_days(r["lat"], r["lon"], d0) - {r["day"]}
        rec = {"key": r["key"], "year": r["year"], "cell": r["cell"]}
        for kind, s in scores.items():
            ctrl = {k: v for k, v in s.items() if k != r["day"]}
            rec[f"a_{kind}"] = vs.rank_of(s[r["day"]], np.array(list(ctrl.values())))
            ctrl_b = [v for k, v in ctrl.items() if k in fungi]
            rec[f"b_{kind}"] = vs.rank_of(s[r["day"]], np.array(ctrl_b)) if len(ctrl_b) >= nb12.MIN_FUNGI_DAYS else np.nan
        rows.append(rec)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "17_2_5_K0_K1_rangi.csv", index=False)
    out = {"nowe_zapytania_GBIF": len(list(pathlib.Path(".cache/gbif_inventory").glob("*.json"))) - cache_before}
    orig = pd.read_csv(OUT / "2_5_rangi.csv")[["key", "a_F_bez_G_season", "b_F_bez_G_season"]].merge(res, on="key")
    out["kontrola_K0_vs_oryginal_2_5"] = {
        "wspolne_rekordy": len(orig),
        "maks_roznica_rangi_a": float((orig["a_K0"] - orig["a_F_bez_G_season"]).abs().max()),
        "maks_roznica_rangi_b": float((orig["b_K0"] - orig["b_F_bez_G_season"]).abs().max())}
    for bg in ("a", "b"):
        fr = res.dropna(subset=[f"{bg}_K0", f"{bg}_K1"])
        diff = (fr[f"{bg}_K1"] - fr[f"{bg}_K0"]).to_numpy()
        lo, hi = nb12.ci(diff, fr, "cell")
        out[f"tlo_{bg}"] = {
            "n": len(fr), "srednia_ranga_K0": round(float(fr[f"{bg}_K0"].mean()), 4),
            "srednia_ranga_K1": round(float(fr[f"{bg}_K1"].mean()), 4),
            "roznica_K1_minus_K0": round(float(diff.mean()), 4), "ci95": [round(lo, 4), round(hi, 4)],
            "nie_gorsze": bool(diff.mean() >= -0.010 and lo >= -0.030)}
    out["warunek_3"] = bool(out["tlo_a"]["nie_gorsze"] and out["tlo_b"]["nie_gorsze"])
    return out


def decide(dll: float, n_better: int, ci_a: list[float], cond3: bool, enough: bool) -> str:
    """Regula decyzji z docs/WALIDACJA_BIELEFELD.md (kolejnosc: lepsze, gorsze, nie gorsze, nierozstrzygniete)."""
    if not enough:
        return "brak wniosku"
    if dll > 2 and n_better >= 6 and ci_a[0] > 0 and cond3:
        return "K1 lepsze"
    if dll < -2 or ci_a[1] < 0:
        return "K1 gorsze"
    if dll >= -2 and ci_a[0] >= -0.03 and cond3:
        return "K1 nie gorsze"
    return "nierozstrzygniete"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    profile = load_profile("profiles/boletus_edulis.yaml")
    counts = load_counts()
    store = EobsStore("cache", region="BI")
    lat, lon = bf.CENTROID
    result = {"komorka_EOBS": list(store.cell(lat, lon))}

    # --- A (a): wzor aplikacji ---
    climates = {k: CellClimate(store, lat, lon, precip_weights(k)) for k in KINDS}
    F = {k: f_series(climates[k], counts.index, profile) for k in KINDS}
    ra = ranks_a(F, counts).dropna(subset=list(KINDS))
    ra.to_csv(OUT / "17_bielefeld_rangi_a.csv", index=False)
    enough = len(ra) >= MIN_DAYS and ra["rok"].nunique() >= MIN_YEARS
    a = {"dni_z_owocnikami": len(ra), "lat": int(ra["rok"].nunique()), "min_licznosc_spelniona": bool(enough)}
    for k in KINDS:
        a[k] = mean_ci(ra[k], ra["rok"])
        a[k]["srednia_wazona_liczba_owocnikow_opisowo"] = round(float(np.average(ra[k], weights=ra["owocniki"])), 4)
    a["roznica_K1_minus_K0"] = mean_ci(ra["K1"] - ra["K0"], ra["rok"])
    for k in ("K2", "K3"):
        a[f"roznica_{k}_minus_K0_opisowo"] = mean_ci(ra[k] - ra["K0"], ra["rok"])
    result["A_a_wzor_aplikacji"] = a

    # --- A (b): NB1, tygodnie, LOYO ---
    daily = store.daily(*store.cell(lat, lon), date(1990, 12, 1), date(2025, 12, 31))
    f = model_frame(daily, counts)
    ll = {k: loyo_ll(f, design(f, [f"P_{k}"])) for k in KINDS}
    b = {"tygodnie": int(f["tydzien"].nunique()), "lata": int(f["rok"].nunique())}
    for k in KINDS:
        fit = bf.fit_nb1(f["y"], design(f, [f"P_{k}"]), f["rok"], f["tydzien"], se=True)
        b[k] = {"LL_LOYO": round(float(ll[k].sum()), 3), "LL_pelne": round(fit["loglik"], 3),
                "beta_P": round(float(fit["beta"][0]), 4), "se_P": round(float(fit["beta_se"][0]), 4),
                "optimum_T20": round(float(-fit["beta"][1] / (2 * fit["beta"][2])), 2) if fit["beta"][2] < 0 else None}
    d10 = ll["K1"] - ll["K0"]
    b["dLL_K1_minus_K0"] = round(float(d10.sum()), 3)
    b["dLL_K1_minus_K0_na_rok"] = {int(y): round(float(v), 3) for y, v in d10.items()}
    b["lat_K1_lepsze"] = int((d10 > 0).sum())
    for k in ("K2", "K3"):
        b[f"dLL_{k}_minus_K0_opisowo"] = round(float((ll[k] - ll["K0"]).sum()), 3)
    ll_day = {k: loyo_ll(f, design(f, [f"P_{k}"]), weekly=False) for k in ("K0", "K1")}
    b["wrazliwosc_dni_dLL_K1_minus_K0"] = round(float((ll_day["K1"] - ll_day["K0"]).sum()), 3)
    result["A_b_model_zliczen"] = b

    # --- warunek 3: 2.5 ---
    c3 = check_2_5(profile)
    result["A_warunek_3_walidacja_2_5"] = c3

    verdict = decide(b["dLL_K1_minus_K0"], b["lat_K1_lepsze"], a["roznica_K1_minus_K0"]["ci95"], c3["warunek_3"], enough)
    result["A_wynik_wg_regul"] = verdict

    # --- opisowo: profil opoznienia ---
    lag_cols = [f"P_lag_{x}_{y}" for x, y in LAG_BINS]
    fit = bf.fit_nb1(f["y"], design(f, lag_cols), f["rok"], f["tydzien"], se=True)
    result["profil_opoznienia_opisowo"] = {
        f"{x}-{y} dni": {"beta_na_mm_dobe": round(float(be), 4), "ci95": [round(float(be - 1.96 * s), 4), round(float(be + 1.96 * s), 4)]}
        for (x, y), be, s in zip(LAG_BINS, fit["beta"][:len(LAG_BINS)], fit["beta_se"][:len(LAG_BINS)])}
    result["profil_opoznienia_opisowo"]["LL_LOYO_minus_K0"] = round(float(loyo_ll(f, design(f, lag_cols)).sum() - ll["K0"].sum()), 3)

    # --- B: eksploracyjnie ---
    base_kind = "K1" if verdict in ("K1 lepsze", "K1 nie gorsze") else "K0"
    base_ll = ll[base_kind]
    bb = {"model_bazowy": f"T20 + T20^2 + P_{base_kind}"}
    for extra in ("TX_mean5", "TX_gt20_n7", "TN_mean7", "DTR_mean7"):
        X = design(f, [f"P_{base_kind}"], [extra])
        dll = loyo_ll(f, X) - base_ll
        fit = bf.fit_nb1(f["y"], X, f["rok"], f["tydzien"], se=True)
        bb[extra] = {"dLL_LOYO": round(float(dll.sum()), 3), "lat_lepiej": int((dll > 0).sum()),
                     "beta": round(float(fit["beta"][-1]), 4), "se": round(float(fit["beta_se"][-1]), 4),
                     "korelacja_z_T20": round(float(f[extra].corr(f["T20"])), 3)}
    result["B_temperatura_w_ciagu_dnia_eksploracyjnie"] = bb

    (OUT / "17_bielefeld.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
