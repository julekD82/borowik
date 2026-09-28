"""Plan wdrozenia 1.8a (spec S18.4 #1): notebooks/03_backtest_gbif.py's
_daily_features must convert Open-Meteo's UTC-instant `date` to Europe/Warsaw
before extracting day-of-year, exactly like notebooks 06/09 already do --
otherwise every feature is filed under the PREVIOUS local calendar day (local
midnight is ~22:00-23:00 UTC the day before). The module filename starts
with a digit, so it's loaded via importlib like tests/test_launcher_pyw_runs.py
loads launcher.pyw, not a normal `import`."""
import importlib.util
import pathlib

import numpy as np
import pandas as pd
import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "notebooks" / "03_backtest_gbif.py"
_spec = importlib.util.spec_from_file_location("backtest_gbif_03", _PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_daily_features = _mod._daily_features


def _synthetic_year_daily(first_local_day: str, n_days: int) -> pd.DataFrame:
    """One row per intended local day, UTC `date` column built the same way
    pipeline.weather._parse_open_meteo_response does (fixed 86400s step
    from day 1's true local midnight) -- reproduces the real DST drift.
    precipitation_mm is a ramp (row i = i) so a feature computed from a
    specific slot can be checked against an exact expected number instead
    of just "is not None"."""
    start_utc = pd.Timestamp(first_local_day, tz="Europe/Warsaw").tz_convert("UTC")
    dates = pd.date_range(start=start_utc, periods=n_days, freq="86400s")
    return pd.DataFrame({
        "date": dates,
        "precipitation_mm": np.arange(n_days, dtype=float),
        "et0_mm": np.zeros(n_days),
        "tmean_c": np.zeros(n_days),
        "tmin_c": np.zeros(n_days),
        "soil_moisture": np.zeros(n_days),
    })


def test_daily_features_assigns_the_correct_local_day_across_october_transition():
    # 2026-01-01 is array index 0 -> doy 1, so doy 299 (2026-10-26) is index
    # 298 IF the intended local day is recovered correctly. p5 there is the
    # 5-day sum ending at index 298: 294+295+296+297+298 = 1480. Without the
    # fix, index 298's row is misfiled one slot earlier (doy 298), and slot
    # 299 instead gets index 299's row (p5 = 295+..+299 = 1485) -- a real,
    # checkable difference, not just "some value is present".
    daily = _synthetic_year_daily("2026-01-01", 366)
    feats = _daily_features(daily)
    assert feats[299] is not None
    assert feats[299]["p5"] == pytest.approx(1480.0)
