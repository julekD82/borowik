# A2: model fazy wysypu (oś czasu na 7 dni) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer "kiedy jechać": detect rain pulses, run a thermal clock (with cold-night slowdown and frost stop) from each pulse, turn it into a flush-intensity curve, and show one 7-day timeline + phase sentence for the whole search area in the frontend's „Warunki” bar — without changing R (ranking stays "gdzie").

**Architecture:** New pure module `pipeline/flush.py` (never imported by `orchestrate`/`scoring`/`mvp`/`habitat` — structural guarantee that R is untouched, same idea as `pipeline/tie_break.py`). Calibrated on the existing GBIF backtest (90 real Boletus edulis finds, weather already cached) with leave-one-year-out cross-validation and a hard ship gate against the current F. `prepare_trip` makes one extra weather fetch (radar-merged past + 7 forecast days), builds an area-median daily weather series, runs the model once, and writes an optional `flush_{day}.json`; `sync-data` copies it as optional `flush.json`; the frontend renders it in `#conditions`.

**Tech Stack:** Python 3.12 (numpy, pandas, pyproj, scipy for the notebook), pytest; TypeScript/Vite frontend (`model.ts`, `main.ts`, `style.css`, Vitest); Node `scripts/sync-data.mjs`; `launcher/trip_archive.py`.

**Spec:** This plan's "Decyzje projektowe" section. Derived in the 2026-09-27 session: user chose (1) separate indicator, R unchanged until GBIF shows the flush model beats F; (2) one area-wide timeline in the „Warunki” bar; (3) 7-day horizon; then approved the model design below. Context: `docs/CODEX-HANDOFF.md` notes (23), (25), (26).

## Decyzje projektowe (spec)

Model (all numbers marked [E] are initial values; Task 3 calibrates the ones in the grid):
- **Pulse** = an episode of wet days (`precip >= wet_day_mm` = 1 mm), a single dry day inside an episode allowed, whose total ≥ `pulse_min_mm` [E 15 mm, calibrated]. Strength = `min(1, total / (2 * pulse_min_mm))`.
- **Thermal clock** from the day after the pulse's last wet day: daily rate = `max(0, tmean − t_base_c)` [E 5 °C, calibrated]; a day with `tmin < cold_night_c` (5 °C) [E] counts `cold_night_factor` (0.5) [E] of its rate; the first day with `tmin < frost_c` (−1 °C) [E] ends the wave (thermal time = +∞ → intensity 0).
- **Intensity** of one wave = `strength * exp(-0.5 * ((DD − dd_peak) / dd_sigma)^2)` [E dd_peak 100, dd_sigma 35, both calibrated]. Daily index = max over waves × `G_season(doy)` (existing `pipeline.phenology.compute_g_season`).
- **Phase** of a wave on day t from its DD(t): `< peak−2σ` przed_fala ("grzyby dopiero rosną"), `< peak−0.5σ` poczatek ("początek wysypu"), `≤ peak+0.5σ` szczyt, `≤ peak+2σ` starzeje_sie ("fala się starzeje"), else po_fali (not shown). NaN (rain still falling today) = przed_fala. Peak window = dates where DD crosses peak∓0.5σ, extrapolated past the series end with the mean rate of the last ≤7 days.
- **Output**: up to `max_waves` (2) most recent non-finished waves whose rain ended ≤ `lookback_days` (45) ago and not in the future; 7 day tiles (today..today+6) with `level` 0–3 from `level_thresholds` [0.1, 0.3, 0.6]; a Polish summary sentence, e.g. "Fala po deszczu 21–23.09: grzyby dopiero rosną, szczyt ok. 1–3.10 · starsza fala po deszczu 11–12.09: fala się starzeje".

Decisions to confirm in Task 0 (E1–E4):
- **E1 Area-level only.** One timeline from the per-day MEDIAN of precipitation/tmean/tmin over weather grid points within the search radius (rain differences within 20 km were 10–25 %, note (26)). Per-region timelines: later, if ever needed.
- **E2 Radar vs ERA5 threshold.** Calibration runs on ERA5 (Open-Meteo archive) rain — the radar archive is only 2018+ and ~80 MB/day. Production rain is radar, measured 0.848× ERA5 (note (25)), so the production pulse threshold is `pulse_min_mm * flush.radar_rain_scale` (0.848) when radar is on, `* 1.0` with `--no-radar`.
- **E3 Ship gate.** Task 3 compares the flush index (without G_season) with the CURRENT profile's F_loc (without G_season, `rank_F_loc_no_gseason` after re-running `notebooks/03_backtest_gbif.py`, since `soil_moisture_weight` changed on 2026-09-27). Ship (Tasks 4–7) only if the leave-one-year-out held-out mean rank > the baseline mean AND a paired Wilcoxon test on per-find rank differences gives p < 0.10. Otherwise **stop and ask**.
- **E4 Timeline always starts today** (`date.today()`), independent of `--date` (which still only drives F/R's forecast windows).

## Global Constraints

- TDD: failing test first in every code task. Python tests run with no network.
- Tests: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`; frontend in `frontend/`: `npm test`, `npx tsc --noEmit`, `npx vite build`.
- `pipeline/flush.py` must never be imported by `pipeline/orchestrate.py`, `scoring.py`, `mvp.py`, `habitat.py` (Task 4 adds a test). R, H, F, F_loc, `scores_{day}.json` fields do not change.
- Do not change `fruiting.*`, `fruiting_classes`, `pressure.*`, `radar.*` profile values.
- `flush_{day}.json` / `flush.json` is optional everywhere (sync, frontend, saved trips), same pattern as `regions`/`details`: missing = old „Warunki” text, malformed = loud error.
- No personal data in the repo (station coordinates stay in `cache/stations/`).
- User-facing text in Polish; Python prints ASCII-only Polish like the rest of `prepare_trip.py`; JSON/UI strings may use Polish diacritics.
- Final task: full pytest + frontend test/tsc/build, new top note in `docs/CODEX-HANDOFF.md`.

## Review Focus

- Open-Meteo `date` = UTC instant of local midnight — area aggregation must use `tz_convert("Europe/Warsaw")` before `.dt.date` (and accept naive dates from test fakes) — Task 2 test `test_area_daily_weather_uses_local_dates_and_median`.
- Today missing from the weather frame (test fakes in `tests/test_search_area.py` return Aug 2026 data) must skip the timeline with a `UWAGA` line, not crash the whole analysis — Task 4 step 4 runs `tests/test_search_area.py`; Task 2 test `test_build_area_timeline_rejects_missing_today`.
- A frost day must end a wave (intensity 0 from then on, phase not shown), not leave a stale "szczyt" — Task 1 test `test_frost_ends_the_wave`.
- A stale `flush.json` from a previous day/sync must never sit next to fresh scores (sync removes it; saved trips drop it; prepare_trip deletes a same-day file before recomputing) — Task 5 tests.
- Rain still falling today (pulse ends today, DD = NaN) must read "przed_fala" with a peak window of None rather than crash — Task 2 test `test_wave_phase_nan_is_przed_fala` and `test_peak_window_none_without_accumulated_days`.

---

## Task 0: Pre-flight (no code)

- [ ] **Step 1:** `git status` — working tree should only show the long-standing `uv.lock`, `CLAUDE.md`, `frontend/public/`. If anything else is modified, ask before starting.
- [ ] **Step 2:** Confirm E1–E4 with the user in one short message (quote them). Update this section if anything changes.

---

## Task 1: `pipeline/flush.py` core — pulses, thermal clock, intensity

**Files:**
- Create: `pipeline/flush.py`
- Modify: `profiles/boletus_edulis.yaml` (new `flush:` section)
- Test: `tests/test_flush.py`

**Interfaces:**
- Produces: `FlushParams` (frozen dataclass: `wet_day_mm, pulse_min_mm, t_base_c, cold_night_c, cold_night_factor, frost_c, dd_peak, dd_sigma`), `flush_params(profile, rain_scale=1.0) -> FlushParams`, `Pulse` (frozen: `start:int, end:int, rain_mm:float, strength:float`), `detect_pulses(precip, params) -> list[Pulse]`, `degree_days_after(end, tmean, tmin, params) -> np.ndarray` (NaN ≤ end, +inf from first frost day), `wave_intensity(dd, strength, params) -> np.ndarray`, `flush_series(precip, tmean, tmin, params) -> tuple[np.ndarray, list[Pulse], list[np.ndarray]]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_flush.py
import math

import numpy as np
import pytest

from pipeline.flush import (
    FlushParams, Pulse, flush_params, detect_pulses, degree_days_after, wave_intensity, flush_series,
)
from pipeline.habitat import load_profile

PROFILE = load_profile("profiles/boletus_edulis.yaml")
P = FlushParams(wet_day_mm=1.0, pulse_min_mm=15.0, t_base_c=5.0, cold_night_c=5.0,
                cold_night_factor=0.5, frost_c=-1.0, dd_peak=100.0, dd_sigma=20.0)


def test_flush_params_scales_only_the_rain_threshold():
    base = flush_params(PROFILE)
    scaled = flush_params(PROFILE, rain_scale=0.5)
    assert scaled.pulse_min_mm == pytest.approx(base.pulse_min_mm * 0.5)
    assert scaled.dd_peak == base.dd_peak


def test_detect_pulses_merges_across_one_dry_day_and_applies_threshold():
    precip = [0, 5, 0, 12, 0, 0, 20, 0, 8, 0]
    pulses = detect_pulses(precip, P)
    assert pulses == [
        Pulse(start=1, end=3, rain_mm=17.0, strength=pytest.approx(17 / 30)),
        Pulse(start=6, end=8, rain_mm=28.0, strength=pytest.approx(28 / 30)),
    ]


def test_detect_pulses_does_not_merge_across_two_dry_days():
    assert detect_pulses([10, 0, 0, 10], P) == []  # two 10 mm episodes, each below 15


def test_degree_days_after_accumulates_from_the_day_after_the_pulse():
    dd = degree_days_after(1, tmean=[15, 15, 15, 15], tmin=[10, 10, 10, 10], params=P)
    assert math.isnan(dd[0]) and math.isnan(dd[1])
    assert dd[2:].tolist() == [10.0, 20.0]


def test_cold_night_halves_that_days_rate():
    dd = degree_days_after(0, tmean=[15, 15, 15], tmin=[10, 3, 10], params=P)
    assert dd[1:].tolist() == [5.0, 15.0]


def test_frost_ends_the_wave():
    dd = degree_days_after(0, tmean=[15, 15, 15, 15], tmin=[10, 10, -2, 10], params=P)
    assert dd[1] == 10.0 and np.isinf(dd[2]) and np.isinf(dd[3])
    assert wave_intensity(dd, 1.0, P)[2:].tolist() == [0.0, 0.0]


def test_wave_intensity_peaks_at_dd_peak_and_is_zero_before_the_pulse_ends():
    dd = np.array([np.nan, 100.0, 120.0])
    out = wave_intensity(dd, 0.8, P)
    assert out[0] == 0.0
    assert out[1] == pytest.approx(0.8)
    assert out[2] == pytest.approx(0.8 * math.exp(-0.5))


def test_flush_series_takes_the_stronger_of_overlapping_waves():
    precip = [20, 0, 0, 0, 30] + [0] * 15
    tmean, tmin = [15.0] * 20, [10.0] * 20
    index, pulses, dds = flush_series(precip, tmean, tmin, P)
    assert len(pulses) == 2 and len(dds) == 2
    expected = np.maximum(wave_intensity(dds[0], pulses[0].strength, P),
                          wave_intensity(dds[1], pulses[1].strength, P))
    assert index.tolist() == pytest.approx(expected.tolist())
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_flush.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.flush'`.

- [ ] **Step 3: Implement**

`profiles/boletus_edulis.yaml` — new top-level section after `radar:`:

```yaml
flush:
  # Plan 2026-09-27 A2 (docs/superpowers/plans/2026-09-27-borowik-wysyp-a2.md):
  # flush-timing model, pipeline/flush.py. NEVER feeds R. [E] values below
  # are initial; pulse_min_mm/t_base_c/dd_peak/dd_sigma are calibrated in
  # Task 3 on the GBIF backtest (ERA5 rain) -- record the result here.
  wet_day_mm: 1.0
  pulse_min_mm: 15.0          # [E] ERA5 mm; production multiplies by radar_rain_scale
  radar_rain_scale: 0.848     # radar/ERA5 rain ratio, notebooks/05 (note (25))
  t_base_c: 5.0               # [E]
  cold_night_c: 5.0           # [E] tmin below this -> that day's rate * cold_night_factor
  cold_night_factor: 0.5      # [E]
  frost_c: -1.0               # [E] tmin below this ends the wave
  dd_peak: 100.0              # [E] degree-days after the pulse at peak (~10 d at 15 C mean)
  dd_sigma: 35.0              # [E]
  lookback_days: 45
  horizon_days: 7
  max_waves: 2
  level_thresholds: [0.1, 0.3, 0.6]
```

```python
# pipeline/flush.py
"""A2: flush (wysyp) timing model -- plan 2026-09-27
(docs/superpowers/plans/2026-09-27-borowik-wysyp-a2.md).

Rain pulse -> thermal clock (cold nights slow it, frost stops it) ->
Gaussian flush curve in degree-days. Answers "kiedy", never "gdzie":
this module is deliberately NOT imported by pipeline.orchestrate /
scoring / mvp / habitat, so R cannot change because of it."""
import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FlushParams:
    wet_day_mm: float
    pulse_min_mm: float
    t_base_c: float
    cold_night_c: float
    cold_night_factor: float
    frost_c: float
    dd_peak: float
    dd_sigma: float


def flush_params(profile: dict, rain_scale: float = 1.0) -> FlushParams:
    cfg = profile["flush"]
    return FlushParams(
        wet_day_mm=cfg["wet_day_mm"], pulse_min_mm=cfg["pulse_min_mm"] * rain_scale,
        t_base_c=cfg["t_base_c"], cold_night_c=cfg["cold_night_c"],
        cold_night_factor=cfg["cold_night_factor"], frost_c=cfg["frost_c"],
        dd_peak=cfg["dd_peak"], dd_sigma=cfg["dd_sigma"],
    )


@dataclass(frozen=True)
class Pulse:
    start: int
    end: int
    rain_mm: float
    strength: float


def detect_pulses(precip, params: FlushParams) -> list[Pulse]:
    """Episodes of wet days (a single dry day inside allowed) whose total
    reaches pulse_min_mm. Strength 0.5 at the threshold, 1.0 at twice it."""
    p = np.asarray(precip, dtype=float)
    wet = p >= params.wet_day_mm
    pulses, i, n = [], 0, len(p)
    while i < n:
        if not wet[i]:
            i += 1
            continue
        start = end = i
        j = i + 1
        while j < n:
            if wet[j]:
                end = j
                j += 1
            elif j + 1 < n and wet[j + 1]:
                j += 1
            else:
                break
        total = float(p[start:end + 1].sum())
        if total >= params.pulse_min_mm:
            pulses.append(Pulse(start, end, total, min(1.0, total / (2.0 * params.pulse_min_mm))))
        i = end + 1
    return pulses


def degree_days_after(end: int, tmean, tmin, params: FlushParams) -> np.ndarray:
    """Thermal time accumulated on the days AFTER the pulse's last wet day:
    NaN up to and including `end`, +inf from the first frost day on."""
    tmean = np.asarray(tmean, dtype=float)
    tmin = np.asarray(tmin, dtype=float)
    dd = np.full(len(tmean), np.nan)
    total = 0.0
    for k in range(end + 1, len(tmean)):
        if tmin[k] < params.frost_c:
            dd[k:] = np.inf
            break
        rate = max(0.0, tmean[k] - params.t_base_c)
        if tmin[k] < params.cold_night_c:
            rate *= params.cold_night_factor
        total += rate
        dd[k] = total
    return dd


def wave_intensity(dd: np.ndarray, strength: float, params: FlushParams) -> np.ndarray:
    z = (np.asarray(dd, dtype=float) - params.dd_peak) / params.dd_sigma
    with np.errstate(invalid="ignore"):
        out = strength * np.exp(-0.5 * z * z)
    return np.nan_to_num(out, nan=0.0)


def flush_series(precip, tmean, tmin, params: FlushParams):
    """Daily flush index (max over waves) + the pulses and their thermal clocks."""
    pulses = detect_pulses(precip, params)
    dds = [degree_days_after(p.end, tmean, tmin, params) for p in pulses]
    index = np.zeros(len(np.asarray(precip)))
    for pulse, dd in zip(pulses, dds):
        index = np.maximum(index, wave_intensity(dd, pulse.strength, params))
    return index, pulses, dds
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_flush.py -q -p no:cacheprovider`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/flush.py profiles/boletus_edulis.yaml tests/test_flush.py
git commit -m "feat: flush model core -- rain pulses, thermal clock, wave intensity (plan A2 task 1)"
```

---

## Task 2: Phases, peak window, area timeline

**Files:**
- Modify: `pipeline/flush.py` (append)
- Test: `tests/test_flush.py` (append)

**Interfaces:**
- Consumes: Task 1.
- Produces: `PHASE_LABELS: dict[str, str]`, `wave_phase(dd_today: float, params) -> str`, `peak_window(dd, dates: list[date], params) -> tuple[date, date] | None`, `fmt_day_range(a: date, b: date) -> str`, `area_daily_weather(daily: pd.DataFrame, points) -> pd.DataFrame` (index = local `date`, columns `precipitation_mm, tmean_c, tmin_c`), `timeline_summary(waves: list[dict], pulse_min_mm: float) -> str`, `build_area_timeline(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> dict` with keys `generated_for, horizon_days, pulse_min_mm, waves, days, summary` (raises `ValueError` when `today` is not in `area.index`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_flush.py (append)
from datetime import date, timedelta

import pandas as pd

from pipeline.flush import (
    PHASE_LABELS, wave_phase, peak_window, fmt_day_range, area_daily_weather,
    timeline_summary, build_area_timeline,
)


@pytest.mark.parametrize("dd,phase", [
    (50.0, "przed_fala"), (70.0, "poczatek"), (95.0, "szczyt"), (110.0, "szczyt"),
    (125.0, "starzeje_sie"), (150.0, "po_fali"), (math.inf, "po_fali"),
])
def test_wave_phase_boundaries(dd, phase):
    assert wave_phase(dd, P) == phase  # peak 100, sigma 20


def test_wave_phase_nan_is_przed_fala():
    assert wave_phase(float("nan"), P) == "przed_fala"


D0 = date(2026, 9, 20)


def _dates(n):
    return [D0 + timedelta(days=k) for k in range(n)]


def test_peak_window_from_series_and_by_extrapolation():
    tmean, tmin = [15.0] * 12, [10.0] * 12  # 10 DD/day from day 1
    full = degree_days_after(0, tmean, tmin, P)
    assert peak_window(full, _dates(12), P) == (D0 + timedelta(days=9), D0 + timedelta(days=11))
    short = degree_days_after(0, tmean[:5], tmin[:5], P)
    assert peak_window(short, _dates(5), P) == (D0 + timedelta(days=9), D0 + timedelta(days=11))


def test_peak_window_none_without_accumulated_days_or_after_frost():
    assert peak_window(np.array([np.nan, np.nan]), _dates(2), P) is None
    frost = degree_days_after(0, [15, 15, 15], [10, -5, 10], P)
    assert peak_window(frost, _dates(3), P) is None


def test_fmt_day_range():
    assert fmt_day_range(date(2026, 9, 21), date(2026, 9, 23)) == "21–23.09"
    assert fmt_day_range(date(2026, 9, 30), date(2026, 10, 2)) == "30.09–2.10"
    assert fmt_day_range(date(2026, 9, 11), date(2026, 9, 11)) == "11.09"


def test_area_daily_weather_uses_local_dates_and_median():
    utc_midnights = pd.to_datetime(["2026-09-20 22:00", "2026-09-21 22:00"], utc=True)  # local 21.09, 22.09
    rows = []
    for (lat, lon), mm in [((50.0, 21.0), 10.0), ((50.1, 21.1), 20.0), ((50.2, 21.2), 30.0), ((60.0, 10.0), 99.0)]:
        for d in utc_midnights:
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": mm, "tmean_c": 12.0, "tmin_c": 6.0})
    area = area_daily_weather(pd.DataFrame(rows), [(50.0, 21.0), (50.1, 21.1), (50.2, 21.2)])
    assert list(area.index) == [date(2026, 9, 21), date(2026, 9, 22)]
    assert area["precipitation_mm"].tolist() == [20.0, 20.0]  # (60, 10) not in points -> excluded


def _area(precip, tmean=15.0, tmin=10.0, start=D0):
    idx = [start + timedelta(days=k) for k in range(len(precip))]
    return pd.DataFrame({"precipitation_mm": precip, "tmean_c": tmean, "tmin_c": tmin}, index=idx)


def _profile(**overrides):
    flush = {**PROFILE["flush"], "pulse_min_mm": 15.0, "dd_peak": 100.0, "dd_sigma": 20.0,
             "t_base_c": 5.0, "cold_night_c": 5.0, **overrides}
    return {**PROFILE, "flush": flush}


def test_build_area_timeline_reports_upcoming_wave_and_seven_tiles():
    precip = [0.0] * 3 + [30.0] + [0.0] * 20   # pulse on 23.09, then 10 DD/day
    today = date(2026, 9, 26)                   # 3 days after -> DD 30 -> przed_fala
    out = build_area_timeline(_area(precip), today, _profile())
    assert out["generated_for"] == "2026-09-26"
    assert [d["date"] for d in out["days"]] == [(today + timedelta(days=k)).isoformat() for k in range(7)]
    assert out["days"][0]["forecast"] is False and all(d["forecast"] for d in out["days"][1:])
    assert all(0 <= d["level"] <= 3 for d in out["days"])
    (wave,) = out["waves"]
    assert wave["phase"] == "przed_fala" and wave["rain_start"] == wave["rain_end"] == "2026-09-23"
    assert (wave["peak_from"], wave["peak_to"]) == ("2026-10-02", "2026-10-04")
    assert out["summary"] == "Fala po deszczu 23.09: grzyby dopiero rosną, szczyt ok. 2–4.10"


def test_build_area_timeline_without_pulses_says_so():
    out = build_area_timeline(_area([0.0] * 20), date(2026, 9, 26), _profile())
    assert out["waves"] == []
    assert out["summary"].startswith("Brak świeżej fali po większym deszczu")
    assert all(d["level"] == 0 for d in out["days"])


def test_build_area_timeline_rejects_missing_today():
    with pytest.raises(ValueError):
        build_area_timeline(_area([0.0] * 5), date(2026, 12, 1), _profile())


def test_timeline_summary_lists_the_older_wave_second():
    waves = [
        {"rain_start": "2026-09-21", "rain_end": "2026-09-23", "phase": "poczatek",
         "phase_label": PHASE_LABELS["poczatek"], "peak_from": "2026-10-01", "peak_to": "2026-10-03"},
        {"rain_start": "2026-09-11", "rain_end": "2026-09-12", "phase": "starzeje_sie",
         "phase_label": PHASE_LABELS["starzeje_sie"], "peak_from": "2026-09-22", "peak_to": "2026-09-24"},
    ]
    assert timeline_summary(waves, 12.7) == (
        "Fala po deszczu 21–23.09: początek wysypu, szczyt ok. 1–3.10"
        " · starsza fala po deszczu 11–12.09: fala się starzeje")
```

(Check of the expected peak in `test_build_area_timeline_reports_upcoming_wave_and_seven_tiles`: pulse ends 23.09, 10 DD/day → DD 90 (= peak−0.5σ) on 2.10 and DD 110 on 4.10.)

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_flush.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'PHASE_LABELS'`.

- [ ] **Step 3: Implement (append to `pipeline/flush.py`; add `from datetime import date, timedelta`, `import pandas as pd` and `from pipeline.phenology import compute_g_season` to the imports)**

```python
PHASE_LABELS = {
    "przed_fala": "grzyby dopiero rosną",
    "poczatek": "początek wysypu",
    "szczyt": "szczyt wysypu",
    "starzeje_sie": "fala się starzeje",
    "po_fali": "po fali",
}


def wave_phase(dd_today: float, params: FlushParams) -> str:
    if math.isnan(dd_today):
        return "przed_fala"  # rain still falling today: the clock has not started
    peak, sigma = params.dd_peak, params.dd_sigma
    if dd_today < peak - 2 * sigma:
        return "przed_fala"
    if dd_today < peak - 0.5 * sigma:
        return "poczatek"
    if dd_today <= peak + 0.5 * sigma:
        return "szczyt"
    if dd_today <= peak + 2 * sigma:
        return "starzeje_sie"
    return "po_fali"  # also +inf after frost


def peak_window(dd: np.ndarray, dates: list, params: FlushParams):
    """Dates when thermal time crosses peak -/+ 0.5 sigma. Past the end of
    the series: extrapolated with the mean daily rate of the last <=7
    accumulated days. None after frost or before any day accumulated."""
    dd = np.asarray(dd, dtype=float)
    if np.isinf(dd).any():
        return None
    finite = np.flatnonzero(np.isfinite(dd))
    if len(finite) == 0:
        return None
    last = finite[-1]
    k = min(7, len(finite))
    base = dd[finite[-k - 1]] if len(finite) > k else 0.0
    rate = (dd[last] - base) / k

    def crossing(threshold):
        hits = finite[dd[finite] >= threshold]
        if len(hits):
            return dates[hits[0]]
        if rate <= 0:
            return None
        return dates[last] + timedelta(days=math.ceil((threshold - dd[last]) / rate))

    lo = crossing(params.dd_peak - 0.5 * params.dd_sigma)
    hi = crossing(params.dd_peak + 0.5 * params.dd_sigma)
    return (lo, hi) if lo is not None and hi is not None else None


def fmt_day_range(a: date, b: date) -> str:
    if a == b:
        return f"{a.day}.{a.month:02d}"
    if a.month == b.month:
        return f"{a.day}–{b.day}.{b.month:02d}"
    return f"{a.day}.{a.month:02d}–{b.day}.{b.month:02d}"


def area_daily_weather(daily: pd.DataFrame, points) -> pd.DataFrame:
    """Per-LOCAL-day median over `points` (Open-Meteo `date` is the UTC
    instant of local midnight; naive dates from test fakes are taken as-is)."""
    wanted = set(points)
    sel = daily[[(la, lo) in wanted for la, lo in zip(daily["lat"], daily["lon"])]]
    dates = sel["date"]
    local = (dates.dt.tz_convert("Europe/Warsaw") if dates.dt.tz is not None else dates).dt.date
    return (sel.assign(local_date=local)
            .groupby("local_date")[["precipitation_mm", "tmean_c", "tmin_c"]].median()
            .sort_index()
            .rename_axis("date"))


def timeline_summary(waves: list[dict], pulse_min_mm: float) -> str:
    if not waves:
        return (f"Brak świeżej fali po większym deszczu (≥ {pulse_min_mm:.0f} mm) "
                "— wysyp mało prawdopodobny")
    parts = []
    for i, w in enumerate(waves):
        rain = fmt_day_range(date.fromisoformat(w["rain_start"]), date.fromisoformat(w["rain_end"]))
        text = f"{'Fala' if i == 0 else 'starsza fala'} po deszczu {rain}: {w['phase_label']}"
        if w["phase"] in ("przed_fala", "poczatek") and w["peak_from"]:
            peak = fmt_day_range(date.fromisoformat(w["peak_from"]), date.fromisoformat(w["peak_to"]))
            text += f", szczyt ok. {peak}"
        parts.append(text)
    return " · ".join(parts)


def build_area_timeline(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> dict:
    cfg = profile["flush"]
    params = flush_params(profile, rain_scale)
    horizon = cfg["horizon_days"]
    area = area[area.index <= today + timedelta(days=horizon - 1)]
    dates = list(area.index)
    if today not in dates:
        raise ValueError(f"brak danych pogodowych dla {today.isoformat()}")
    t = dates.index(today)
    index, pulses, dds = flush_series(area["precipitation_mm"].to_numpy(), area["tmean_c"].to_numpy(),
                                      area["tmin_c"].to_numpy(), params)
    seasonal = index * np.array([compute_g_season(d.timetuple().tm_yday, profile) for d in dates])
    days = []
    for k in range(t, min(t + horizon, len(dates))):
        value = float(seasonal[k])
        days.append({"date": dates[k].isoformat(), "index": round(value, 3),
                     "level": int(sum(value >= th for th in cfg["level_thresholds"])), "forecast": k > t})
    waves = []
    for pulse, dd in sorted(zip(pulses, dds), key=lambda x: -x[0].end):
        if pulse.end > t or (today - dates[pulse.end]).days > cfg["lookback_days"]:
            continue
        phase = wave_phase(float(dd[t]), params)
        if phase == "po_fali":
            continue
        window = peak_window(dd, dates, params)
        waves.append({
            "rain_start": dates[pulse.start].isoformat(), "rain_end": dates[pulse.end].isoformat(),
            "rain_mm": round(pulse.rain_mm, 1), "strength": round(pulse.strength, 2),
            "phase": phase, "phase_label": PHASE_LABELS[phase],
            "peak_from": window[0].isoformat() if window else None,
            "peak_to": window[1].isoformat() if window else None,
        })
        if len(waves) == cfg["max_waves"]:
            break
    return {"generated_for": today.isoformat(), "horizon_days": horizon,
            "pulse_min_mm": round(params.pulse_min_mm, 1), "waves": waves, "days": days,
            "summary": timeline_summary(waves, params.pulse_min_mm)}
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_flush.py -q -p no:cacheprovider`
Expected: 24 passed (8 from Task 1 + 7 parametrized + 9).

- [ ] **Step 5: Commit**

```bash
git add pipeline/flush.py tests/test_flush.py
git commit -m "feat: flush phases, peak window and area timeline (plan A2 task 2)"
```

---

## Task 3: Calibration on GBIF + field check (SHIP GATE)

**Files:**
- Create: `notebooks/06_backtest_flush.py`, `notebooks/07_flush_field_check.py`
- Modify: `profiles/boletus_edulis.yaml` (`flush:` calibrated values), `notebooks/output/backtest_gbif_results.csv` is regenerated (gitignored)

- [ ] **Step 1: Fresh baseline with the current profile**

Run: `.venv/Scripts/python.exe notebooks/03_backtest_gbif.py` (cache-only; `MAX_YEAR` caps it to cached years — if it tries the network and fails, stop and report). Record "F_loc bez G_season" mean/median from its printed report — this is the E3 baseline (the old 0.620 was computed before `soil_moisture_weight: 0.0`).
Known caveat, do not fix in this plan: notebook 03 takes day-of-year from the UTC timestamp of local midnight (22:00 UTC the previous day), so its F series is shifted by one day relative to the find date; notebook 06 below uses local dates. F varies smoothly day to day, so the baseline is barely affected — mention it in the handoff note next to the numbers.

- [ ] **Step 2: Calibration notebook**

```python
# notebooks/06_backtest_flush.py
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
```

Run: `.venv/Scripts/python.exe notebooks/06_backtest_flush.py` (144 combos × 90 finds; a few minutes, no network).

- [ ] **Step 3: Apply the gate (E3)**

If the last line says `NIEZALICZONA`: **stop**, report the printed table to the user and ask (options: widen the grid, add a moisture-state condition to pulses, or keep A2 as an experimental notebook only). Do not start Task 4.
If `ZALICZONA`: write the "najlepsze na calosci" values into `profiles/boletus_edulis.yaml` `flush:` (`pulse_min_mm`, `dd_peak`, `dd_sigma`, `t_base_c`), replacing their `[E]` comments with `# calibrated plan A2 Task 3 (GBIF, LOYO held-out mean X.XXX vs baseline Y.YYY, p=Z)`.

- [ ] **Step 4: Field check against the 2026-09-26 observation**

```python
# notebooks/07_flush_field_check.py
"""Plan A2 Task 3: does the calibrated model agree with the 2026-09-26
field visit near rejon 1 (old mushrooms from the ~11.09 wave, a few small
ones after 21-23.09)? Uses the production path (radar + Open-Meteo, cache).
Run: .venv/Scripts/python.exe notebooks/07_flush_field_check.py"""
import functools
import json
import pathlib
from datetime import date

from pipeline.flush import area_daily_weather, build_area_timeline
from pipeline.habitat import load_profile
from pipeline.orchestrate import WEATHER_GRID_SPACING_M
from pipeline.prepare_trip import _radius_scaled_spacing, build_weather_fetcher, points_within_radius
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import fetch_weather_raw, make_grid

LAT, LON, RADIUS_KM = 50.0555, 21.7889, 20.0


def main():
    profile = load_profile("profiles/boletus_edulis.yaml")
    spacing = _radius_scaled_spacing(WEATHER_GRID_SPACING_M, RADIUS_KM)
    grid = make_grid(tile_bbox_2180(LAT, LON, size_km=2 * RADIUS_KM), spacing_m=spacing)
    points = points_within_radius(grid, LAT, LON, RADIUS_KM)
    fetcher = build_weather_fetcher(functools.partial(fetch_weather_raw, cache_dir=pathlib.Path("cache")),
                                    use_radar=True, profile=profile, grid_spacing_m=spacing,
                                    cache_dir=pathlib.Path("cache"))
    daily = fetcher(points, 92, forecast_days=profile["flush"]["horizon_days"])
    area = area_daily_weather(daily, points)
    for day in [date(2026, 9, 20), date(2026, 9, 26), date.today()]:
        out = build_area_timeline(area, day, profile, rain_scale=profile["flush"]["radar_rain_scale"])
        print(day, "|", out["summary"])
        print("   ", json.dumps(out["waves"], ensure_ascii=False))


if __name__ == "__main__":
    main()
```

This notebook depends on `points_within_radius` from Task 4 — run it right after Task 4 Step 3, then come back here. Accept when, for 2026-09-26, the wave with rain around 11–12.09 is `szczyt` or `starzeje_sie` (user found old mushrooms) and the 21–23.09 wave is `przed_fala` or `poczatek`. If not, report both lines to the user before continuing (the GBIF gate is the primary criterion; this is a sanity check, not a second optimisation target — do not re-tune to fit one visit).

- [ ] **Step 5: Commit**

```bash
git add notebooks/06_backtest_flush.py notebooks/07_flush_field_check.py profiles/boletus_edulis.yaml
git commit -m "feat: calibrate flush model on GBIF backtest (plan A2 task 3)"
```

---

## Task 4: Export + `prepare_trip` wiring

**Files:**
- Modify: `pipeline/export.py`, `pipeline/prepare_trip.py`
- Test: `tests/test_export.py`, `tests/test_prepare_trip.py`, `tests/test_flush.py` (structural test)

**Interfaces:**
- Consumes: `build_area_timeline`, `area_daily_weather` (Task 2), `build_weather_fetcher` (existing, `pipeline/prepare_trip.py`).
- Produces: `write_flush_json(timeline: dict, day: str, out_path) -> pathlib.Path` (adds `"day"`), `points_within_radius(points, lat, lon, radius_km) -> list[tuple[float, float]]`, `summary["flush_path"]` (str or None).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_export.py (append)
import json

from pipeline.export import write_flush_json


def test_write_flush_json_adds_day_and_writes_strict_json(tmp_path):
    timeline = {"generated_for": "2026-09-27", "horizon_days": 7, "pulse_min_mm": 12.7,
                "waves": [], "days": [{"date": "2026-09-27", "index": 0.1, "level": 1, "forecast": False}],
                "summary": "Brak świeżej fali"}
    path = write_flush_json(timeline, "2026-09-27", tmp_path / "flush_2026-09-27.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["day"] == "2026-09-27" and data["summary"] == "Brak świeżej fali"
```

```python
# tests/test_prepare_trip.py (append)
def test_points_within_radius_keeps_only_points_inside_the_circle():
    import pipeline.prepare_trip as trip
    center = (50.0555, 21.7889)
    near = (50.0555, 21.80)      # ~0.8 km east
    far = (50.40, 21.7889)       # ~38 km north
    assert trip.points_within_radius([near, far], *center, 20.0) == [near]
```

```python
# tests/test_flush.py (append)
import pathlib


def test_flush_is_never_imported_by_the_scoring_path():
    # Structural guarantee that the flush model cannot change R (plan A2).
    for name in ["orchestrate", "scoring", "mvp", "habitat"]:
        src = pathlib.Path(f"pipeline/{name}.py").read_text(encoding="utf-8")
        assert "pipeline.flush" not in src and "from pipeline import flush" not in src, name
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py tests/test_prepare_trip.py tests/test_flush.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'write_flush_json'` / `AttributeError: points_within_radius` (the structural test passes already; it is a guard, keep it).

- [ ] **Step 3: Implement**

`pipeline/export.py` (after `write_regions_json`):

```python
def write_flush_json(timeline: dict, day: str, out_path) -> pathlib.Path:
    """Plan A2: area flush timeline (pipeline.flush.build_area_timeline),
    optional on the frontend like regions/details."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"day": day, **timeline}, ensure_ascii=False, indent=2, allow_nan=False),
                        encoding="utf-8")
    return out_path
```

`pipeline/prepare_trip.py`:
- imports: `from pyproj import Transformer`, `from pipeline.flush import area_daily_weather, build_area_timeline`, and add `write_flush_json` to the existing `from pipeline.export import (...)`.
- module level (next to `build_weather_fetcher`):

```python
_WGS84_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def points_within_radius(points, lat: float, lon: float, radius_km: float) -> list[tuple[float, float]]:
    """Weather grid points inside the search circle (plan A2: the area
    timeline is the median over exactly these points)."""
    cx, cy = _WGS84_TO_2180.transform(lon, lat)
    out = []
    for p_lat, p_lon in points:
        x, y = _WGS84_TO_2180.transform(p_lon, p_lat)
        if math.hypot(x - cx, y - cy) <= radius_km * 1000.0:
            out.append((p_lat, p_lon))
    return out
```

- in `run_trip_preparation`: build the fetcher once and reuse it —

```python
    weather_fetcher = build_weather_fetcher(
        functools.partial(fetch_weather_raw, call_api=_weather_call_api, cache_dir=cache_dir),
        use_radar=use_radar, profile=profile, grid_spacing_m=grid_spacing_m, cache_dir=cache_dir,
    )
```

and pass `weather_fetcher=weather_fetcher` to `run_poc` (replacing the inline `build_weather_fetcher(...)` call). Right after the `run_poc` result prints, add:

```python
    # Plan A2: one area-wide flush timeline (today..today+6). Never feeds R.
    flush_out = out_dir / f"flush_{day}.json"
    flush_out.unlink(missing_ok=True)
    flush_path = None
    flush_points = points_within_radius(make_grid(bbox, spacing_m=grid_spacing_m), lat, lon, radius_km)
    flush_daily = weather_fetcher(flush_points, 92, forecast_days=profile["flush"]["horizon_days"])
    rain_scale = profile["flush"]["radar_rain_scale"] if use_radar and profile["radar"]["enabled"] else 1.0
    try:
        timeline = build_area_timeline(area_daily_weather(flush_daily, flush_points), date.today(), profile,
                                       rain_scale=rain_scale)
    except ValueError as exc:
        print(f"UWAGA: os wysypu pominieta ({exc}).", flush=True)
    else:
        flush_path = write_flush_json(timeline, day, flush_out)
        print(f"Wysyp: {timeline['summary']}", flush=True)
```

(`out_dir`, `bbox`, `grid_spacing_m`, `day`, `lat`, `lon`, `radius_km` already exist in `run_trip_preparation`; check the exact variable name used there for the output directory — the function parameter is `out_dir` — and that `date` is imported from `datetime` at the top, which it is.) Add `"flush_path": str(flush_path) if flush_path else None,` to the summary dict.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all pass. `tests/test_search_area.py`'s fakes return August data, so their runs must take the `UWAGA: os wysypu pominieta` path and still pass; if they fail instead, fix the code path (not the fakes).

Then run the field-check notebook from Task 3 Step 4 and finish that step.

- [ ] **Step 5: Commit**

```bash
git add pipeline/export.py pipeline/prepare_trip.py tests/test_export.py tests/test_prepare_trip.py tests/test_flush.py
git commit -m "feat: export area flush timeline from prepare_trip (plan A2 task 4)"
```

---

## Task 5: `sync-data` + saved trips carry `flush.json`

**Files:**
- Modify: `frontend/scripts/sync-data.mjs`, `frontend/scripts/sync-data.test.mjs`, `launcher/trip_archive.py`, `tests/test_trip_archive.py`

**Interfaces:**
- Produces: `syncData(...)` result gains `flush: 0 | 1`; `flush_{day}.json` → `public/data/flush.json` (validated: JSON object, `day === day`, `Array.isArray(days)`); stale `flush.json` removed; `TRIP_FILES` includes `"flush.json"`.

- [ ] **Step 1: Write the failing tests**

In `frontend/scripts/sync-data.test.mjs`, change the expected object of `"copies one complete same-day bundle"` to include `flush: 0`, and append:

```js
// Plan A2: flush_{day}.json -> flush.json, optional like regions/details.
const flushFile = (day = "2026-09-24") =>
  JSON.stringify({ day, summary: "Fala po deszczu 21–23.09: początek wysypu", days: [], waves: [] });

it("syncs a same-day flush file alongside scores and geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "flush_2026-09-24.json"), flushFile());
  const result = await syncData(source, target);
  expect(result.flush).toBe(1);
  expect(JSON.parse(await readFile(path.join(target, "flush.json"), "utf8")).summary).toContain("Fala");
});

it("rejects a same-day flush file from another day or malformed", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "flush_2026-09-24.json"), flushFile("2026-09-23"));
  await expect(syncData(source, target)).rejects.toThrow();
  await writeFile(path.join(source, "flush_2026-09-24.json"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
});

it("removes a stale flush.json from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "flush_2026-09-24.json"), flushFile());
  await syncData(source, target);
  await rm(path.join(source, "flush_2026-09-24.json"));
  const result = await syncData(source, target);
  expect(result.flush).toBe(0);
  await expect(readFile(path.join(target, "flush.json"), "utf8")).rejects.toThrow();
});
```

```python
# tests/test_trip_archive.py (append)
def test_resave_without_flush_removes_old_flush_snapshot(tmp_path):
    data, dest = tmp_path / "data", tmp_path / "trip"
    data.mkdir()
    for name in ["scores.json", "stands.geojson"]:
        (data / name).write_text("{}", encoding="utf-8")
    dest.mkdir()
    (dest / "flush.json").write_text("old-flush", encoding="utf-8")
    copied = copy_trip_files(data, dest)
    assert "flush.json" not in copied
    assert not (dest / "flush.json").exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm test` and `.venv/Scripts/python.exe -m pytest tests/test_trip_archive.py -q -p no:cacheprovider`
Expected: FAIL (no `flush` in result; old `flush.json` not removed).

- [ ] **Step 3: Implement**

`frontend/scripts/sync-data.mjs` — after the details block, before `await mkdir(target, ...)`:

```js
  // Plan A2: flush_{day}.json is optional too (area flush timeline).
  let flushRaw = null;
  try {
    flushRaw = await readFile(path.join(source, `flush_${day}.json`), "utf8");
  } catch {
    flushRaw = null;
  }
  let flush = null;
  if (flushRaw !== null) {
    try {
      flush = JSON.parse(flushRaw);
    } catch {
      throw new Error(`Plik flush_${day}.json jest uszkodzony.`);
    }
    if (!flush || typeof flush !== "object" || flush.day !== day || !Array.isArray(flush.days))
      throw new Error(`Niepoprawny format flush_${day}.json.`);
  }
```

then next to the details push: `if (flush !== null) { targets.push("flush.json"); allContents.push(flushRaw); }`, next to the details `rm`: `if (flush === null) await rm(path.join(target, "flush.json"), { force: true });`, and add `flush: flush === null ? 0 : 1,` to the returned object.

`launcher/trip_archive.py`: `TRIP_FILES = ["scores.json", "stands.geojson", "regions.json", "details.json", "flush.json"]`.

- [ ] **Step 4: Run to verify they pass**

Run: `cd frontend && npm test` and `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/sync-data.mjs frontend/scripts/sync-data.test.mjs launcher/trip_archive.py tests/test_trip_archive.py
git commit -m "feat: sync and archive optional flush.json (plan A2 task 5)"
```

---

## Task 6: Frontend — timeline in „Warunki”

**Files:**
- Modify: `frontend/src/model.ts`, `frontend/src/model.test.ts`, `frontend/src/main.ts`, `frontend/src/style.css`

**Interfaces:**
- Produces: types `FlushDay`, `FlushWave`, `FlushTimeline`; `parseFlush(raw: unknown, day: string | undefined): FlushTimeline | null`; `dayLabel(dateIso: string, position: number): string`; `loadData()` result gains `flush: FlushTimeline | null`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/model.test.ts (append; add parseFlush, dayLabel to the import from "./model")
describe("flush timeline", () => {
  const flush = (over: Record<string, unknown> = {}) => ({
    day: "2026-09-27",
    generated_for: "2026-09-27",
    horizon_days: 7,
    summary: "Fala po deszczu 21–23.09: początek wysypu, szczyt ok. 1–3.10",
    waves: [],
    days: [{ date: "2026-09-27", index: 0.2, level: 1, forecast: false }],
    ...over,
  });
  it("returns null when flush.json is absent", () => {
    expect(parseFlush(undefined, "2026-09-27")).toBeNull();
  });
  it("accepts a valid same-day timeline", () => {
    expect(parseFlush(flush(), "2026-09-27")?.summary).toContain("początek");
  });
  it("rejects another day's timeline or malformed tiles", () => {
    expect(() => parseFlush(flush(), "2026-09-26")).toThrow();
    expect(() =>
      parseFlush(flush({ days: [{ date: "2026-09-27", index: 0.2, level: 7, forecast: false }] }), "2026-09-27"),
    ).toThrow();
  });
  it("labels today and Polish weekdays", () => {
    expect(dayLabel("2026-09-27", 0)).toBe("dziś");
    expect(dayLabel("2026-09-28", 1)).toBe("pn");
    expect(dayLabel("2026-10-03", 6)).toBe("sb");
  });
});
```

(If `describe` is not already imported from `vitest` in this file, add it to the existing vitest import.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — `parseFlush` / `dayLabel` not exported.

- [ ] **Step 3: Implement**

`frontend/src/model.ts` (near the other exported types/parsers):

```ts
export type FlushDay = { date: string; index: number; level: 0 | 1 | 2 | 3; forecast: boolean };
export type FlushWave = {
  rain_start: string;
  rain_end: string;
  rain_mm: number;
  phase: string;
  phase_label: string;
  peak_from: string | null;
  peak_to: string | null;
};
export type FlushTimeline = {
  day: string;
  generated_for: string;
  horizon_days: number;
  summary: string;
  waves: FlushWave[];
  days: FlushDay[];
};

function isFlushDay(value: unknown): value is FlushDay {
  const d = value as Record<string, unknown> | null;
  return (
    !!d &&
    typeof d.date === "string" &&
    typeof d.index === "number" &&
    Number.isFinite(d.index) &&
    [0, 1, 2, 3].includes(d.level as number) &&
    typeof d.forecast === "boolean"
  );
}

export function parseFlush(raw: unknown, day: string | undefined): FlushTimeline | null {
  if (raw === undefined) return null;
  const f = raw as Record<string, unknown> | null;
  if (
    !f ||
    typeof f !== "object" ||
    f.day !== day ||
    typeof f.summary !== "string" ||
    !Array.isArray(f.waves) ||
    !Array.isArray(f.days) ||
    !f.days.every(isFlushDay)
  )
    throw new Error("Plik flush.json jest niepoprawny. Uruchom synchronizację danych.");
  return f as unknown as FlushTimeline;
}

const WEEKDAYS = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];
export function dayLabel(dateIso: string, position: number): string {
  if (position === 0) return "dziś";
  return WEEKDAYS[new Date(`${dateIso}T12:00:00`).getDay()];
}
```

In `loadData`, after the details block, fetch `flush.json` with the same optional pattern (`flushResponse?.ok` → `response.json()`, parse error → `throw new Error("Plik flush.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.")`), then replace the final return with:

```ts
  const parsed = parseData(scoresRaw, standsRaw, regionsRaw, detailsRaw);
  return { ...parsed, flush: parseFlush(flushRaw, parsed.scores[0]?.day) };
```

`frontend/src/main.ts`: add the `FlushTimeline` type and `dayLabel` to the existing import from `./model`; add

```ts
function conditionsHtml(median: number | null, flush: FlushTimeline | null): string {
  const moisture = fruitingClass(median).toLocaleLowerCase("pl");
  if (!flush)
    return `<span class="condition-symbol">${icon("leaf")}</span><div><strong>Warunki w obszarze: ${moisture}</strong><p>Ocena pogody z analizy · mediana dla wydzieleń przechodzących filtry</p></div><span class="model-label">MODEL EKSPERCKI · NIESKALIBROWANY</span>`;
  const tiles = flush.days
    .map(
      (d, i) =>
        `<li class="flush-day level-${d.level}${d.forecast ? " forecast" : ""}" title="${escape(formatDate(d.date))}: ${Math.round(d.index * 100)}/100"><span>${dayLabel(d.date, i)}</span><b aria-label="poziom ${d.level} z 3">${"●".repeat(d.level)}${"○".repeat(3 - d.level)}</b></li>`,
    )
    .join("");
  return `<span class="condition-symbol">${icon("mushroom")}</span><div><strong>${escape(flush.summary)}</strong><p>Warunki wilgotności: ${moisture} · wysyp liczony od opadów z radaru i temperatur (także nocnych), kolejne dni z prognozy</p><ol class="flush-days" aria-label="Szansa na wysyp w kolejnych dniach">${tiles}</ol></div><span class="model-label">MODEL EKSPERCKI · NIESKALIBROWANY</span>`;
}
```

and replace the success-path `$("#conditions").innerHTML = ...` (currently ~line 615) with `$("#conditions").innerHTML = conditionsHtml(median, data.flush);`. (`escape`, `formatDate`, `icon`, `fruitingClass` already exist in `main.ts`.)

`frontend/src/style.css` (append):

```css
.flush-days { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; margin: 8px 0 0; padding: 0; }
.flush-day { display: flex; flex-direction: column; align-items: center; min-width: 40px; padding: 4px 6px; border-radius: 8px; background: rgba(127, 127, 127, 0.08); font-size: 12px; }
.flush-day b { font-weight: 400; letter-spacing: 1px; }
.flush-day.level-2 { background: rgba(46, 125, 50, 0.12); }
.flush-day.level-3 { background: rgba(46, 125, 50, 0.22); }
.flush-day.forecast span { font-style: italic; }
```

- [ ] **Step 4: Run to verify they pass**

Run (in `frontend/`): `npm test`, `npx tsc --noEmit`, `npx vite build`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/model.ts frontend/src/model.test.ts frontend/src/main.ts frontend/src/style.css
git commit -m "feat: flush timeline in the conditions bar (plan A2 task 6)"
```

---

## Task 7: Real run, visual check, docs, final verification

**Files:**
- Modify: `docs/CODEX-HANDOFF.md`, `frontend/README.md`

- [ ] **Step 1: Real run + sync**

```bash
.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 50.0555 --lon 21.7889 --radius-km 20
cd frontend && npm run sync-data
```

Expected: a `Wysyp: ...` line, `notebooks/output/flush_{today}.json` written, sync prints success and `public/data/flush.json` exists. Record the summary sentence and the 7 levels.

- [ ] **Step 2: Visual check**

`npm run dev` in `frontend/`, open the page, check: summary sentence in the „Warunki” bar, 7 tiles (first "dziś", weekday labels, dots), no layout break on a narrow window (~375 px). If the browser tool cannot reach localhost (seen before, note (21)), say so in the handoff and rely on `vite build` + tests.

- [ ] **Step 3: Docs**

`frontend/README.md`: one paragraph "Oś wysypu" — what the tiles mean (poziom 0–3 szansy na wysyp z modelu fazy fali, nie prawdopodobieństwo zbioru), that the first day is today, later days use the temperature forecast, and that `flush.json` is optional.
`docs/CODEX-HANDOFF.md`: new top note "(27): A2 — model fazy wysypu" — model, calibrated parameters and the GBIF table (held-out mean vs baseline, p, per-year chosen params), field-check lines for 20.09/26.09/today, real-run summary, test counts, open items (per-region timelines — E1; soil-water state as a pulse condition; B pressure from forest tracks still pending).

- [ ] **Step 4: Final verification**

```bash
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
cd frontend && npm test && npx tsc --noEmit && npx vite build
git diff --check
```

Expected: all green; put exact counts in the handoff note.

- [ ] **Step 5: Commit**

```bash
git add docs/CODEX-HANDOFF.md frontend/README.md
git commit -m "docs: record A2 flush model, calibration and real-run results"
```
