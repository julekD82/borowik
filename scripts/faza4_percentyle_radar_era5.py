"""Faza 4.2: spojnosc percentyli -- opad z radaru vs ERA5 (i E-OBS opisowo).

A. Radar (RainGRS, cache) vs ERA5 (Open-Meteo archive, TYLKO ten skrypt wola API:
   ~50 punktow x ok. 33 dni, koszt wg wzoru ~70) na tym samym okresie i tych samych
   ~50 punktach w obszarze Kieleczki. 26-dniowa suma opadu (wykladniczo wazona jak
   w F oraz zwykla), obciazenie, rozrzut i roznica percentyla CWB26 policzonego z
   radaru i z ERA5 dla tych samych dni (obie wzgledem tej samej klimatologii ERA5;
   ET0 z ERA5 w obu, wiec roznica pochodzi tylko z opadu).
B. E-OBS vs ERA5 (2.6, opisowo): dobowe archiwum ERA5 z cache (lata 2018/2020/2022,
   punkty z backtestu GBIF) i E-OBS lokalnie z cache/eobs -- rozklad 26-dniowej sumy
   opadu w sezonie sierpien-pazdziernik. E-OBS konczy sie na 2025, wiec nie da sie go
   porownac z radarem 2026 (BLOCKED dla trojki radar/ERA5/E-OBS na tym samym okresie).

  python scripts/faza4_percentyle_radar_era5.py
Wynik: docs/porownania/faza4/percentyle_radar_era5.json
"""
import glob
import json
import os
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from faza4_wspolne import ROOT, CACHE, KIELECZKA, RADIUS_KM, open_meteo_weight  # noqa: E402
from pipeline.eobs import EobsStore  # noqa: E402
from pipeline.prepare_trip import points_within_radius  # noqa: E402
from pipeline.radar import radar_hourly_at_points, radar_daily_at_points  # noqa: E402
from pipeline.tiles import tile_bbox_2180  # noqa: E402
from pipeline.weather import (  # noqa: E402
    make_grid, fetch_archive_daily, fetch_climatology_raw, climatology_window_values,
    percentile_rank, _exp_weighted_sum,
)

OUT = ROOT / "docs" / "porownania" / "faza4"
WINDOW = 26
HALF_SIZE_M = 5000.0        # blok 10 x 10 km ~ rozdzielczosc ERA5-Land (0,1 st.)
N_POINTS = 50
START = date(2026, 8, 28)   # pierwszy dzien z kompletnym archiwum radaru w cache


def pick_points():
    bbox = tile_bbox_2180(*KIELECZKA, size_km=2 * RADIUS_KM)
    pts = points_within_radius(make_grid(bbox, spacing_m=5000.0), *KIELECZKA, RADIUS_KM)
    step = max(1, len(pts) // N_POINTS)
    return pts[::step][:N_POINTS]


def radar_daily_series(points, first, last):
    start_utc = datetime(first.year, first.month, first.day, tzinfo=timezone.utc) - timedelta(hours=2)
    end_utc = datetime(last.year, last.month, last.day, tzinfo=timezone.utc) + timedelta(days=1, hours=2)
    hourly = radar_hourly_at_points(points, HALF_SIZE_M, start_utc, end_utc, CACHE / "radar_grs")
    d = radar_daily_at_points(hourly)
    # Archiwum RainGRS ma w cache dni z brakujacymi godzinami (np. 19/24): dobe z >= 16 godzin
    # uznaje za uzywalna, a jej sume skaluje o expected/hours (zaklada podobny opad w brakujacych
    # godzinach -- zanotowane w raporcie jako ograniczenie); dobe z mniejsza liczba godzin odrzuca.
    d["complete"] = d["radar_hours"] >= 16
    d["radar_mm"] = d["radar_mm"] * d["expected_hours"] / d["radar_hours"]
    return d


def part_a():
    points = pick_points()
    last = date.today() - timedelta(days=1)
    radar = radar_daily_series(points, START, last)
    era = fetch_archive_daily(points, START.isoformat(), last.isoformat(), cache_dir=CACHE)
    era["date"] = pd.to_datetime(era["date"], utc=True).dt.tz_convert("Europe/Warsaw").dt.date
    om = None
    try:
        from pipeline.weather import fetch_weather_raw
        om = fetch_weather_raw(points, 92, forecast_days=1, cache_dir=CACHE,
                               call_api=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("brak w cache")))
        om["date"] = pd.to_datetime(om["date"], utc=True).dt.tz_convert("Europe/Warsaw").dt.date
    except Exception as exc:  # noqa: BLE001 -- zrodlo dodatkowe, nie wymagane
        print("Open-Meteo (model) pominiety:", exc)

    bbox = tile_bbox_2180(*KIELECZKA, size_km=2 * RADIUS_KM)
    clim_pts = make_grid(bbox, spacing_m=20000.0)
    clim = fetch_climatology_raw(clim_pts, 1991, 2020, cache_dir=CACHE,
                                 call_api=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("brak w cache")))
    clim_xy = np.array(clim_pts)

    rows = []
    for lat, lon in points:
        e = era[(era["lat"] == lat) & (era["lon"] == lon)].set_index("date").sort_index()
        r = radar[(radar["lat"] == lat) & (radar["lon"] == lon)].set_index("local_date").sort_index()
        o = om[(om["lat"] == lat) & (om["lon"] == lon)].set_index("date").sort_index() if om is not None else None
        ci = int(np.argmin((clim_xy[:, 0] - lat) ** 2 + ((clim_xy[:, 1] - lon) * 0.64) ** 2))
        cell = clim_pts[ci]
        days = [d for d in e.index if d >= START + timedelta(days=WINDOW - 1)]
        for D in days:
            idx = [D - timedelta(days=k) for k in range(WINDOW - 1, -1, -1)]
            if not all(i in e.index and pd.notna(e.loc[i, "precipitation_mm"]) and pd.notna(e.loc[i, "et0_mm"]) for i in idx):
                continue
            if not all(i in r.index and bool(r.loc[i, "complete"]) for i in idx):
                continue
            p_era = pd.Series([e.loc[i, "precipitation_mm"] for i in idx])
            p_rad = pd.Series([r.loc[i, "radar_mm"] for i in idx])
            et0 = pd.Series([e.loc[i, "et0_mm"] for i in idx])
            hist = climatology_window_values(clim[(clim["lat"] == cell[0]) & (clim["lon"] == cell[1])],
                                             *cell, D.timetuple().tm_yday, "cwb26")
            et26 = _exp_weighted_sum(et0, WINDOW)
            row = {"lat": lat, "lon": lon, "end": str(D),
                   "sum_era5": float(p_era.sum()), "sum_radar": float(p_rad.sum()),
                   "p26w_era5": _exp_weighted_sum(p_era, WINDOW), "p26w_radar": _exp_weighted_sum(p_rad, WINDOW)}
            row["pct_era5"] = percentile_rank(row["p26w_era5"] - et26, hist)
            row["pct_radar"] = percentile_rank(row["p26w_radar"] - et26, hist)
            if o is not None and all(i in o.index for i in idx):
                p_om = pd.Series([o.loc[i, "precipitation_mm"] for i in idx])
                row["sum_om"] = float(p_om.sum())
                row["p26w_om"] = _exp_weighted_sum(p_om, WINDOW)
                row["pct_om"] = percentile_rank(row["p26w_om"] - et26, hist)
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "percentyle_radar_era5_punkty.csv", index=False)
    res = {"points": len(points), "windows_ending": sorted(df["end"].unique().tolist()) if len(df) else [],
           "n_point_windows": int(len(df)),
           "api_weight_era5_pull": open_meteo_weight(len(points), (last - START).days + 1, 0)}
    if not len(df):
        res["error"] = "brak kompletnych okien 26 dni (radar + ERA5)"
        return res

    def stats(a, b, name):
        diff = df[a] - df[b]
        return {name: {
            "median_diff_mm": float(diff.median()), "median_ratio": float((df[a] / df[b]).median()),
            "iqr_diff_mm": [float(diff.quantile(.25)), float(diff.quantile(.75))],
            "p05_p95_diff_mm": [float(diff.quantile(.05)), float(diff.quantile(.95))],
            "spearman_across_point_windows": float(spearmanr(df[a], df[b]).statistic),
            "median_abs_diff_pct": float((df["pct_" + a.split("_")[-1]] - df["pct_" + b.split("_")[-1]]).abs().median()),
            "p90_abs_diff_pct": float((df["pct_" + a.split("_")[-1]] - df["pct_" + b.split("_")[-1]]).abs().quantile(.9)),
            "median_signed_diff_pct": float((df["pct_" + a.split("_")[-1]] - df["pct_" + b.split("_")[-1]]).median()),
        }}
    res["radar_vs_era5_p26w"] = stats("p26w_radar", "p26w_era5", "p26w")["p26w"]
    res["radar_vs_era5_raw_sum"] = {
        "median_diff_mm": float((df["sum_radar"] - df["sum_era5"]).median()),
        "median_ratio": float((df["sum_radar"] / df["sum_era5"]).median()),
        "sum_radar_median": float(df["sum_radar"].median()), "sum_era5_median": float(df["sum_era5"].median())}
    res["pct_median_radar"] = float(df["pct_radar"].median())
    res["pct_median_era5"] = float(df["pct_era5"].median())
    if "p26w_om" in df:
        res["om_model_vs_era5_p26w"] = stats("p26w_om", "p26w_era5", "p26w")["p26w"]
        res["om_model_vs_radar_p26w"] = stats("p26w_om", "p26w_radar", "p26w")["p26w"]
    res["rule_median_abs_dpct_gt_0_10"] = bool(res["radar_vs_era5_p26w"]["median_abs_diff_pct"] > 0.10)
    return res


def _exp_sums(series: pd.Series) -> pd.Series:
    """Wykladniczo wazona suma 26 dni (polowa co 10 dni) na koniec kazdego dnia."""
    w = 0.5 ** (np.arange(WINDOW - 1, -1, -1) / 10.0)
    return series.rolling(WINDOW).apply(lambda x: float((x * w).sum()), raw=True)


def part_b():
    store = EobsStore(CACHE)
    files = glob.glob(str(CACHE / "archive_daily_points" / "*.parquet"))
    era_all, eobs_all = [], []
    for f in files:
        b = os.path.basename(f)[:-8].split("_")
        lat, lon, s, e = float(b[0]), float(b[1]), b[2], b[3]
        df = pd.read_parquet(f)
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("Europe/Warsaw").dt.tz_localize(None).dt.normalize()
        ser = df.set_index("date")["precipitation_mm"]
        ser = ser[~ser.index.duplicated(keep="first")]
        ob = store.daily(lat, lon, date.fromisoformat(s), date.fromisoformat(e), variables=["rr"])["rr"]
        j = pd.concat([ser.rename("era5"), ob.rename("eobs")], axis=1).dropna()
        if len(j) < 300:
            continue
        j = j.reindex(pd.date_range(j.index.min(), j.index.max())).interpolate(limit=2)
        sums = pd.DataFrame({"era5": _exp_sums(j["era5"]), "eobs": _exp_sums(j["eobs"])}).dropna()
        sums = sums[(sums.index.month >= 8) & (sums.index.month <= 10)]
        sums["lat"], sums["lon"] = lat, lon
        era_all.append(sums["era5"]); eobs_all.append(sums["eobs"])
    if not era_all:
        return {"error": "brak danych E-OBS/ERA5 w cache"}
    a, b = pd.concat(era_all), pd.concat(eobs_all)
    q = [5, 25, 50, 75, 95]
    # percentyl wartosci E-OBS w rozkladzie ERA5 (te same obserwacje)
    ref = np.sort(a.to_numpy())
    pct_eobs_in_era = np.searchsorted(ref, b.to_numpy()) / len(ref)
    pct_era_in_era = np.searchsorted(ref, a.to_numpy()) / len(ref)
    return {
        "observations": int(len(a)), "points": len(files), "season": "koniec okna 1.08-31.10, lata 2018/2020/2022",
        "p26w_quantiles_era5_5_25_50_75_95": [float(np.percentile(a, x)) for x in q],
        "p26w_quantiles_eobs_5_25_50_75_95": [float(np.percentile(b, x)) for x in q],
        "median_ratio_eobs_to_era5": float(np.median(b.to_numpy() / np.maximum(a.to_numpy(), 1e-6))),
        "spearman": float(spearmanr(a, b).statistic),
        "median_abs_diff_of_percentile_eobs_vs_era5": float(np.median(np.abs(pct_eobs_in_era - pct_era_in_era))),
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"date": str(date.today()), "A_radar_vs_era5": part_a(), "B_eobs_vs_era5": part_b()}
    (OUT / "percentyle_radar_era5.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
