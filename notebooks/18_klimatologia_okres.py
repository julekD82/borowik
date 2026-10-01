"""EKSPLORACYJNIE (bez zmiany modelu): okres klimatologii 1991-2020 (produkcja) vs 1996-2025 (ostatnie 30 lat).

Pytanie wlasciciela (1.10.2026): czy uzupelnic klimatologie o ostatnie lata. Klimatologia to punkt odniesienia
percentyla CWB26 (M w F) i normy opadu w panelu pogody. Liczone na lokalnym E-OBS (produkcja uzywa ERA5 z
Open-Meteo -- tu kierunek i rzad wielkosci, nie dokladne wartosci aplikacji).

1. Test 2.5 na zamrozonym zbiorze (jak notebooks/12 i 17): F bez G_season, oba tla, roznica rang C1 - C0.
2. Przesuniecie poziomu: komorki E-OBS w promieniu 20 km wokol dwoch analiz, dni sezonu 15.08-10.11 lat
   2021-2025: zmiana percentyla, M i F; czy kolejnosc komorek (ranking miejsc) zostaje.
3. Norma opadu z 26 dni w panelu (E-OBS, jak pipeline/rain_normal.py) dla 1.10 w obu okresach.

Run: .venv/Scripts/python.exe notebooks/18_klimatologia_okres.py
"""
import importlib.util
import json
import pathlib
from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy import stats

from pipeline import validation_stats as vs
from pipeline.eobs import EobsStore
from pipeline.eobs_fruiting import CLIM_WINDOW_DAYS, CellClimate, variant_scores
from pipeline.habitat import load_profile
from pipeline.rain_normal import eobs_cells_in_radius, rain26_pool

OUT = pathlib.Path("notebooks/output/walidacja")
PERIODS = {"C0": (1991, 2020), "C1": (1996, 2025)}
WINDOW = 15
AREAS = {"Zawadzkie": (50.6191, 18.4611)}
SEASON = ((8, 15), (11, 10))
RECENT_YEARS = range(2021, 2026)


class Climatologies:
    """Klimatologia CWB26 jednej komorki dla kilku okresow (z tych samych cech dobowych CellClimate)."""

    def __init__(self, cc: CellClimate):
        self.cc = cc
        self._by_period = {}
        for name, (y0, y1) in PERIODS.items():
            clim = cc.features.loc[f"{y0}-01-01":f"{y1}-12-31", "cwb26"].dropna()
            self._by_period[name] = (clim.index.dayofyear.to_numpy(), clim.to_numpy())

    def hist(self, period: str, doy: int) -> np.ndarray:
        doys, vals = self._by_period[period]
        diff = np.abs(doys - doy)
        return vals[np.minimum(diff, 365 - diff) <= CLIM_WINDOW_DAYS]


def load_nb12():
    spec = importlib.util.spec_from_file_location("nb12", "notebooks/12_walidacja_2_5.py")
    nb12 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb12)
    return nb12


def check_2_5(profile: dict, store: EobsStore) -> dict:
    nb12 = load_nb12()
    df = pd.read_csv(OUT / "2_5_zbior_zamrozony.csv")
    climates: dict[str, Climatologies] = {}
    cache_before = len(list(pathlib.Path(".cache/gbif_inventory").glob("*.json")))
    rows = []
    for _, r in df.iterrows():
        if r["cell"] not in climates:
            climates[r["cell"]] = Climatologies(CellClimate(store, r["lat"], r["lon"]))
        cl = climates[r["cell"]]
        d0 = date.fromisoformat(r["day"])
        scores = {p: {} for p in PERIODS}
        for k in range(-WINDOW, WINDOW + 1):
            ts = pd.Timestamp(d0 + timedelta(days=k))
            if ts not in cl.cc.features.index or cl.cc.features.loc[ts].isna().any():
                continue
            for p in PERIODS:
                scores[p][ts.date().isoformat()] = variant_scores(
                    cl.cc.features.loc[ts], ts.dayofyear, cl.hist(p, ts.dayofyear), profile)["F_bez_G_season"]
        if any(r["day"] not in s or len(s) < 10 for s in scores.values()):
            continue
        fungi = nb12.other_fungi_days(r["lat"], r["lon"], d0) - {r["day"]}
        rec = {"key": r["key"], "year": r["year"], "cell": r["cell"]}
        for p, s in scores.items():
            ctrl = {k: v for k, v in s.items() if k != r["day"]}
            rec[f"a_{p}"] = vs.rank_of(s[r["day"]], np.array(list(ctrl.values())))
            ctrl_b = [v for k, v in ctrl.items() if k in fungi]
            rec[f"b_{p}"] = vs.rank_of(s[r["day"]], np.array(ctrl_b)) if len(ctrl_b) >= nb12.MIN_FUNGI_DAYS else np.nan
        rows.append(rec)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "18_2_5_C0_C1_rangi.csv", index=False)
    out = {"nowe_zapytania_GBIF": len(list(pathlib.Path(".cache/gbif_inventory").glob("*.json"))) - cache_before}
    orig = pd.read_csv(OUT / "2_5_rangi.csv")[["key", "a_F_bez_G_season", "b_F_bez_G_season"]].merge(res, on="key")
    out["kontrola_C0_vs_oryginal_2_5"] = {
        "wspolne_rekordy": len(orig),
        "maks_roznica_rangi_a": float((orig["a_C0"] - orig["a_F_bez_G_season"]).abs().max()),
        "maks_roznica_rangi_b": float((orig["b_C0"] - orig["b_F_bez_G_season"]).abs().max())}
    for bg in ("a", "b"):
        fr = res.dropna(subset=[f"{bg}_C0", f"{bg}_C1"])
        diff = (fr[f"{bg}_C1"] - fr[f"{bg}_C0"]).to_numpy()
        lo, hi = nb12.ci(diff, fr, "cell")
        out[f"tlo_{bg}"] = {
            "n": len(fr), "srednia_ranga_C0": round(float(fr[f"{bg}_C0"].mean()), 4),
            "srednia_ranga_C1": round(float(fr[f"{bg}_C1"].mean()), 4),
            "roznica_C1_minus_C0": round(float(diff.mean()), 4), "ci95": [round(lo, 4), round(hi, 4)],
            "rekordy_z_inna_ranga": int((np.abs(diff) > 1e-9).sum())}
    return out


def season_days(year: int) -> pd.DatetimeIndex:
    return pd.date_range(date(year, *SEASON[0]), date(year, *SEASON[1]), freq="D")


def level_shift(profile: dict, store: EobsStore, lat: float, lon: float) -> dict:
    cells = eobs_cells_in_radius(lat, lon, 20)
    per_day = []  # (dzien, komorka, pct/M/F w C0 i C1)
    normal_doy = date(2026, 10, 1).timetuple().tm_yday
    medians = {p: [] for p in PERIODS}
    for clat, clon in cells:
        cl = Climatologies(CellClimate(store, clat, clon))
        for p in PERIODS:
            medians[p].append(float(np.median(cl.hist(p, normal_doy))))
        for year in RECENT_YEARS:
            for ts in season_days(year):
                if ts not in cl.cc.features.index or cl.cc.features.loc[ts].isna().any():
                    continue
                feat, doy = cl.cc.features.loc[ts], ts.dayofyear
                row = {"day": ts, "cell": (clat, clon)}
                for p in PERIODS:
                    hist = cl.hist(p, doy)
                    s = variant_scores(feat, doy, hist, profile)
                    row[f"pct_{p}"] = vs_pct(float(feat["cwb26"]), hist)
                    row[f"M_{p}"] = s["samo_M"]
                    row[f"F_{p}"] = s["F_bez_G_season"]
                per_day.append(row)
    f = pd.DataFrame(per_day)
    d_pct, d_m, d_f = (f["pct_C1"] - f["pct_C0"]), (f["M_C1"] - f["M_C0"]), (f["F_C1"] - f["F_C0"])
    rho = []
    for _, g in f.groupby("day"):
        if len(g) >= 3 and g["F_C0"].nunique() > 1:
            rho.append(stats.spearmanr(g["F_C0"], g["F_C1"]).statistic)
    return {
        "komorek_E_OBS": len(cells), "dni_x_komorek": len(f),
        "mediana_CWB26_1_10_mm": {p: round(float(np.mean(v)), 1) for p, v in medians.items()},
        "zmiana_percentyla_srednia": round(float(d_pct.mean()), 3),
        "zmiana_percentyla_p10_p90": [round(float(d_pct.quantile(0.1)), 3), round(float(d_pct.quantile(0.9)), 3)],
        "zmiana_M_srednia": round(float(d_m.mean()), 3),
        "zmiana_F_srednia": round(float(d_f.mean()), 3),
        "zmiana_F_p10_p90": [round(float(d_f.quantile(0.1)), 3), round(float(d_f.quantile(0.9)), 3)],
        "udzial_dni_z_abs_zmiana_F_ponad_0_05": round(float((d_f.abs() > 0.05).mean()), 3),
        "spearman_F_miedzy_komorkami_tego_dnia_mediana": round(float(np.median(rho)), 4) if rho else None,
        "spearman_F_min": round(float(np.min(rho)), 4) if rho else None,
    }


def vs_pct(value: float, hist: np.ndarray) -> float:
    from pipeline.weather import percentile_rank
    return percentile_rank(value, hist)


def panel_normal(store: EobsStore, lat: float, lon: float) -> dict:
    cells = eobs_cells_in_radius(lat, lon, 20)
    doy = date(2026, 10, 1).timetuple().tm_yday
    return {p: round(float(np.median(rain26_pool(store, cells, doy, years=y))), 1) for p, y in PERIODS.items()}


def main() -> None:
    profile = load_profile("profiles/boletus_edulis.yaml")
    store = EobsStore("cache")
    manifest = json.loads(pathlib.Path("frontend/public/data/manifest.json").read_text(encoding="utf-8"))
    areas = dict(AREAS)
    if manifest.get("lat") and abs(manifest["lat"] - AREAS["Zawadzkie"][0]) > 0.2:
        areas["biezaca_analiza"] = (manifest["lat"], manifest["lon"])
    result = {"okresy": PERIODS, "uwaga": "E-OBS (siec stacji), produkcja liczy z ERA5 -- kierunek i skala, nie wartosci aplikacji"}
    result["test_2_5"] = check_2_5(profile, store)
    result["przesuniecie_poziomu"] = {name: level_shift(profile, store, *ll) for name, ll in areas.items()}
    result["norma_opadu_panelu_1_10_mm"] = {name: panel_normal(store, *ll) for name, ll in areas.items()}
    (OUT / "18_klimatologia_okres.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str),
                                                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
