"""A2 Task 3 follow-up #2: diagnostic only, NOT production code. Repeats
notebooks/08_flush_pulse_timing_diagnostic.py's comparison but controls for
season: candidate days for each find are restricted to a +/-15 day window
around THAT find's own day-of-year (same point/year), instead of the whole
1 Jun - 31 Oct range. Tests the hypothesis that the earlier "znaleziska mial
nizsze degree-days-since-pulse" result was really just "znaleziska sa w
chlodniejszej czesci sezonu" (degree-days accumulate slower when cooler),
not a same-season rain-recency effect.

No network (reuses notebook 06's cached ERA5 series).
Run: .venv/Scripts/python.exe notebooks/09_flush_pulse_timing_season_controlled.py
(PYTHONPATH=. if pipeline.flush is not picked up by the active install)."""
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
SEASON_LO, SEASON_HI = 152, 304   # 1 Jun - 31 Oct, same bounds as notebook 06/08
WINDOW_DAYS = 15
PULSE_MIN_VALUES = [15.0, 20.0]
FIXED = {"wet_day_mm": 1.0, "t_base_c": 5.0, "cold_night_c": 5.0, "cold_night_factor": 0.5, "frost_c": -1.0}

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def _snap(lat: float, lon: float, spacing_m: float) -> tuple[float, float]:
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


def main():
    obs = load_obs()
    series = load_series(obs)
    for pulse_min_mm in PULSE_MIN_VALUES:
        params = FlushParams(pulse_min_mm=pulse_min_mm, dd_peak=100.0, dd_sigma=35.0, **FIXED)
        print(f"\n=== pulse_min_mm = {pulse_min_mm} (kandydaci: +/-{WINDOW_DAYS} dni wokol DOY znaleziska) ===")

        obs_days_since, obs_dd = [], []
        cand_days_since, cand_dd = [], []
        for row in obs.itertuples():
            doys, precip, tmean, tmin = series[(_snap(row.lat, row.lon, WEATHER_GRID_SPACING_M), row.year)]
            d, dd = since_last_pulse(doys, precip, tmean, tmin, row.doy, params)
            if d is not None:
                obs_days_since.append(d)
            if dd is not None:
                obs_dd.append(dd)

            lo, hi = max(SEASON_LO, row.doy - WINDOW_DAYS), min(SEASON_HI, row.doy + WINDOW_DAYS)
            for cand_doy in range(lo, hi + 1):
                if cand_doy == row.doy:
                    continue
                cd, cdd = since_last_pulse(doys, precip, tmean, tmin, cand_doy, params)
                if cd is not None:
                    cand_days_since.append(cd)
                if cdd is not None:
                    cand_dd.append(cdd)

        print(f"  znaleziska z policzonym ostatnim pulsem: {len(obs_days_since)} / {len(obs)}")
        print(f"  dni kandydackie (sezonowo dopasowane) z policzonym pulsem: {len(cand_days_since)}")

        print(f"  dni od pulsu -- znaleziska: srednia={np.mean(obs_days_since):.1f}"
              f" mediana={np.median(obs_days_since):.1f}")
        print(f"  dni od pulsu -- kandydaci (sezon +/-{WINDOW_DAYS}d): srednia={np.mean(cand_days_since):.1f}"
              f" mediana={np.median(cand_days_since):.1f}")
        ks_days = stats.ks_2samp(obs_days_since, cand_days_since)
        print(f"  KS (dni od pulsu): statystyka={ks_days.statistic:.3f} p={ks_days.pvalue:.4g}")

        print(f"  stopniodni od pulsu -- znaleziska: srednia={np.mean(obs_dd):.1f}"
              f" mediana={np.median(obs_dd):.1f}  (N={len(obs_dd)})")
        print(f"  stopniodni od pulsu -- kandydaci (sezon +/-{WINDOW_DAYS}d): srednia={np.mean(cand_dd):.1f}"
              f" mediana={np.median(cand_dd):.1f}  (N={len(cand_dd)})")
        ks_dd = stats.ks_2samp(obs_dd, cand_dd)
        print(f"  KS (stopniodni od pulsu): statystyka={ks_dd.statistic:.3f} p={ks_dd.pvalue:.4g}")


if __name__ == "__main__":
    main()
