# A2: model fazy wysypu (oś czasu na 7 dni) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer "kiedy jechać": detect rain pulses, run a thermal clock (with cold-night slowdown and frost stop) from each pulse, turn it into a flush-intensity curve, and show one 7-day timeline + phase sentence for the whole search area in the frontend's „Warunki” bar — without changing R (ranking stays "gdzie").

**Architecture:** New pure module `pipeline/flush.py` (never imported by `orchestrate`/`scoring`/`mvp`/`habitat` — structural guarantee that R is untouched, same idea as `pipeline/tie_break.py`). Calibrated on the existing GBIF backtest (90 real Boletus edulis finds, weather already cached) with leave-one-year-out cross-validation and a hard ship gate against the current F. `prepare_trip` makes one extra weather fetch (radar-merged past + 7 forecast days), builds an area-median daily weather series, runs the model once, and writes an optional `flush_{day}.json`; `sync-data` copies it as optional `flush.json`; the frontend renders it in `#conditions`.

**Tech Stack:** Python 3.12 (numpy, pandas, pyproj, scipy for the notebook), pytest; TypeScript/Vite frontend (`model.ts`, `main.ts`, `style.css`, Vitest); Node `scripts/sync-data.mjs`; `launcher/trip_archive.py`.

**Spec:** This plan's "Decyzje projektowe" section. Derived in the 2026-09-27 session: user chose (1) separate indicator, R unchanged until GBIF shows the flush model beats F; (2) one area-wide timeline in the „Warunki” bar; (3) 7-day horizon; then approved the model design below. Context: `docs/archiwum/CODEX-HANDOFF.md` notes (23), (25), (26).

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

## Decyzja 2026-09-27 (po sesji): Plan-B -- bramka E3 NIEZALICZONA

Task 3's ship gate failed: `notebooks/06_backtest_flush.py`'s leave-one-year-out held-out mean rank (0.548) was BELOW the baseline `rank_F_loc_no_gseason` (0.626), not above it (Wilcoxon p=0.041, significant in the wrong direction). Per the plan's own E3 rule this stops Tasks 4-7 as originally written. Two follow-up diagnostics (`notebooks/08_flush_pulse_timing_diagnostic.py`, `notebooks/09_flush_pulse_timing_season_controlled.py`, user-requested, no production code) explain why: days/degree-days since the most recent rain pulse looked like they separated the 90 real GBIF finds from random candidate days (KS p=0.006-0.0008) only when candidates were pooled across the WHOLE season -- once candidates are restricted to +/-15 days around each find's own day-of-year (same point/year), the effect vanishes (KS p=0.12-0.84). The apparent signal was a season confound (finds skew toward the cooler/later part of the season, where degree-days accumulate more slowly for the same elapsed time), not a real same-season "closer to a pulse is better" effect. The pulse -> thermal-clock -> Gaussian-peak model does not track real fruiting timing on this sample.

**Decision (Plan-B, replaces Tasks 3-7 below):**
- `pipeline/flush.py` (Tasks 1-2, already committed/tested) and `notebooks/06,08,09_*.py` stay in the repo as a **frozen, documented experiment** -- never imported by the production path (`prepare_trip.py`/frontend), same as they're already never imported by `orchestrate`/`scoring`/`mvp`/`habitat`. `profiles/boletus_edulis.yaml`'s `flush:` section keeps its original `[E]` values (uncalibrated -- the gate never passed) with a comment recording the gate failure.
- Two supporting real-data checks (ad hoc, not committed, run live against Bedziemysl 20km): (a) F itself (already validated at 0.626 in the GBIF backtest) varies by *two* `fruiting_classes` boundaries across a real 7-day horizon (0.803 "Bardzo dobre" today down to 0.324 "Umiarkowane" at +6d) -- enough day-to-day variation to justify per-day tiles, by the user's own "less than one class = skip tiles" test. (b) The real last-two-rain-pulses (radar, area median, unscaled mm) are 21-22.09 (28.5mm, 5 days ago) and 11-12.09 (20.3mm, 15 days ago) -- confirms `pipeline.flush.detect_pulses`/`area_daily_weather` (the pulse-DETECTION half of Task 1-2, not the thermal-clock/Gaussian half) still produce correct, reusable facts.
- New module **`pipeline/conditions_timeline.py`**: reuses only `pipeline.flush.{FlushParams, detect_pulses, area_daily_weather, fmt_day_range}` (pure pulse detection + date formatting, not the invalidated model) for a **fact-only** rain summary (dates, real mm, days-ago of up to 2 recent pulses -- no phase/peak language), plus a **new** per-horizon-day F computation reusing existing, unmodified `pipeline.scoring`/`pipeline.weather`/`pipeline.phenology` functions (the same math that already scores 0.626 in the GBIF backtest), run once per day of the horizon instead of once per search.
- New profile section `conditions:` (separate from the frozen `flush:` section) holds the reporting thresholds (`wet_day_mm`, `pulse_min_mm`, `radar_rain_scale`, `lookback_days`, `horizon_days`, `max_rains`). No ship gate needed for Tasks 4 (renumbered) onward: F is already validated; nothing here is newly calibrated.
- Artifact renamed `flush_{day}.json`/`flush.json` -> `conditions_{day}.json`/`conditions.json` throughout (export, sync, archive, frontend) -- "flush"/"wysyp" implied the disproven peak-timing claim; the new file only carries F-per-day + rain facts.
- Tile `level` (0-3) is now the day's `fruiting_classes` index (via new `pipeline.scoring.classify_fruiting_level`), not a separate threshold table.

E1 (area-level only, median over radius) and E4 (timeline always starts today) are unchanged and still apply. E2/E3 are superseded: E2's radar/ERA5 rain-scale ratio is still used (for the pulse *reporting* threshold, not a predictive parameter), but E3's ship-gate mechanism no longer applies to Tasks 4+ since nothing calibrated ships.

## Global Constraints

- TDD: failing test first in every code task. Python tests run with no network.
- Tests: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`; frontend in `frontend/`: `npm test`, `npx tsc --noEmit`, `npx vite build`.
- `pipeline/flush.py` must never be imported by `pipeline/orchestrate.py`, `scoring.py`, `mvp.py`, `habitat.py` (Task 4's structural test already covers this from Tasks 1-2). R, H, F, F_loc, `scores_{day}.json` fields do not change.
- **(Plan-B addition)** `pipeline/conditions_timeline.py` must never import `pipeline.flush`'s disproven modeling names (`wave_intensity`, `wave_phase`, `peak_window`, `build_area_timeline`, `PHASE_LABELS`, `degree_days_after`, `timeline_summary`, `flush_series`) -- only the pure pulse-detection/date-formatting helpers (`FlushParams`, `detect_pulses`, `area_daily_weather`, `fmt_day_range`). Task 4 (renumbered) adds a structural test for this, same pattern as the R-boundary guard.
- Do not change `fruiting.*`, `fruiting_classes`, `pressure.*`, `radar.*` profile values. (Plan-B reads `fruiting_classes`/`fruiting.*` from more days than before via `classify_fruiting_level`, but never changes their values.)
- `conditions_{day}.json` / `conditions.json` is optional everywhere (sync, frontend, saved trips), same pattern as `regions`/`details`: missing = old „Warunki” text, malformed = loud error.
- No personal data in the repo (station coordinates stay in `cache/stations/`).
- User-facing text in Polish; Python prints ASCII-only Polish like the rest of `prepare_trip.py`; JSON/UI strings may use Polish diacritics.
- Final task: full pytest + frontend test/tsc/build, new top note in `docs/archiwum/CODEX-HANDOFF.md`.

## Review Focus

- Open-Meteo `date` = UTC instant of local midnight — area aggregation must use `tz_convert("Europe/Warsaw")` before `.dt.date` (and accept naive dates from test fakes) — already covered by Task 2's `test_area_daily_weather_uses_local_dates_and_median`; Plan-B's `pipeline/conditions_timeline.py` duplicates the same tz handling (`with_local_date`) for the raw multi-point frame it feeds `compute_weather_features` — Task 4 (renumbered) test `test_with_local_date_converts_utc_midnight_to_local_day`.
- Today missing from the weather frame (test fakes in `tests/test_search_area.py` return Aug 2026 data) must skip the timeline with a `UWAGA` line, not crash the whole analysis — Task 5 (renumbered) step 4 runs `tests/test_search_area.py`; Task 4 (renumbered) test `test_build_conditions_timeline_rejects_missing_today`.
- ~~A frost day must end a wave...~~ (Task 1's `test_frost_ends_the_wave` already covers this for the frozen experimental module; not applicable to Plan-B's production path, which never runs the thermal clock.)
- A stale `conditions.json` from a previous day/sync must never sit next to fresh scores (sync removes it; saved trips drop it; prepare_trip deletes a same-day file before recomputing) — Task 6 (renumbered) tests.
- ~~Rain still falling today...~~ (Task 2's tests already cover this for the frozen experimental module; not applicable to Plan-B, which has no phase/peak concept.)
- **(Plan-B addition)** A rain pulse whose end is still in the future relative to `today` (forecast rain, not yet fallen) must not be reported as a "recent rain" fact — Task 4 (renumbered) test `test_recent_rains_excludes_a_pulse_not_yet_ended`.
- **(Plan-B addition)** `classify_fruiting_level` must return the same class boundary semantics as the existing `classify_fruiting` label lookup (same `<` comparison against `cls["max"]`, same fallback to the last class) — Task 4 (renumbered) test `test_classify_fruiting_level_matches_classify_fruiting_label`.

---

## Task 0: Pre-flight (no code)

- [x] **Step 1:** `git status` — working tree should only show the long-standing `uv.lock`, `CLAUDE.md`, `frontend/public/`. If anything else is modified, ask before starting. **Done 2026-09-27: matched.**
- [x] **Step 2:** Confirm E1–E4 with the user in one short message (quote them). Update this section if anything changes. **Done 2026-09-27: user confirmed E1-E4 unchanged.**

---

## Task 1: `pipeline/flush.py` core — pulses, thermal clock, intensity

**Status: complete, committed (`bcc1324`).** Kept verbatim below for the historical record; do not re-run. `pipeline/flush.py` is now a **frozen experiment** per the Plan-B decision above — Tasks 4+ reuse only its pure pulse-detection/date-formatting exports, never its thermal-clock/Gaussian exports.

**Files:**
- Create: `pipeline/flush.py`
- Modify: `profiles/boletus_edulis.yaml` (new `flush:` section)
- Test: `tests/test_flush.py`

**Interfaces:**
- Produces: `FlushParams` (frozen dataclass: `wet_day_mm, pulse_min_mm, t_base_c, cold_night_c, cold_night_factor, frost_c, dd_peak, dd_sigma`), `flush_params(profile, rain_scale=1.0) -> FlushParams`, `Pulse` (frozen: `start:int, end:int, rain_mm:float, strength:float`), `detect_pulses(precip, params) -> list[Pulse]`, `degree_days_after(end, tmean, tmin, params) -> np.ndarray` (NaN ≤ end, +inf from first frost day), `wave_intensity(dd, strength, params) -> np.ndarray`, `flush_series(precip, tmean, tmin, params) -> tuple[np.ndarray, list[Pulse], list[np.ndarray]]`.

- [x] **Step 1-5:** written, run RED then GREEN (8 passed), committed. See `git show bcc1324` for the exact diff (identical to the code this plan originally specified).

---

## Task 2: Phases, peak window, area timeline

**Status: complete, committed (`95d7352`).** Kept verbatim below for the historical record; do not re-run. Same frozen-experiment note as Task 1 — `wave_phase`/`peak_window`/`timeline_summary`/`build_area_timeline`/`PHASE_LABELS` are NOT reused by Tasks 4+; only `area_daily_weather`/`fmt_day_range` (also defined here) are.

**Files:**
- Modify: `pipeline/flush.py` (append)
- Test: `tests/test_flush.py` (append)

**Interfaces:**
- Consumes: Task 1.
- Produces: `PHASE_LABELS: dict[str, str]`, `wave_phase(dd_today: float, params) -> str`, `peak_window(dd, dates: list[date], params) -> tuple[date, date] | None`, `fmt_day_range(a: date, b: date) -> str`, `area_daily_weather(daily: pd.DataFrame, points) -> pd.DataFrame` (index = local `date`, columns `precipitation_mm, tmean_c, tmin_c`), `timeline_summary(waves: list[dict], pulse_min_mm: float) -> str`, `build_area_timeline(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> dict` with keys `generated_for, horizon_days, pulse_min_mm, waves, days, summary` (raises `ValueError` when `today` is not in `area.index`).

- [x] **Step 1-5:** written, run RED then GREEN (24 passed), committed. See `git show 95d7352` for the exact diff (identical to the code this plan originally specified).

---

## Task 3: Diagnoza i decyzja Plan-B (bramka E3 NIEZALICZONA)

**Status: complete, run inline this session; nothing to implement — this task's outcome IS the Plan-B decision above.** Kept as a record of exactly what ran and why Tasks 4+ below look the way they do.

**Files (all created, none committed yet — commit them as the first step of Task 4):**
- `notebooks/06_backtest_flush.py` — calibration + LOYO CV grid search (as originally specified by this plan).
- `notebooks/08_flush_pulse_timing_diagnostic.py`, `notebooks/09_flush_pulse_timing_season_controlled.py` — user-requested diagnostics, no production code.
- `profiles/boletus_edulis.yaml`'s `flush:` section: NOT modified (gate failed, no calibrated values to write) — Task 4 adds a comment recording the failure.

- [x] **Step 1: Fresh baseline.** `.venv/Scripts/python.exe notebooks/03_backtest_gbif.py` (cache-only, `MAX_YEAR=2023`, all cache hits, N=90). Result: **F_loc bez G_season: średnia=0.626 mediana=0.693** (the E3 baseline).
- [x] **Step 2: Calibration.** `notebooks/06_backtest_flush.py` (144 combos × 90 finds, no network). Result:
  - flush (LOYO held-out): średnia=0.548 mediana=0.552
  - baseline: średnia=0.626 mediana=0.693
  - Wilcoxon (flush − baseline) p=0.04095 (significant, wrong direction)
  - best on full data: `pulse_min_mm=20.0, dd_peak=80.0, dd_sigma=20.0, t_base_c=6.0`, średnia=0.599 (still < baseline)
- [x] **Step 3: Gate.** `heldout.mean() (0.548) > baseline.mean() (0.626)` is **False** → **BRAMKA E3: NIEZALICZONA.** Per the plan: stop, report, ask. Reported to the user; user chose not to widen the grid and instead requested the two diagnostics below before deciding what ships.
- [x] **Step 4a: Diagnostic — pulse timing vs. random days, whole season.** `notebooks/08_flush_pulse_timing_diagnostic.py`. For `pulse_min_mm` ∈ {15, 20}, compared days/degree-days since the most recent rain pulse for the 90 finds against ALL candidate days (1 Jun–31 Oct) at the same point/year:
  - pulse_min_mm=15: dni od pulsu KS p=0.244 (n.s.); **stopniodni od pulsu KS p=0.0064** (istotne, znaleziska niżej: śr 118.2 vs 174.4)
  - pulse_min_mm=20: dni od pulsu KS p=0.068; **stopniodni od pulsu KS p=0.0008** (istotne, śr 145.3 vs 220.1)
- [x] **Step 4b: Diagnostic — season-controlled.** `notebooks/09_flush_pulse_timing_season_controlled.py`. Same comparison, but candidates restricted to ±15 days around each find's own day-of-year (same point/year):
  - pulse_min_mm=15: dni od pulsu KS p=0.8415; stopniodni KS p=0.2639 — **both n.s.**
  - pulse_min_mm=20: dni od pulsu KS p=0.8229; stopniodni KS p=0.1191 — **both n.s.**
  - **Conclusion: the Step 4a signal was a season confound, not a real rain-recency effect.** Confirms the gate result; no further calibration attempt is warranted on this model shape.
- [x] **Step 5: Real-data sanity checks (ad hoc, not saved as notebooks).**
  - 7-day F horizon, Będziemyśl 20km, radar, live: F 0.803 ("Bardzo dobre", dziś) → 0.324 ("Umiarkowane", +6d), crossing 2 class boundaries — enough variation to keep per-day tiles.
  - Last two real rain pulses (radar, area median, unscaled): 21–22.09 28.5mm (5 days ago), 11–12.09 20.3mm (15 days ago). Confirms `detect_pulses`/`area_daily_weather` produce correct facts independent of the failed thermal-clock model.
- [x] **Step 6: Decision.** Plan-B (recorded above). Proceed to Task 4.

---

## Task 4: `pipeline/conditions_timeline.py` core — fact-only rain summary + per-day F

**Files:**
- Modify: `pipeline/scoring.py` (add `classify_fruiting_level`), `profiles/boletus_edulis.yaml` (new `conditions:` section; comment on `flush:` recording the gate failure)
- Create: `pipeline/conditions_timeline.py`
- Test: `tests/test_scoring.py` (append), `tests/test_conditions_timeline.py`
- Commit also: `notebooks/06_backtest_flush.py`, `notebooks/08_flush_pulse_timing_diagnostic.py`, `notebooks/09_flush_pulse_timing_season_controlled.py` (Task 3's outputs, not yet committed)

**Interfaces:**
- Produces (scoring.py): `classify_fruiting_level(f: float, profile: dict) -> int` (0-based index into `profile["fruiting_classes"]`, same boundary semantics as `classify_fruiting`).
- Produces (conditions_timeline.py): `with_local_date(daily: pd.DataFrame) -> pd.DataFrame` (adds `local_date` column), `recent_rains(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> list[dict]` (keys `start, end, rain_mm, days_ago`, raises `ValueError` when `today not in area.index`), `rains_summary(rains: list[dict], pulse_min_mm: float) -> str`, `build_conditions_timeline(daily: pd.DataFrame, points, clim_df: pd.DataFrame, clim_points, today: date, profile: dict, rain_scale: float = 1.0) -> dict` with keys `generated_for, horizon_days, pulse_min_mm, rains, days, summary` (`days` entries: `date, F, level, forecast`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scoring.py (append)
@pytest.mark.parametrize("f,expected", [
    (0.1, 0), (0.2, 1), (0.44, 1), (0.45, 2), (0.69, 2), (0.70, 3),
])
def test_classify_fruiting_level_matches_classify_fruiting_label(f, expected):
    from pipeline.scoring import classify_fruiting_level
    assert classify_fruiting_level(f, PROFILE) == expected
    classes = PROFILE["fruiting_classes"]
    assert classes[classify_fruiting_level(f, PROFILE)]["label"] == classify_fruiting(f, PROFILE)
```

```python
# tests/test_conditions_timeline.py
import pathlib
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from pipeline.habitat import load_profile
from pipeline.phenology import compute_g_season
from pipeline.scoring import classify_fruiting_level, compute_fruiting, score_frost, score_moisture, score_temperature
from pipeline.weather import climatology_window_values, compute_weather_features, percentile_rank
from pipeline.conditions_timeline import (
    build_conditions_timeline, rains_summary, recent_rains, with_local_date,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")
D0 = date(2026, 9, 20)


def test_with_local_date_converts_utc_midnight_to_local_day():
    utc_midnights = pd.to_datetime(["2026-09-20 22:00", "2026-09-21 22:00"], utc=True)  # local 21.09, 22.09
    daily = pd.DataFrame({"lat": [50.0, 50.0], "lon": [21.0, 21.0], "date": utc_midnights,
                          "precipitation_mm": [1.0, 2.0]})
    out = with_local_date(daily)
    assert out["local_date"].tolist() == [date(2026, 9, 21), date(2026, 9, 22)]


def _area(precip, start=D0):
    idx = [start + timedelta(days=k) for k in range(len(precip))]
    return pd.DataFrame({"precipitation_mm": precip}, index=idx)


def test_recent_rains_excludes_a_pulse_not_yet_ended():
    precip = [0, 0, 0, 0, 0, 20, 0, 0, 0, 25, 0, 0]  # pulse at idx5 (past), idx9 (future vs today)
    today = D0 + timedelta(days=7)
    rains = recent_rains(_area(precip), today, PROFILE)
    assert rains == [{"start": "2026-09-25", "end": "2026-09-25", "rain_mm": 20.0, "days_ago": 2}]


def test_recent_rains_returns_up_to_max_rains_most_recent_first():
    precip = [0, 0, 20, 0, 0, 0, 20, 0, 0, 0, 20, 0, 0, 0, 0]
    today = D0 + timedelta(days=14)
    rains = recent_rains(_area(precip), today, PROFILE)
    assert [r["start"] for r in rains] == ["2026-09-30", "2026-09-26"]  # 2 most recent, newest first


def test_recent_rains_rejects_missing_today():
    with pytest.raises(ValueError):
        recent_rains(_area([0.0] * 5), date(2026, 12, 1), PROFILE)


def test_rains_summary_formats_dates_mm_and_days_ago():
    rains = [{"start": "2026-09-25", "end": "2026-09-25", "rain_mm": 20.0, "days_ago": 2},
             {"start": "2026-09-11", "end": "2026-09-12", "rain_mm": 20.3, "days_ago": 15}]
    assert rains_summary(rains, 15.0) == (
        "Ostatni większy deszcz: 25.09 (20.0 mm), 2 dni temu"
        " · wcześniejszy deszcz: 11–12.09 (20.3 mm), 15 dni temu")


def test_rains_summary_without_rains_states_the_threshold():
    assert rains_summary([], 15.0) == "Brak deszczu ≥ 15 mm w ostatnich dniach."


def _daily_multi_point(points, start, days, precip=2.0, et0=1.0, tmean=13.0, tmin=6.0):
    rows = []
    for lat, lon in points:
        for d in pd.date_range(start, periods=days, freq="D", tz="UTC"):
            rows.append({"lat": lat, "lon": lon, "date": d, "precipitation_mm": precip,
                         "et0_mm": et0, "tmean_c": tmean, "tmin_c": tmin})
    return pd.DataFrame(rows)


def _clim(points, cwb26=30.0):
    rows = []
    for lat, lon in points:
        for d in pd.date_range("2000-01-01", periods=400, freq="D"):
            rows.append({"lat": lat, "lon": lon, "date": d, "cwb26": cwb26})
    return pd.DataFrame(rows)


def test_build_conditions_timeline_rejects_missing_today():
    points = [(50.0, 21.0)]
    daily = _daily_multi_point(points, "2026-08-01", 10)
    with pytest.raises(ValueError):
        build_conditions_timeline(daily, points, _clim(points), points, date(2026, 12, 1), PROFILE)


def test_build_conditions_timeline_seven_days_match_direct_recomputation():
    points = [(50.0, 21.0), (50.1, 21.1)]
    today = date(2026, 9, 27)
    start = pd.Timestamp(today, tz="UTC") - pd.Timedelta(days=40)
    daily = _daily_multi_point(points, start, 47)
    clim_df = _clim(points)

    out = build_conditions_timeline(daily, points, clim_df, points, today, PROFILE)

    assert [d["date"] for d in out["days"]] == [(today + timedelta(days=k)).isoformat() for k in range(7)]
    assert out["days"][0]["forecast"] is False and all(d["forecast"] for d in out["days"][1:])

    with_ld = with_local_date(daily)
    for k, entry in enumerate(out["days"]):
        day_k = today + timedelta(days=k)
        sub = with_ld[with_ld["local_date"] <= day_k]
        feats = compute_weather_features(sub)
        target_doy = day_k.timetuple().tm_yday
        cwb_hist = np.concatenate([climatology_window_values(clim_df, lat, lon, target_doy, "cwb26")
                                    for lat, lon in points])
        pct_cwb26 = percentile_rank(float(feats["cwb26"].median()), cwb_hist)
        m = score_moisture(pct_cwb26, 0.5, PROFILE)
        t = score_temperature(float(feats["tmean20"].median()), float(feats["tmean5"].median()),
                              float(feats["p5"].median()), PROFILE)
        k_frost = score_frost(float(feats["tmin3"].median()), PROFILE)
        g_season = compute_g_season(target_doy, PROFILE)
        expected_f = compute_fruiting(m, t, k_frost, g_season=g_season)
        assert entry["F"] == pytest.approx(round(expected_f, 3))
        assert entry["level"] == classify_fruiting_level(expected_f, PROFILE)


def test_conditions_timeline_does_not_use_the_disproven_wave_model():
    # Structural guarantee (Plan-B): production reuses only pulse DETECTION
    # from pipeline.flush, never its thermal-clock/Gaussian model.
    src = pathlib.Path("pipeline/conditions_timeline.py").read_text(encoding="utf-8")
    for name in ["wave_intensity", "wave_phase", "peak_window", "build_area_timeline",
                 "PHASE_LABELS", "degree_days_after", "timeline_summary", "flush_series"]:
        assert name not in src, name
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_scoring.py tests/test_conditions_timeline.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'classify_fruiting_level'` / `ModuleNotFoundError: No module named 'pipeline.conditions_timeline'`.

- [ ] **Step 3: Implement**

`pipeline/scoring.py` (after `classify_fruiting`):

```python
def classify_fruiting_level(f: float, profile: dict) -> int:
    """Same boundary semantics as classify_fruiting, as a 0-based index
    (plan A2 Plan-B: this is the flush timeline's per-day tile `level`,
    replacing a separate threshold table)."""
    classes = profile["fruiting_classes"]
    for i, cls in enumerate(classes):
        if f < cls["max"]:
            return i
    return len(classes) - 1
```

`profiles/boletus_edulis.yaml` — update the `flush:` section's header comment (values unchanged) and add a new `conditions:` section after it:

```yaml
flush:
  # Plan 2026-09-27 A2 (docs/archiwum/superpowers/plans/2026-09-27-borowik-wysyp-a2.md):
  # flush-timing model, pipeline/flush.py. NEVER feeds R.
  # SHIP GATE FAILED 2026-09-27 (Task 3: LOYO held-out mean 0.548 <
  # baseline F_loc bez G_season 0.626; notebooks 08/09 traced the earlier
  # apparent rain-recency signal to a season confound). Frozen as an
  # uncalibrated experiment -- NOT imported by prepare_trip/frontend.
  # See pipeline/conditions_timeline.py for what shipped instead (Plan-B).
  wet_day_mm: 1.0
  pulse_min_mm: 15.0
  radar_rain_scale: 0.848
  t_base_c: 5.0
  cold_night_c: 5.0
  cold_night_factor: 0.5
  frost_c: -1.0
  dd_peak: 100.0
  dd_sigma: 35.0
  lookback_days: 45
  horizon_days: 7
  max_waves: 2
  level_thresholds: [0.1, 0.3, 0.6]

conditions:
  # Plan 2026-09-27 A2 "Plan-B" (docs/archiwum/superpowers/plans/2026-09-27-borowik-wysyp-a2.md):
  # pipeline/conditions_timeline.py. Real F per horizon day (already
  # validated in the GBIF backtest, 0.626) + a fact-only rain summary,
  # reusing only flush.py's pulse DETECTION (not its thermal clock/peak
  # model -- see the flush: section's comment above for why).
  wet_day_mm: 1.0
  pulse_min_mm: 15.0          # "big enough to mention" cutoff, not calibrated
  radar_rain_scale: 0.848     # radar/ERA5 rain ratio, notebooks/05 (note (25))
  lookback_days: 45
  horizon_days: 7
  max_rains: 2
```

`pipeline/conditions_timeline.py`:

```python
"""A2 Plan-B: fact-only conditions timeline -- plan 2026-09-27
(docs/archiwum/superpowers/plans/2026-09-27-borowik-wysyp-a2.md, "Decyzja
2026-09-27: Plan-B" section).

Reuses only pipeline.flush's pulse DETECTION (never its thermal-clock/
Gaussian model, which failed its GBIF ship gate) for a fact-only rain
summary, plus real F -- already validated at 0.626 in the GBIF backtest --
computed once per horizon day instead of once per search. Still answers
"kiedy", never "gdzie": R is untouched."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline.flush import FlushParams, area_daily_weather, detect_pulses, fmt_day_range
from pipeline.phenology import compute_g_season
from pipeline.scoring import (
    classify_fruiting_level, compute_fruiting, score_frost, score_moisture, score_temperature,
)
from pipeline.weather import climatology_window_values, compute_weather_features, percentile_rank


def with_local_date(daily: pd.DataFrame) -> pd.DataFrame:
    """Adds a `local_date` column (Open-Meteo `date` is the UTC instant of
    local midnight; naive dates from test fakes are taken as-is) -- same
    tz handling as pipeline.flush.area_daily_weather, duplicated here
    because this module needs the per-point rows (for
    compute_weather_features' rolling windows), not the area median."""
    dates = daily["date"]
    local = (dates.dt.tz_convert("Europe/Warsaw") if dates.dt.tz is not None else dates).dt.date
    return daily.assign(local_date=local)


def _pulse_params(profile: dict, rain_scale: float) -> FlushParams:
    """detect_pulses only reads wet_day_mm/pulse_min_mm -- the thermal-
    clock fields are unused placeholders, kept only so pipeline.flush's
    (frozen) FlushParams shape doesn't need touching."""
    cfg = profile["conditions"]
    return FlushParams(wet_day_mm=cfg["wet_day_mm"], pulse_min_mm=cfg["pulse_min_mm"] * rain_scale,
                        t_base_c=0.0, cold_night_c=-1e9, cold_night_factor=1.0, frost_c=-1e9,
                        dd_peak=0.0, dd_sigma=1.0)


def recent_rains(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> list[dict]:
    """Up to conditions.max_rains most recent qualifying pulses that have
    already ended by `today`, newest first, within conditions.lookback_days."""
    cfg = profile["conditions"]
    params = _pulse_params(profile, rain_scale)
    dates = list(area.index)
    if today not in dates:
        raise ValueError(f"brak danych pogodowych dla {today.isoformat()}")
    t = dates.index(today)
    pulses = detect_pulses(area["precipitation_mm"].to_numpy(), params)
    out = []
    for pulse in sorted(pulses, key=lambda p: -p.end):
        if pulse.end > t or (today - dates[pulse.end]).days > cfg["lookback_days"]:
            continue
        out.append({"start": dates[pulse.start].isoformat(), "end": dates[pulse.end].isoformat(),
                    "rain_mm": round(pulse.rain_mm, 1), "days_ago": (today - dates[pulse.end]).days})
        if len(out) == cfg["max_rains"]:
            break
    return out


def rains_summary(rains: list[dict], pulse_min_mm: float) -> str:
    if not rains:
        return f"Brak deszczu ≥ {pulse_min_mm:.0f} mm w ostatnich dniach."
    labels = ["Ostatni większy deszcz", "wcześniejszy deszcz"]
    parts = []
    for i, r in enumerate(rains):
        rng = fmt_day_range(date.fromisoformat(r["start"]), date.fromisoformat(r["end"]))
        parts.append(f"{labels[min(i, 1)]}: {rng} ({r['rain_mm']:.1f} mm), {r['days_ago']} dni temu")
    return " · ".join(parts)


def build_conditions_timeline(daily: pd.DataFrame, points, clim_df: pd.DataFrame, clim_points,
                               today: date, profile: dict, rain_scale: float = 1.0) -> dict:
    cfg = profile["conditions"]
    params = _pulse_params(profile, rain_scale)
    area = area_daily_weather(daily, points)
    rains = recent_rains(area, today, profile, rain_scale)  # raises ValueError if today missing

    with_ld = with_local_date(daily)
    all_dates = set(with_ld["local_date"])
    days = []
    for k in range(cfg["horizon_days"]):
        day_k = today + timedelta(days=k)
        if day_k not in all_dates:
            break
        sub = with_ld[with_ld["local_date"] <= day_k]
        feats = compute_weather_features(sub)
        target_doy = day_k.timetuple().tm_yday
        cwb_hist = np.concatenate([climatology_window_values(clim_df, lat, lon, target_doy, "cwb26")
                                    for lat, lon in clim_points]) if clim_points else np.array([])
        pct_cwb26 = percentile_rank(float(feats["cwb26"].median()), cwb_hist)
        m = score_moisture(pct_cwb26, 0.5, profile)  # pct_sm ignored: fruiting.soil_moisture_weight == 0.0
        t = score_temperature(float(feats["tmean20"].median()), float(feats["tmean5"].median()),
                              float(feats["p5"].median()), profile)
        k_frost = score_frost(float(feats["tmin3"].median()), profile)
        g_season = compute_g_season(target_doy, profile)
        f = compute_fruiting(m, t, k_frost, g_season=g_season)
        days.append({"date": day_k.isoformat(), "F": round(f, 3),
                     "level": classify_fruiting_level(f, profile), "forecast": k > 0})
    return {"generated_for": today.isoformat(), "horizon_days": cfg["horizon_days"],
            "pulse_min_mm": round(params.pulse_min_mm, 1), "rains": rains, "days": days,
            "summary": rains_summary(rains, params.pulse_min_mm)}
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_scoring.py tests/test_conditions_timeline.py tests/test_flush.py -q -p no:cacheprovider`
Expected: all pass (6 new in test_scoring.py's parametrize + 9 new in test_conditions_timeline.py; test_flush.py's 24 unaffected).

- [ ] **Step 5: Commit**

```bash
git add pipeline/scoring.py pipeline/conditions_timeline.py profiles/boletus_edulis.yaml \
        tests/test_scoring.py tests/test_conditions_timeline.py \
        notebooks/06_backtest_flush.py notebooks/08_flush_pulse_timing_diagnostic.py \
        notebooks/09_flush_pulse_timing_season_controlled.py
git commit -m "feat: conditions_timeline core (fact rains + per-day F); record failed flush ship gate (plan A2 task 4, Plan-B)"
```

---

## Task 5: Export + `prepare_trip` wiring

**Files:**
- Modify: `pipeline/export.py`, `pipeline/prepare_trip.py`
- Test: `tests/test_export.py`, `tests/test_prepare_trip.py`

**Interfaces:**
- Consumes: `build_conditions_timeline` (Task 4).
- Produces: `write_conditions_json(timeline: dict, day: str, out_path) -> pathlib.Path` (adds `"day"`), `points_within_radius(points, lat, lon, radius_km) -> list[tuple[float, float]]`, `summary["conditions_path"]` (str or None).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_export.py (append)
from pipeline.export import write_conditions_json


def test_write_conditions_json_adds_day_and_writes_strict_json(tmp_path):
    timeline = {"generated_for": "2026-09-27", "horizon_days": 7, "pulse_min_mm": 15.0,
                "rains": [], "days": [{"date": "2026-09-27", "F": 0.5, "level": 2, "forecast": False}],
                "summary": "Brak deszczu ≥ 15 mm w ostatnich dniach."}
    path = write_conditions_json(timeline, "2026-09-27", tmp_path / "conditions_2026-09-27.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["day"] == "2026-09-27" and data["summary"] == timeline["summary"]
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

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py tests/test_prepare_trip.py -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'write_conditions_json'` / `AttributeError: points_within_radius`.

- [ ] **Step 3: Implement**

`pipeline/export.py` (after `write_regions_json`):

```python
def write_conditions_json(timeline: dict, day: str, out_path) -> pathlib.Path:
    """Plan A2 Plan-B: area conditions timeline
    (pipeline.conditions_timeline.build_conditions_timeline), optional on
    the frontend like regions/details."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"day": day, **timeline}, ensure_ascii=False, indent=2, allow_nan=False),
                        encoding="utf-8")
    return out_path
```

`pipeline/prepare_trip.py`:
- imports: `from pyproj import Transformer`, `from pipeline.conditions_timeline import build_conditions_timeline`, and add `write_conditions_json` to the existing `from pipeline.export import (...)`.
- module level (next to `build_weather_fetcher`):

```python
_WGS84_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def points_within_radius(points, lat: float, lon: float, radius_km: float) -> list[tuple[float, float]]:
    """Weather/climatology grid points inside the search circle (plan A2:
    the conditions timeline is the median/percentile over exactly these
    points)."""
    cx, cy = _WGS84_TO_2180.transform(lon, lat)
    out = []
    for p_lat, p_lon in points:
        x, y = _WGS84_TO_2180.transform(p_lon, p_lat)
        if math.hypot(x - cx, y - cy) <= radius_km * 1000.0:
            out.append((p_lat, p_lon))
    return out
```

- in `run_trip_preparation`: pull the weather AND climatology fetchers out into named variables (currently the climatology one is built inline inside the `run_poc(...)` call) and reuse both —

```python
    weather_fetcher = build_weather_fetcher(
        functools.partial(fetch_weather_raw, call_api=_weather_call_api, cache_dir=cache_dir),
        use_radar=use_radar, profile=profile, grid_spacing_m=grid_spacing_m, cache_dir=cache_dir,
    )
    climatology_fetcher = functools.partial(
        fetch_climatology_raw, call_api=_climatology_call_api, cache_dir=cache_dir,
    )
```

and pass `weather_fetcher=weather_fetcher, climatology_fetcher=climatology_fetcher` to `run_poc` (replacing both inline calls). Right after the `run_poc` result prints, add:

```python
    # Plan A2 Plan-B: real F per horizon day (today..today+6) + fact-only
    # rain summary. Never uses pipeline.flush's disproven Gaussian model.
    conditions_out = out_dir / f"conditions_{day}.json"
    conditions_out.unlink(missing_ok=True)
    conditions_path = None
    conditions_points = points_within_radius(make_grid(bbox, spacing_m=grid_spacing_m), lat, lon, radius_km)
    conditions_clim_points = points_within_radius(
        make_grid(bbox, spacing_m=climatology_grid_spacing_m), lat, lon, radius_km)
    conditions_daily = weather_fetcher(conditions_points, 92, forecast_days=profile["conditions"]["horizon_days"])
    conditions_clim = climatology_fetcher(conditions_clim_points, 1991, 2020)  # cached from run_poc's own fetch
    rain_scale = profile["conditions"]["radar_rain_scale"] if use_radar and profile["radar"]["enabled"] else 1.0
    try:
        timeline = build_conditions_timeline(conditions_daily, conditions_points, conditions_clim,
                                             conditions_clim_points, date.today(), profile, rain_scale=rain_scale)
    except ValueError as exc:
        print(f"UWAGA: warunki na kolejne dni pominiete ({exc}).", flush=True)
    else:
        conditions_path = write_conditions_json(timeline, day, conditions_out)
        print(f"Warunki: {timeline['summary']}", flush=True)
```

(`out_dir`, `bbox`, `grid_spacing_m`, `climatology_grid_spacing_m`, `day`, `lat`, `lon`, `radius_km` already exist in `run_trip_preparation`; `date` is already imported from `datetime` at the top.) Add `"conditions_path": str(conditions_path) if conditions_path else None,` to the summary dict.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all pass. `tests/test_search_area.py`'s fakes return August data, so their runs must take the `UWAGA: warunki na kolejne dni pominiete` path and still pass; if they fail instead, fix the code path (not the fakes).

- [ ] **Step 5: Commit**

```bash
git add pipeline/export.py pipeline/prepare_trip.py tests/test_export.py tests/test_prepare_trip.py
git commit -m "feat: export conditions timeline from prepare_trip (plan A2 task 5, Plan-B)"
```

---

## Task 6: `sync-data` + saved trips carry `conditions.json`

**Files:**
- Modify: `frontend/scripts/sync-data.mjs`, `frontend/scripts/sync-data.test.mjs`, `launcher/trip_archive.py`, `tests/test_trip_archive.py`

**Interfaces:**
- Produces: `syncData(...)` result gains `conditions: 0 | 1`; `conditions_{day}.json` → `public/data/conditions.json` (validated: JSON object, `day === day`, `Array.isArray(days)`); stale `conditions.json` removed; `TRIP_FILES` includes `"conditions.json"`.

- [ ] **Step 1: Write the failing tests**

In `frontend/scripts/sync-data.test.mjs`, change the expected object of `"copies one complete same-day bundle"` to include `conditions: 0`, and append:

```js
// Plan A2 Plan-B: conditions_{day}.json -> conditions.json, optional like regions/details.
const conditionsFile = (day = "2026-09-24") =>
  JSON.stringify({ day, summary: "Ostatni większy deszcz: 21–22.09 (28.5 mm), 5 dni temu", days: [] });

it("syncs a same-day conditions file alongside scores and geometries", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), conditionsFile());
  const result = await syncData(source, target);
  expect(result.conditions).toBe(1);
  expect(JSON.parse(await readFile(path.join(target, "conditions.json"), "utf8")).summary).toContain("deszcz");
});

it("rejects a same-day conditions file from another day or malformed", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), conditionsFile("2026-09-23"));
  await expect(syncData(source, target)).rejects.toThrow();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), "not json");
  await expect(syncData(source, target)).rejects.toThrow();
});

it("removes a stale conditions.json from a previous sync when the new day has none", async () => {
  const { source, target } = await fixture();
  await writeFile(path.join(source, "conditions_2026-09-24.json"), conditionsFile());
  await syncData(source, target);
  await rm(path.join(source, "conditions_2026-09-24.json"));
  const result = await syncData(source, target);
  expect(result.conditions).toBe(0);
  await expect(readFile(path.join(target, "conditions.json"), "utf8")).rejects.toThrow();
});
```

```python
# tests/test_trip_archive.py (append)
def test_resave_without_conditions_removes_old_conditions_snapshot(tmp_path):
    data, dest = tmp_path / "data", tmp_path / "trip"
    data.mkdir()
    for name in ["scores.json", "stands.geojson"]:
        (data / name).write_text("{}", encoding="utf-8")
    dest.mkdir()
    (dest / "conditions.json").write_text("old-conditions", encoding="utf-8")
    copied = copy_trip_files(data, dest)
    assert "conditions.json" not in copied
    assert not (dest / "conditions.json").exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm test` and `.venv/Scripts/python.exe -m pytest tests/test_trip_archive.py -q -p no:cacheprovider`
Expected: FAIL (no `conditions` in result; old `conditions.json` not removed).

- [ ] **Step 3: Implement**

`frontend/scripts/sync-data.mjs` — after the details block, before `await mkdir(target, ...)`:

```js
  // Plan A2 Plan-B: conditions_{day}.json is optional too (fact-only rain + per-day F).
  let conditionsRaw = null;
  try {
    conditionsRaw = await readFile(path.join(source, `conditions_${day}.json`), "utf8");
  } catch {
    conditionsRaw = null;
  }
  let conditions = null;
  if (conditionsRaw !== null) {
    try {
      conditions = JSON.parse(conditionsRaw);
    } catch {
      throw new Error(`Plik conditions_${day}.json jest uszkodzony.`);
    }
    if (!conditions || typeof conditions !== "object" || conditions.day !== day || !Array.isArray(conditions.days))
      throw new Error(`Niepoprawny format conditions_${day}.json.`);
  }
```

then next to the details push: `if (conditions !== null) { targets.push("conditions.json"); allContents.push(conditionsRaw); }`, next to the details `rm`: `if (conditions === null) await rm(path.join(target, "conditions.json"), { force: true });`, and add `conditions: conditions === null ? 0 : 1,` to the returned object.

`launcher/trip_archive.py`: `TRIP_FILES = ["scores.json", "stands.geojson", "regions.json", "details.json", "conditions.json"]`.

- [ ] **Step 4: Run to verify they pass**

Run: `cd frontend && npm test` and `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/sync-data.mjs frontend/scripts/sync-data.test.mjs launcher/trip_archive.py tests/test_trip_archive.py
git commit -m "feat: sync and archive optional conditions.json (plan A2 task 6, Plan-B)"
```

---

## Task 7: Frontend — timeline in „Warunki”

**Files:**
- Modify: `frontend/src/model.ts`, `frontend/src/model.test.ts`, `frontend/src/main.ts`, `frontend/src/style.css`

**Interfaces:**
- Produces: types `ConditionsDay`, `ConditionsRain`, `ConditionsTimeline`; `parseConditions(raw: unknown, day: string | undefined): ConditionsTimeline | null`; `dayLabel(dateIso: string, position: number): string`; `loadData()` result gains `conditions: ConditionsTimeline | null`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/model.test.ts (append; add parseConditions, dayLabel to the import from "./model")
describe("conditions timeline", () => {
  const conditions = (over: Record<string, unknown> = {}) => ({
    day: "2026-09-27",
    generated_for: "2026-09-27",
    horizon_days: 7,
    pulse_min_mm: 15.0,
    rains: [],
    summary: "Ostatni większy deszcz: 21–22.09 (28.5 mm), 5 dni temu",
    days: [{ date: "2026-09-27", F: 0.803, level: 3, forecast: false }],
    ...over,
  });
  it("returns null when conditions.json is absent", () => {
    expect(parseConditions(undefined, "2026-09-27")).toBeNull();
  });
  it("accepts a valid same-day timeline", () => {
    expect(parseConditions(conditions(), "2026-09-27")?.summary).toContain("deszcz");
  });
  it("rejects another day's timeline or malformed tiles", () => {
    expect(() => parseConditions(conditions(), "2026-09-26")).toThrow();
    expect(() =>
      parseConditions(conditions({ days: [{ date: "2026-09-27", F: 0.8, level: 7, forecast: false }] }), "2026-09-27"),
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
Expected: FAIL — `parseConditions` / `dayLabel` not exported.

- [ ] **Step 3: Implement**

`frontend/src/model.ts` (near the other exported types/parsers):

```ts
export type ConditionsDay = { date: string; F: number; level: 0 | 1 | 2 | 3; forecast: boolean };
export type ConditionsRain = { start: string; end: string; rain_mm: number; days_ago: number };
export type ConditionsTimeline = {
  day: string;
  generated_for: string;
  horizon_days: number;
  pulse_min_mm: number;
  rains: ConditionsRain[];
  summary: string;
  days: ConditionsDay[];
};

function isConditionsDay(value: unknown): value is ConditionsDay {
  const d = value as Record<string, unknown> | null;
  return (
    !!d &&
    typeof d.date === "string" &&
    typeof d.F === "number" &&
    Number.isFinite(d.F) &&
    [0, 1, 2, 3].includes(d.level as number) &&
    typeof d.forecast === "boolean"
  );
}

export function parseConditions(raw: unknown, day: string | undefined): ConditionsTimeline | null {
  if (raw === undefined) return null;
  const c = raw as Record<string, unknown> | null;
  if (
    !c ||
    typeof c !== "object" ||
    c.day !== day ||
    typeof c.summary !== "string" ||
    !Array.isArray(c.rains) ||
    !Array.isArray(c.days) ||
    !c.days.every(isConditionsDay)
  )
    throw new Error("Plik conditions.json jest niepoprawny. Uruchom synchronizację danych.");
  return c as unknown as ConditionsTimeline;
}

const WEEKDAYS = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];
export function dayLabel(dateIso: string, position: number): string {
  if (position === 0) return "dziś";
  return WEEKDAYS[new Date(`${dateIso}T12:00:00`).getDay()];
}
```

In `loadData`, after the details block, fetch `conditions.json` with the same optional pattern (`conditionsResponse?.ok` → `response.json()`, parse error → `throw new Error("Plik conditions.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.")`), then replace the final return with:

```ts
  const parsed = parseData(scoresRaw, standsRaw, regionsRaw, detailsRaw);
  return { ...parsed, conditions: parseConditions(conditionsRaw, parsed.scores[0]?.day) };
```

`frontend/src/main.ts`: add the `ConditionsTimeline` type and `dayLabel` to the existing import from `./model`; add

```ts
function conditionsHtml(median: number | null, conditions: ConditionsTimeline | null): string {
  const moisture = fruitingClass(median).toLocaleLowerCase("pl");
  if (!conditions)
    return `<span class="condition-symbol">${icon("leaf")}</span><div><strong>Warunki w obszarze: ${moisture}</strong><p>Ocena pogody z analizy · mediana dla wydzieleń przechodzących filtry</p></div><span class="model-label">MODEL EKSPERCKI · NIESKALIBROWANY</span>`;
  const tiles = conditions.days
    .map(
      (d, i) =>
        `<li class="conditions-day level-${d.level}${d.forecast ? " forecast" : ""}" title="${escape(formatDate(d.date))}: ${Math.round(d.F * 100)}/100"><span>${dayLabel(d.date, i)}</span><b aria-label="poziom ${d.level} z 3">${"●".repeat(d.level)}${"○".repeat(3 - d.level)}</b></li>`,
    )
    .join("");
  return `<span class="condition-symbol">${icon("mushroom")}</span><div><strong>${escape(conditions.summary)}</strong><p>Warunki wilgotności: ${moisture} · prognoza F na kolejne dni z pogody (radar/model), bez przewidywania szczytu wysypu</p><ol class="conditions-days" aria-label="Warunki wzrostu w kolejnych dniach">${tiles}</ol></div><span class="model-label">MODEL EKSPERCKI · NIESKALIBROWANY</span>`;
}
```

and replace the success-path `$("#conditions").innerHTML = ...` (currently ~line 615) with `$("#conditions").innerHTML = conditionsHtml(median, data.conditions);`. (`escape`, `formatDate`, `icon`, `fruitingClass` already exist in `main.ts`.)

`frontend/src/style.css` (append):

```css
.conditions-days { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; margin: 8px 0 0; padding: 0; }
.conditions-day { display: flex; flex-direction: column; align-items: center; min-width: 40px; padding: 4px 6px; border-radius: 8px; background: rgba(127, 127, 127, 0.08); font-size: 12px; }
.conditions-day b { font-weight: 400; letter-spacing: 1px; }
.conditions-day.level-2 { background: rgba(46, 125, 50, 0.12); }
.conditions-day.level-3 { background: rgba(46, 125, 50, 0.22); }
.conditions-day.forecast span { font-style: italic; }
```

- [ ] **Step 4: Run to verify they pass**

Run (in `frontend/`): `npm test`, `npx tsc --noEmit`, `npx vite build`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/model.ts frontend/src/model.test.ts frontend/src/main.ts frontend/src/style.css
git commit -m "feat: conditions timeline in the conditions bar (plan A2 task 7, Plan-B)"
```

---

## Task 8: Real run, visual check, docs, final verification

**Files:**
- Modify: `docs/archiwum/CODEX-HANDOFF.md`, `frontend/README.md`

- [ ] **Step 1: Real run + sync**

```bash
.venv/Scripts/python.exe -m pipeline.prepare_trip --lat 50.0555 --lon 21.7889 --radius-km 20
cd frontend && npm run sync-data
```

Expected: a `Warunki: ...` line, `notebooks/output/conditions_{today}.json` written, sync prints success and `public/data/conditions.json` exists. Record the summary sentence and the 7 F/level values.

- [ ] **Step 2: Visual check**

`npm run dev` in `frontend/`, open the page, check: fact-only rain sentence in the „Warunki” bar (no phase/peak language), 7 tiles (first "dziś", weekday labels, dots reflecting `fruiting_classes` level), no layout break on a narrow window (~375 px). If the browser tool cannot reach localhost (seen before, note (21)), say so in the handoff and rely on `vite build` + tests.

- [ ] **Step 3: Docs**

`frontend/README.md`: one paragraph "Warunki na kolejne dni" — what the tiles mean (poziom 0–3 = klasa F z `fruiting_classes`, nie model fazy wysypu), that the first day is today, later days use the temperature/rain forecast, that the sentence only reports facts about the last rain(s) (no peak prediction), and that `conditions.json` is optional.
`docs/archiwum/CODEX-HANDOFF.md`: new top note "(27): A2 -- flush model failed its GBIF ship gate; Plan-B shipped instead" -- the original model (pulse -> thermal clock -> Gaussian), the E3 gate numbers, the two diagnostics and why the apparent signal was a season confound, what Plan-B ships (per-day F + fact-only rain summary), real-run summary/sentence, test counts, open items (per-region timelines -- E1; a possible revisit of the pulse model with a moisture-state precondition, if ever revisited; B pressure from forest tracks still pending).

- [ ] **Step 4: Final verification**

```bash
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
cd frontend && npm test && npx tsc --noEmit && npx vite build
git diff --check
```

Expected: all green; put exact counts in the handoff note.

- [ ] **Step 5: Commit**

```bash
git add docs/archiwum/CODEX-HANDOFF.md frontend/README.md
git commit -m "docs: record A2 Plan-B (flush model failed gate, per-day F + fact rain summary shipped instead)"
```
