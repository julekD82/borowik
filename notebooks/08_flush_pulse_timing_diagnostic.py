"""A2 Task 3 follow-up: diagnostic only, NOT production code, NOT part of
the plan's task list. After the E3 gate failed (notebooks/06_backtest_flush.py:
LOYO held-out mean 0.548 < baseline F_loc bez G_season 0.626), the user asked
for a narrower question before touching the model at all: does "days since
the last rain pulse" or "degree-days since the last rain pulse" separate the
90 real GBIF Boletus edulis find dates from random candidate days (1 Jun -
31 Oct) at the SAME point/year, at all -- regardless of any Gaussian peak
shape or dd_peak/dd_sigma choice?

Method: reuses notebooks/06_backtest_flush.py's cached per-point-year ERA5
series (same _snap, same CANDIDATE_DOYS = 152..304). For pulse_min_mm in
[15, 20] (the two values the user named; wet_day_mm/cold_night_c/
cold_night_factor/frost_c/t_base_c fixed at the profile's original [E]
values), for every point/year and every day in CANDIDATE_DOYS (plus each
find's own day), find the most recent pulse ending on or before that day and
report (day - pulse.end) and degree_days_after(pulse.end)[day]. Compares the
90 find-day values against the pooled candidate-day values with a two-sample
KS test, for both metrics.

No network. Run: .venv/Scripts/python.exe notebooks/08_flush_pulse_timing_diagnostic.py
(from the repo root; PYTHONPATH=. only needed if pipeline.flush is not yet
picked up by the active environment's editable install)."""
import math
import pathlib

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import stats

from pipeline.flush import FlushParams, detect_pulses, degree_days_after
from pipeline.weather import fetch_archive_daily

RESULTS_03 = pathlib.Path("notebooks/output/backtest_gbif_results.csv")
CACHE_DIR = pathlib.Path("cache")
WEATHER_GRID_SPACING_M = 5000.0
CANDIDATE_DOYS = list(range(152, 305))
PULSE_MIN_VALUES = [15.0, 20.0]
FIXED = {"wet_day_mm": 1.0, "t_base_c": 5.0, "cold_night_c": 5.0, "cold_night_factor": 0.5, "frost_c": -1.0}

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


def since_last_pulse(doys, precip, tmean, tmin, target_doy, params: FlushParams):
    """(days_since, degree_days) for the most recent pulse ending on or
    before target_doy, or (None, None) if no such pulse exists."""
    hits = np.flatnonzero(doys == target_doy)
    if len(hits) == 0:
        return None, None
    t = hits[0]
    pulses = detect_pulses(precip, params)
    candidates = [p for p in pulses if p.end <= t]
    if not candidates:
        return None, None
    pulse = max(candidates, key=lambda p: p.end)
    days_since = int(doys[t] - doys[pulse.end])
    dd = degree_days_after(pulse.end, tmean, tmin, params)
    degree_days = float(dd[t])
    return days_since, (None if math.isinf(degree_days) or math.isnan(degree_days) else degree_days)


def text_histogram(values, label, bins=10):
    values = np.asarray(values, dtype=float)
    counts, edges = np.histogram(values, bins=bins)
    print(f"  histogram {label} (N={len(values)}):")
    for c, lo, hi in zip(counts, edges[:-1], edges[1:]):
        bar = "#" * int(round(40 * c / counts.max())) if counts.max() else ""
        print(f"    {lo:8.1f} .. {hi:8.1f} | {c:4d} {bar}")


def main():
    obs = load_obs()
    series = load_series(obs)
    for pulse_min_mm in PULSE_MIN_VALUES:
        params = FlushParams(pulse_min_mm=pulse_min_mm, dd_peak=100.0, dd_sigma=35.0, **FIXED)
        print(f"\n=== pulse_min_mm = {pulse_min_mm} ===")

        obs_days_since, obs_dd = [], []
        for row in obs.itertuples():
            doys, precip, tmean, tmin = series[(_snap(row.lat, row.lon, WEATHER_GRID_SPACING_M), row.year)]
            d, dd = since_last_pulse(doys, precip, tmean, tmin, row.doy, params)
            if d is not None:
                obs_days_since.append(d)
            if dd is not None:
                obs_dd.append(dd)
        print(f"  znaleziska z policzonym ostatnim pulsem: {len(obs_days_since)} / {len(obs)}")

        cand_days_since, cand_dd = [], []
        seen_series = set()
        for row in obs.itertuples():
            key = (_snap(row.lat, row.lon, WEATHER_GRID_SPACING_M), row.year)
            if key in seen_series:
                continue
            seen_series.add(key)
            doys, precip, tmean, tmin = series[key]
            for doy in CANDIDATE_DOYS:
                d, dd = since_last_pulse(doys, precip, tmean, tmin, doy, params)
                if d is not None:
                    cand_days_since.append(d)
                if dd is not None:
                    cand_dd.append(dd)
        print(f"  dni kandydackie z policzonym ostatnim pulsem: {len(cand_days_since)}"
              f" (z {len(seen_series)} unikalnych punkt/rok)")

        print(f"  dni od pulsu -- znaleziska: srednia={np.mean(obs_days_since):.1f}"
              f" mediana={np.median(obs_days_since):.1f}")
        print(f"  dni od pulsu -- kandydaci:  srednia={np.mean(cand_days_since):.1f}"
              f" mediana={np.median(cand_days_since):.1f}")
        ks_days = stats.ks_2samp(obs_days_since, cand_days_since)
        print(f"  KS (dni od pulsu): statystyka={ks_days.statistic:.3f} p={ks_days.pvalue:.4g}")
        text_histogram(obs_days_since, "dni od pulsu -- znaleziska")
        text_histogram(cand_days_since, "dni od pulsu -- kandydaci")

        print(f"  stopniodni od pulsu -- znaleziska: srednia={np.mean(obs_dd):.1f}"
              f" mediana={np.median(obs_dd):.1f}  (N={len(obs_dd)})")
        print(f"  stopniodni od pulsu -- kandydaci:  srednia={np.mean(cand_dd):.1f}"
              f" mediana={np.median(cand_dd):.1f}  (N={len(cand_dd)})")
        ks_dd = stats.ks_2samp(obs_dd, cand_dd)
        print(f"  KS (stopniodni od pulsu): statystyka={ks_dd.statistic:.3f} p={ks_dd.pvalue:.4g}")
        text_histogram(obs_dd, "stopniodni od pulsu -- znaleziska")
        text_histogram(cand_dd, "stopniodni od pulsu -- kandydaci")


if __name__ == "__main__":
    main()
