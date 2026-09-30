"""Plan 2.8, etap 1 -- KONTROLA WCZYTANIA danych z Bielefeld (bez analizy nowych hipotez).

1. Liczby opisowe z pracy (1905 owocnikow, 4 w 2016, 354 w 2020, 85,8% dni zerowych, zakres 05.08-21.11).
2. Czy nasze srednie kroczace z dziennych Temp/Precip autorow odtwarzaja ich kolumny rollT_w/rollP_w.
4. Wlasna pogoda E-OBS v33.0e (komorka i interpolacja dwuliniowa) vs pogoda autorow; zapis dziennej pogody
   komorki 1991-2024 do dane_walidacyjne/bielefeld/ (wymaga cache/eobs/*_BI.npz).
3. Odtworzenie wyboru okien (AIC, okna 2..35 co 3 dni) prostszym modelem: NB1 z rokiem jako efektem
   STALYM (autorzy: glmmTMB nbinom1 z rokiem jako efektem losowym) na pogodzie autorow.
Bez sieci: dane z cache/bielefeld (scripts/pobierz_bielefeld.py).

Run: .venv/Scripts/python.exe notebooks/17_bielefeld_wczytanie.py
"""
import json
import pathlib
from datetime import date

import numpy as np
import pandas as pd

from pipeline import bielefeld as bf
from pipeline.eobs import EobsStore

SRC = pathlib.Path("cache/bielefeld/V1.2/ebrejonl-Boletus_fruiting_triggers-7967c6d") / bf.AUTHORS_CSV
OUT = pathlib.Path("notebooks/output/walidacja")
DATA = pathlib.Path("dane_walidacyjne/bielefeld")
WINDOWS = list(range(2, 36, 3))


def window_screen(raw: pd.DataFrame, site: str) -> pd.DataFrame:
    d = raw[raw["site"] == site]
    y = d["Mnb"].to_numpy(float)
    rows = []
    for wt in WINDOWS:
        for wp in WINDOWS:
            t = d[f"rollT_{wt}"].to_numpy()
            p = d[f"rollP_{wp}"].to_numpy()
            fit = bf.fit_nb1(y, np.column_stack([p, t, t ** 2]), d["year"].to_numpy())
            b = fit["beta"]
            rows.append({"win_T": wt, "win_P": wp, "aic": fit["aic"], "converged": fit["converged"],
                         "coef_P": b[0], "peak_T": -b[1] / (2 * b[2]) if b[2] < 0 else np.nan})
    res = pd.DataFrame(rows)
    res["dAIC"] = res["aic"] - res["aic"].min()
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SRC)
    daily = bf.daily_counts(raw)
    weather = bf.authors_weather(raw)
    result = {"opis_caly_plik": bf.descriptive(daily),
              "opis_zakres_z_pracy_05.08-21.11": bf.descriptive(daily, md_range=("08-05", "11-21")),
              "opis_Site_A": bf.descriptive(daily, "Site_A"), "opis_Site_B": bf.descriptive(daily, "Site_B")}

    # 2. definicja okien: plik ma tylko 1.08-30.11, wiec sprawdzamy dni, dla ktorych okno miesci sie w pliku
    alls = raw[raw["site"] == "All"].set_index(pd.to_datetime(raw.loc[raw["site"] == "All", "Date"]))
    diffs = {}
    for w in WINDOWS:
        ours_t = bf.rolling_mean_within_year(weather["tg"], w)
        ours_p = bf.rolling_mean_within_year(weather["rr"], w)
        ok = ours_t.index[ours_t.index.dayofyear >= pd.Timestamp("2015-08-01").dayofyear + w + 1]
        ok = [ts for ts in ok if ts.month >= 8 and not (ts.month == 8 and ts.day <= w)]
        diffs[w] = {"T_max_abs": float((ours_t.loc[ok] - alls.loc[ok, f"rollT_{w}"]).abs().max()),
                    "P_max_abs": float((ours_p.loc[ok] - alls.loc[ok, f"rollP_{w}"]).abs().max())}
    result["okna_zgodnosc_z_kolumnami_autorow"] = diffs

    # 3. przeglad okien
    screens = {}
    for site in bf.SITES:
        res = window_screen(raw, site)
        best = res.loc[res["aic"].idxmin()]
        at_20 = res[res["win_T"] == 20].sort_values("dAIC")
        at_26 = res[res["win_P"] == 26].sort_values("dAIC")
        screens[site] = {
            "najlepsze": {"win_T": int(best["win_T"]), "win_P": int(best["win_P"]), "peak_T": round(float(best["peak_T"]), 2)},
            "wszystkie_zbiezne": bool(res["converged"].all()),
            "T20_P26": {k: round(float(v), 3) for k, v in res[(res["win_T"] == 20) & (res["win_P"] == 26)]
                        [["dAIC", "peak_T", "coef_P"]].iloc[0].items()},
            "okno_P_przy_T20_top3": at_20[["win_P", "dAIC"]].head(3).round(2).to_dict("records"),
            "okno_T_przy_P26_top3": at_26[["win_T", "dAIC"]].head(3).round(2).to_dict("records"),
            "top5": res.sort_values("aic")[["win_T", "win_P", "dAIC"]].head(5).round(2).to_dict("records"),
        }
        res.to_csv(OUT / f"17_okna_{site}.csv", index=False)
    result["przeglad_okien_NB1_rok_staly"] = screens

    # 4. wlasna pogoda E-OBS v33.0e (obszar BI) vs pogoda autorow; zapis komorki do dane_walidacyjne/
    store = EobsStore("cache", region="BI")
    lat, lon = bf.CENTROID
    cell = store.cell(lat, lon)
    days = (weather.index.min().date(), weather.index.max().date())
    nearest = store.daily(*cell, *days)
    if nearest[["tg", "rr"]].notna().any().all():
        result["pogoda_EOBS_v33e_vs_autorzy"] = {
            "komorka": list(cell),
            "najblizsza_komorka": bf.compare_weather(nearest, weather),
            "interpolacja_dwuliniowa": bf.compare_weather(store.daily_bilinear(lat, lon, *days, ["tg", "rr"]), weather),
        }
        full = store.daily(*cell, date(1991, 1, 1), date(2024, 12, 31))
        result["pogoda_EOBS_v33e_komorka_plik"] = {
            "sciezka": bf.write_eobs_cell(full, DATA), "dni": len(full),
            "braki": {k: int(v) for k, v in full.isna().sum().items()}}
    else:
        result["pogoda_EOBS_v33e_vs_autorzy"] = "brak plikow cache/eobs/*_BI.npz (scripts/pobierz_eobs.py --obszary BI)"
    (OUT / "17_bielefeld_wczytanie.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
