"""Plan A2 Task 3: calibrate + validate pipeline.flush on the same GBIF
Boletus edulis finds as notebooks/03_backtest_gbif.py (its results CSV
defines the sample; its cached Open-Meteo archive weather is reused --
this notebook never touches the network). Statistic: percentile rank of
the find's day among the candidate days (1 Jun - 31 Oct) at the same
point and year (0.5 = no signal). Leave-one-year-out CV over a small grid.
Run: .venv/Scripts/python.exe notebooks/06_backtest_flush.py"""
import itertools
import math
import pathlib

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import stats

from pipeline.flush import FlushParams, flush_series
from pipeline.weather import fetch_archive_daily

RESULTS_03 = pathlib.Path("notebooks/output/backtest_gbif_results.csv")
CACHE_DIR = pathlib.Path("cache")
WEATHER_GRID_SPACING_M = 5000.0          # same as notebooks/03_backtest_gbif.py
CANDIDATE_DOYS = list(range(152, 305))   # same as notebooks/03_backtest_gbif.py
GRID = {
    "pulse_min_mm": [10.0, 15.0, 20.0, 25.0],
    "dd_peak": [60.0, 80.0, 100.0, 130.0, 160.0, 200.0],
    "dd_sigma": [20.0, 35.0, 50.0],
    "t_base_c": [4.0, 6.0],
}
FIXED = {"wet_day_mm": 1.0, "cold_night_c": 5.0, "cold_night_factor": 0.5, "frost_c": -1.0}

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def _snap(lat: float, lon: float, spacing_m: float) -> tuple[float, float]:
    # Identical to notebooks/03_backtest_gbif.py::_snap -- must stay so, or the cache misses.
    e, n = _TO_2180.transform(lon, lat)
    e_s = math.floor(e / spacing_m) * spacing_m + spacing_m / 2
    n_s = math.floor(n / spacing_m) * spacing_m + spacing_m / 2
    lon_s, lat_s = _TO_4326.transform(e_s, n_s)
    return round(lat_s, 6), round(lon_s, 6)


def _no_network(*args, **kwargs):
    raise RuntimeError("cache miss -- run notebooks/03_backtest_gbif.py first")


def load_obs() -> pd.DataFrame:
    obs = pd.read_csv(RESULTS_03)
    obs["date"] = pd.to_datetime(obs["date"])
    obs["year"] = obs["date"].dt.year
    obs["doy"] = obs["date"].dt.dayofyear
    return obs


def load_series(obs: pd.DataFrame) -> dict:
    series = {}
    for row in obs.itertuples():
        wp = _snap(row.lat, row.lon, WEATHER_GRID_SPACING_M)
        key = (wp, row.year)
        if key in series:
            continue
        df = fetch_archive_daily([wp], f"{row.year}-01-01", f"{row.year}-12-31",
                                 call_api=_no_network, cache_dir=CACHE_DIR).sort_values("date")
        local = df["date"].dt.tz_convert("Europe/Warsaw")
        series[key] = (local.dt.dayofyear.to_numpy(), df["precipitation_mm"].to_numpy(),
                       df["tmean_c"].to_numpy(), df["tmin_c"].to_numpy())
    return series


def rank_of(obs_row, series, params: FlushParams) -> float:
    doys, precip, tmean, tmin = series[(_snap(obs_row.lat, obs_row.lon, WEATHER_GRID_SPACING_M), obs_row.year)]
    index, _, _ = flush_series(precip, tmean, tmin, params)
    by_doy = dict(zip(doys.tolist(), index.tolist()))
    cands = sorted({d for d in CANDIDATE_DOYS + [obs_row.doy] if d in by_doy})
    values = np.array([by_doy[d] for d in cands])
    v = by_doy[obs_row.doy]
    return float((values < v).mean() + 0.5 * (values == v).mean())


def main():
    obs = load_obs()
    series = load_series(obs)
    combos = list(itertools.product(*GRID.values()))
    ranks = {}
    for combo in combos:
        params = FlushParams(**FIXED, **dict(zip(GRID.keys(), combo)))
        ranks[combo] = np.array([rank_of(row, series, params) for row in obs.itertuples()])
    years = sorted(obs["year"].unique())
    heldout = np.empty(len(obs))
    for year in years:
        train = (obs["year"] != year).to_numpy()
        best = max(combos, key=lambda c: ranks[c][train].mean())
        heldout[~train] = ranks[best][~train]
        print(f"rok {year}: n={int((~train).sum())} najlepsze na pozostalych = {dict(zip(GRID.keys(), best))}")
    full_best = max(combos, key=lambda c: ranks[c].mean())
    baseline = obs["rank_F_loc_no_gseason"].to_numpy()
    p = stats.wilcoxon(heldout - baseline).pvalue
    print(f"\nN={len(obs)}  flush (CV, held-out) srednia={heldout.mean():.3f} mediana={np.median(heldout):.3f}")
    print(f"baseline F_loc bez G_season srednia={baseline.mean():.3f} mediana={np.median(baseline):.3f}")
    print(f"Wilcoxon (flush - baseline) p={p:.4g}")
    print(f"najlepsze na calosci: {dict(zip(GRID.keys(), full_best))} srednia={ranks[full_best].mean():.3f}")
    gate = heldout.mean() > baseline.mean() and p < 0.10
    print("BRAMKA E3:", "ZALICZONA" if gate else "NIEZALICZONA -- zatrzymaj sie i zapytaj uzytkownika")


if __name__ == "__main__":
    main()
