# Fenologia (G_season) + kalibracja wilgotności + tie-break pokrycia/zadrzewienia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give F (owocnikowanie) a real seasonal signal (G_season, static GBIF curve), recalibrate the moisture midpoint so "average" conditions read as "Dobre" not "Bardzo dobre", and add a non-scoring tie-break (ground cover + stand density) that orders otherwise-tied wydzielenia and region members more sensibly — without touching H or R_final's own formula.

**Architecture:** Three independent, additive changes, each following an existing pattern in this codebase:
1. **G_season** — a new pure module (`pipeline/phenology.py`) computes a 0..1 seasonal multiplier from a static, sourced GBIF monthly curve stored in the profile YAML; wired into `pipeline.orchestrate.run_poc`'s existing `compute_fruiting(..., g_season=...)` call (the parameter already exists, only the hardcoded `1.0` changes), exported per stand, and surfaced as an explanation note when significantly below 1.
2. **Moisture calibration** — a one-line profile change (`fruiting.moisture_midpoint` 0.35 → 0.50), verified against real cached data before/after.
3. **Tie-break** — a new module (`pipeline/tie_break.py`), structurally identical in spirit to `pipeline/bdl_package_details.py` (B3): never imported by `pipeline.orchestrate`/`habitat`/`scoring`/`mvp`, so it cannot affect H/R_final by construction. Its only consumers are `pipeline.regions` (region member ordering) and the frontend's flat "Wydzielenia" list sort — both purely presentational orderings, not the R/H values themselves.

**Tech Stack:** Python (pandas/geopandas, existing `pipeline/*` modules, pytest), TypeScript/Vite frontend (`frontend/src/model.ts`, `main.ts`, Vitest).

**Spec:** This plan's own text is the spec (derived from a 2026-09-25 user review, `docs/CODEX-HANDOFF.md` notes (18)-(21), and `docs/projekt-borowik.md`). No separate spec document exists for these three changes; the user confirmed there is no missing "Zmiana 3" (numbering in the original review jumped from 2 to 4).

## Global Constraints

- TDD: write the failing test before the implementation in every task below.
- Every new/changed Python test must run with no network access (same convention as the rest of `tests/`).
- **Never let G_season, moisture calibration, or tie-break touch H.** `pipeline.habitat.compute_habitat`/`score_host`/`score_site`/`score_age`/`passes_mask` are not modified by this plan.
- **`pipeline/tie_break.py` is never imported by `pipeline/orchestrate.py`, `pipeline/habitat.py`, `pipeline/scoring.py`, or `pipeline/mvp.py`** — the same structural (not just tested) guarantee `pipeline/bdl_package_details.py` already uses, so tie-break cannot silently leak into R_final.
- Do not change `profiles/boletus_edulis.yaml`'s `fruiting.moisture_slope` (only `moisture_midpoint`).
- Do not change `profiles/boletus_edulis.yaml`'s `fruiting_classes` without explicit user approval — if the before/after table in Task 5 suggests they need adjusting, propose it and stop; do not edit the file.
- No personal data (emails, etc.) in any file this plan touches.
- Final task: full `pytest`, frontend `npm test`, `tsc --noEmit`, `vite build`, and an update to the top of `docs/CODEX-HANDOFF.md`.

## Review Focus

- A trip date near the Dec→Jan boundary must interpolate G_season correctly across the year wrap, not fall off the end of the month list or discontinue at Jan 1 — Task 1's dedicated wraparound test.
- `veg_cover_cd` is blank on a large share of real `f_subarea.txt` rows (~30-45%) and `standdensity_index`/`density_cd` can also be blank cells (real-data quirk already hit twice in B2/B3, `pipeline/bdl_package_details.py`) — Task 6's loader must treat a blank cell as `None`, not crash on `NaN`/`json.dumps(allow_nan=False)` like the earlier two bugs did.
- A wydzielenie whose `adr_for` isn't covered by any downloaded BDL package must still get a neutral, non-crashing tie-break value (0.5), not `KeyError` or `None` propagating into a sort comparator — Task 6/7.
- An older `scores.json`/`details.json` (from before this plan) must still load in the frontend — `G_season`, `tie_break`, `veg_cover`, `standdensity_index` are all additive/optional fields, never required for existing exports to parse — Task 4/9's `parseData` changes.
- Region member ordering must stay well-defined (not just "whatever the spatial index returned") even in a large, near-uniform-R candidate cluster — Task 8 adds `test_group_into_regions_on_a_uniform_r_cluster_orders_members_by_tie_break`, reusing the existing synthetic continuous-forest grid fixture from `tests/test_regions.py` (all `R_final` tied) with a distinct `tie_break` per stand, and asserts member order follows it.

---

## Task 1: G_season phenology module

**Files:**
- Create: `pipeline/phenology.py`
- Modify: `profiles/boletus_edulis.yaml` (add `phenology:` section)
- Test: `tests/test_phenology.py`

**Interfaces:**
- Produces: `pipeline.phenology.compute_g_season(target_doy: int, profile: dict) -> float` — used by Task 2 (`pipeline/orchestrate.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_phenology.py
import pytest

from pipeline.habitat import load_profile
from pipeline.phenology import compute_g_season

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_compute_g_season_peaks_at_september_gbif_maximum():
    # September 15 is the GBIF monthly maximum (471 records) -- see the
    # profile's own gbif_monthly_counts comment for the source query.
    sept_15_doy = 258
    assert compute_g_season(sept_15_doy, PROFILE) == pytest.approx(1.0)


def test_compute_g_season_interpolates_linearly_between_month_midpoints():
    # Sept 15 (doy 258, weight 1.0) -> Oct 15 (doy 288, weight 350/471);
    # Sept 25 is exactly 1/3 of the way there.
    sept_25_doy = 268
    expected = 1.0 + (10.0 / 30.0) * (350.0 / 471.0 - 1.0)
    assert compute_g_season(sept_25_doy, PROFILE) == pytest.approx(expected, abs=1e-6)


def test_compute_g_season_floors_in_deep_winter():
    # January/February/March/April all have 0-1 GBIF records -- the raw
    # normalized weight is ~0, but the floor keeps F from being zeroed
    # outright by a single hard-coded multiplier.
    feb_15_doy = 46
    assert compute_g_season(feb_15_doy, PROFILE) == pytest.approx(
        PROFILE["phenology"]["g_season_floor"]
    )


def test_compute_g_season_interpolates_across_year_boundary():
    # Dec 15 (doy 349, weight 2/471) -> Jan 15 (doy 15 of the NEXT year,
    # weight 1/471) must interpolate smoothly across Dec 31 -> Jan 1
    # instead of jumping or raising.
    dec_20_doy = 354  # 5 days into the 31-day Dec15->Jan15 wrap
    w_dec, w_jan = 2.0 / 471.0, 1.0 / 471.0
    expected = max(
        PROFILE["phenology"]["g_season_floor"],
        w_dec + (5.0 / 31.0) * (w_jan - w_dec),
    )
    assert compute_g_season(dec_20_doy, PROFILE) == pytest.approx(expected, abs=1e-6)


def test_compute_g_season_never_exceeds_one():
    for doy in range(1, 366):
        assert 0.0 < compute_g_season(doy, PROFILE) <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_phenology.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.phenology'` (and `KeyError: 'phenology'` once the module exists but the profile doesn't).

- [ ] **Step 3: Add the `phenology:` section to the profile**

Add after the `fruiting_classes:` block (after line 131) in `profiles/boletus_edulis.yaml`:

```yaml
phenology:
  # Plan 2.1 "Zmiana 1" (user review 2026-09-25): static Boletus edulis
  # fruiting-season curve for Poland, from GBIF occurrence records --
  # queried live 2026-09-25 via
  # api.gbif.org/v1/occurrence/search?country=PL&scientificName=Boletus%20edulis&limit=0&facet=month&facetLimit=12,
  # n=1270 records with a recorded month (of ~1300 total occurrences).
  # Known bias: GBIF counts likely overrepresent Aug-Oct relative to true
  # fruiting frequency (more people are out foraging/reporting sightings
  # in peak season) -- still the only free PL-specific season curve
  # available, per user decision 2026-09-25. Stored statically (not
  # fetched per run) -- re-query and update this comment's date if this
  # curve is ever refreshed.
  gbif_monthly_counts: [1, 0, 0, 0, 2, 25, 118, 243, 471, 350, 58, 2]  # Jan..Dec
  # Floor for pipeline.phenology.compute_g_season's interpolated curve --
  # a genuinely fruitless month still isn't provably impossible with a
  # small, observation-biased sample, so G_season never reaches exactly 0.
  g_season_floor: 0.05
  # Explanation-note threshold (pipeline.explain.g_season_note): below this,
  # F's card/list explanation gets an extra "poza szczytem sezonu" note --
  # [E] plan decision, roughly "below half the GBIF peak month".
  g_season_note_threshold: 0.5
```

- [ ] **Step 4: Implement `pipeline/phenology.py`**

```python
from datetime import date

# Reference length for the circular day-of-year interpolation below.
# pipeline.orchestrate.run_poc's own target_doy (target_date.timetuple().
# tm_yday, used for climatology percentiles, plan 2.1 step A3) is likewise
# never leap-year-corrected -- this module accepts the same class of
# imprecision rather than introducing a different convention just for
# phenology, and target_date is always within Open-Meteo's 16-day forecast
# horizon (pipeline.prepare_trip.parse_args), so the practical effect is
# negligible.
_YEAR_LEN = 365


def _month_midpoint_doy(month: int) -> int:
    """Day-of-year of the 15th of `month`, in a fixed non-leap reference
    year (2023) -- a real date() call (not a hand-maintained lookup table)
    keeps the 12 breakpoints self-consistent by construction."""
    return date(2023, month, 15).timetuple().tm_yday


_MONTH_MIDPOINTS = [_month_midpoint_doy(m) for m in range(1, 13)]


def compute_g_season(target_doy: int, profile: dict) -> float:
    """Seasonal fruiting-frequency multiplier for
    pipeline.scoring.compute_fruiting's g_season (plan 2.1 "Zmiana 1"),
    from profile["phenology"]["gbif_monthly_counts"] (normalized to its
    own maximum month = 1.0), linearly interpolated between month
    MIDPOINTS (day 15 of each month, not month boundaries) so the curve
    has no jump crossing from one month to the next, then floored at
    profile["phenology"]["g_season_floor"].

    Not smoothed beyond this required month-midpoint interpolation: the
    raw monthly counts are already a clean, single-peaked curve (strictly
    rising Jan->Sep, then falling Sep->Dec, no jagged local dips) --
    additional smoothing (e.g. a moving average) would soften the real,
    sharp post-September drop (471->350->58) that a small sample can
    still show without it being noise, so it's deliberately left out
    (user asked to propose+justify whether to smooth, plan 2.1 review).

    `target_doy` should be the trip date's day-of-year
    (date.timetuple().tm_yday) -- same "trip date, not today" input
    pipeline.orchestrate.run_poc already uses for climatology
    percentiles (plan 2.1 step A3)."""
    cfg = profile["phenology"]
    counts = cfg["gbif_monthly_counts"]
    floor = cfg["g_season_floor"]
    max_count = max(counts)
    weights = [c / max_count for c in counts]

    # Triple the 12 anchors (one cycle before, the real cycle, one cycle
    # after) so linear interpolation across the Dec->Jan wrap needs no
    # special-casing -- target_doy always falls inside the middle cycle,
    # bracketed on both sides by real neighbours.
    doys = (
        [d - _YEAR_LEN for d in _MONTH_MIDPOINTS]
        + _MONTH_MIDPOINTS
        + [d + _YEAR_LEN for d in _MONTH_MIDPOINTS]
    )
    vals = weights * 3

    idx = 0
    for i in range(len(doys) - 1):
        if doys[i] <= target_doy <= doys[i + 1]:
            idx = i
            break
    d0, d1 = doys[idx], doys[idx + 1]
    v0, v1 = vals[idx], vals[idx + 1]
    frac = (target_doy - d0) / (d1 - d0)
    value = v0 + frac * (v1 - v0)
    return max(floor, value)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_phenology.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add pipeline/phenology.py profiles/boletus_edulis.yaml tests/test_phenology.py
git commit -m "feat: add G_season phenology curve from GBIF monthly data (plan 2.1 Zmiana 1, step 1/4)"
```

---

## Task 2: Wire G_season into run_poc

**Files:**
- Modify: `pipeline/orchestrate.py:131` (reuse existing `target_doy`), `pipeline/orchestrate.py:204` (compute_fruiting call), `pipeline/orchestrate.py` (new `stands["G_season"]` column + diagnostics entry)
- Test: `tests/test_orchestrate.py`

**Interfaces:**
- Consumes: `pipeline.phenology.compute_g_season(target_doy: int, profile: dict) -> float` (Task 1).
- Produces: `stands["G_season"]` column (float, same value for every stand in a run) on `run_poc`'s returned GeoDataFrame; `stands.attrs["diagnostics"]["g_season"]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_orchestrate.py` (same fixtures as the existing `test_run_poc_uses_target_date_not_today_for_climatology_day_of_year`, which already monkeypatches `orchestrate_mod.date` -- reuse that pattern):

```python
def test_run_poc_exposes_g_season_per_stand_and_in_diagnostics():
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
        target_date=date(2026, 9, 15),  # GBIF monthly maximum, G_season == 1.0
    )
    assert result["G_season"].tolist() == pytest.approx([1.0, 1.0])
    assert result.attrs["diagnostics"]["g_season"] == pytest.approx(1.0)


def test_run_poc_g_season_reduces_f_relative_to_hardcoded_one(monkeypatch):
    import pipeline.orchestrate as orchestrate_mod

    class _FrozenDate(date):
        _today = date(2026, 1, 1)

        @classmethod
        def today(cls):
            return cls._today

    monkeypatch.setattr(orchestrate_mod, "date", _FrozenDate)
    result = run_poc(
        layer="BDL:RDLP_Katowice_wydzielenia",
        bbox_2180=BBOX,
        profile=PROFILE,
        bdl_fetcher=fake_bdl_fetcher,
        weather_fetcher=fake_weather_fetcher,
        climatology_fetcher=fake_climatology_fetcher,
        grid_spacing_m=5000.0,
        past_days=30,
        target_date=date(2026, 1, 1),  # deep winter -- G_season floors near 0.05
    )
    assert result["G_season"].iloc[0] == pytest.approx(PROFILE["phenology"]["g_season_floor"], abs=0.01)
    # F = G_season * M^0.6 * T^0.4 * K_frost, so a floored G_season pulls F
    # down close to that same floor (M/T/K_frost each <= 1.0 by construction).
    assert result["F"].iloc[0] < 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_orchestrate.py -k g_season -v`
Expected: FAIL with `KeyError: 'G_season'`

- [ ] **Step 3: Implement**

In `pipeline/orchestrate.py`, add the import:

```python
from pipeline.phenology import compute_g_season
```

After line 131 (`target_doy = target_date.timetuple().tm_yday`), add:

```python
    # Plan 2.1 "Zmiana 1": one G_season value per run (it depends only on
    # target_date, not on any per-stand attribute), reused for every stand
    # below -- same "compute once, same value for every stand" shape as
    # forecast_days.
    g_season = compute_g_season(target_doy, profile)
```

Change line 204 from:

```python
        f = compute_fruiting(m, t, k_frost, g_season=1.0)
```

to:

```python
        f = compute_fruiting(m, t, k_frost, g_season=g_season)
```

After the `stands["forecast_days"] = forecast_days` line, add:

```python
    stands["G_season"] = g_season
```

In the `stands.attrs["diagnostics"] = {...}` dict, add the entry:

```python
        "g_season": g_season,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_orchestrate.py -v`
Expected: PASS (all existing + 2 new tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/orchestrate.py tests/test_orchestrate.py
git commit -m "feat: wire G_season into run_poc's compute_fruiting call (plan 2.1 Zmiana 1, step 2/4)"
```

---

## Task 3: G_season explanation note

**Files:**
- Modify: `pipeline/explain.py` (new `g_season_note` function), `pipeline/mvp.py:129-142` (wire it into the explanation loop)
- Test: `tests/test_explain.py`, `tests/test_mvp.py`

**Interfaces:**
- Consumes: `row["G_season"]` (Task 2's new column), `profile["phenology"]["g_season_note_threshold"]` (Task 1).
- Produces: `pipeline.explain.g_season_note(g_season: float, profile: dict) -> dict | None`, appended to each stand's `explanation` list.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_explain.py`:

```python
from pipeline.explain import g_season_note


def test_g_season_note_none_when_at_or_above_threshold():
    assert g_season_note(0.5, PROFILE) is None
    assert g_season_note(1.0, PROFILE) is None


def test_g_season_note_present_and_worded_when_below_threshold():
    note = g_season_note(0.3, PROFILE)
    assert note is not None
    assert note["factor"] == "g_season"
    assert note["text"] == "poza szczytem sezonu (G_season=0.30)"
    assert note["contribution"] == pytest.approx(0.3 - 1.0)
```

(`PROFILE` is already imported/defined at the top of `tests/test_explain.py` via `load_profile("profiles/boletus_edulis.yaml")` -- reuse it; add the import if the file doesn't already have `pytest` imported.)

Add to `tests/test_mvp.py`:

```python
def test_enrich_adds_g_season_explanation_note_when_below_threshold():
    stands = _scored_stands()
    stands["G_season"] = [0.2, 1.0]  # A: deep off-season, B: peak season
    result = enrich_with_mvp_layers(
        stands, PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=0,
    )
    exp_a = result[result["stand_id"] == "A"].iloc[0]["explanation"]
    exp_b = result[result["stand_id"] == "B"].iloc[0]["explanation"]
    assert any(e["factor"] == "g_season" for e in exp_a)
    assert not any(e["factor"] == "g_season" for e in exp_b)


def test_enrich_defaults_g_season_to_one_when_column_absent():
    # Older/synthetic callers that don't set G_season (e.g. _scored_stands
    # itself, most other tests in this file) must not crash or spuriously
    # add the note.
    result = enrich_with_mvp_layers(
        _scored_stands(), PROFILE, _no_gdos(), _no_osm_features(),
        zakaz_checker=lambda lat, lon: False, top_n_for_ban_check=0,
    )
    for exp in result["explanation"]:
        assert not any(e["factor"] == "g_season" for e in exp)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_explain.py tests/test_mvp.py -k g_season -v`
Expected: FAIL with `ImportError: cannot import name 'g_season_note'`

- [ ] **Step 3: Implement**

Add to `pipeline/explain.py` (after `TEMPLATES`, before `compute_log_contributions`):

```python
def g_season_note(g_season: float, profile: dict) -> dict | None:
    """Plan 2.1 "Zmiana 1": a flat, threshold-based note (NOT part of the
    ranked contributions/generate_explanation pool above) -- G_season is
    the same value for every stand in a run, so a log-contribution against
    an area median (like host/site/age/moisture/...) would always be 0 and
    never surface it. Returns None when g_season is at or above
    profile["phenology"]["g_season_note_threshold"] (no note needed)."""
    threshold = profile["phenology"]["g_season_note_threshold"]
    if g_season >= threshold:
        return None
    return {
        "factor": "g_season",
        "contribution": g_season - 1.0,
        "text": f"poza szczytem sezonu (G_season={g_season:.2f})",
    }
```

In `pipeline/mvp.py`, change the import line:

```python
from pipeline.explain import compute_log_contributions, generate_explanation, g_season_note
```

Change the explanation loop (around line 129-142) from:

```python
    explanations = []
    for _, row in stands.iterrows():
        values = {_FACTOR_KEY_MAP[col]: row[col] for col in _EXPLANATION_FACTORS}
        values["pressure_factor"] = row["pressure_factor"]
        contributions = compute_log_contributions(values, area_medians)
        meta = {"species_cd": row.get("species_cd"), "site_type": row.get("site_type"),
                 "age": row.get("spec_age"), "P": row.get("P", 0.0),
                 "part_cd": row.get("part_cd"),
                 "host_affinity": host_affinity(row.get("species_cd"), profile)}
        explanations.append(generate_explanation(contributions, values, meta, profile))
    stands["explanation"] = explanations
```

to:

```python
    explanations = []
    for _, row in stands.iterrows():
        values = {_FACTOR_KEY_MAP[col]: row[col] for col in _EXPLANATION_FACTORS}
        values["pressure_factor"] = row["pressure_factor"]
        contributions = compute_log_contributions(values, area_medians)
        meta = {"species_cd": row.get("species_cd"), "site_type": row.get("site_type"),
                 "age": row.get("spec_age"), "P": row.get("P", 0.0),
                 "part_cd": row.get("part_cd"),
                 "host_affinity": host_affinity(row.get("species_cd"), profile)}
        explanation = generate_explanation(contributions, values, meta, profile)
        # Plan 2.1 "Zmiana 1": G_season absent (older/synthetic caller,
        # e.g. most of tests/test_mvp.py) defaults to 1.0 -- no note, exact
        # pre-this-step behaviour.
        note = g_season_note(row.get("G_season", 1.0), profile)
        if note is not None:
            explanation.append(note)
        explanations.append(explanation)
    stands["explanation"] = explanations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_explain.py tests/test_mvp.py -v`
Expected: PASS (all existing + 4 new tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/explain.py pipeline/mvp.py tests/test_explain.py tests/test_mvp.py
git commit -m "feat: add G_season explanation note when significantly off-peak (plan 2.1 Zmiana 1, step 3/4)"
```

---

## Task 4: Export G_season to scores_{day}.json + frontend

**Files:**
- Modify: `pipeline/export.py:7-19` (`SCORE_FIELDS`), `tests/test_export.py` (`_enriched_stands` fixture + new tests)
- Modify: `frontend/src/model.ts` (`Score` type, `parseData` validation)
- Test: `frontend/src/model.test.ts`

**Interfaces:**
- Produces: `record["G_season"]` in every `scores_{day}.json` entry; `Score.G_season?: number | null` in the frontend.

- [ ] **Step 1: Write the failing Python test**

Add to `tests/test_export.py`, and add `"G_season": [0.91, 1.0]` to the `_enriched_stands()` fixture (right after `"forecast_days": [1, 1],`):

```python
def test_build_score_record_includes_g_season():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["G_season"] == pytest.approx(0.91)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export.py -k g_season -v`
Expected: FAIL with `KeyError: 'G_season'`

- [ ] **Step 3: Implement (Python)**

In `pipeline/export.py`, add `"G_season"` to `SCORE_FIELDS`:

```python
SCORE_FIELDS = [
    "stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation",
    "distance_method", "entrance_status", "d_park_m",
    "forecast_days",
    # Plan 2.1 "Zmiana 1": seasonal fruiting-frequency multiplier for this
    # run's target_date (pipeline.phenology.compute_g_season) -- same value
    # for every stand in one export.
    "G_season",
    "s_host_source", "s_host_package_date",
]
```

- [ ] **Step 4: Run Python test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: PASS (all existing + 1 new test)

- [ ] **Step 5: Write the failing frontend test**

Add to the `describe("data and classification", ...)` block in `frontend/src/model.test.ts`, reusing that file's own `score(id, r, mask)` helper and top-level `stands` fixture (both already defined near the top of the file, ids `"A"`/`"B"`):

```ts
it("accepts an optional G_season field and still loads without it", () => {
  const scores = [
    { ...score("A", 40), G_season: 0.42 },
    score("B", 30), // no G_season -- older export
  ];
  const result = parseData(scores, stands);
  expect(result.scores.map((s) => s.G_season)).toEqual([0.42, undefined]);
});
```

- [ ] **Step 6: Run frontend test to verify it fails**

Run: `cd frontend && npm test -- -t "G_season"`
Expected: FAIL (TypeScript error: `Object literal may only specify known properties`, or the assertion fails since `G_season` isn't parsed through)

- [ ] **Step 7: Implement (frontend)**

In `frontend/src/model.ts`, add to the `Score` type (after `area_ha?: number | null;`):

```ts
  // Plan 2.1 "Zmiana 1": seasonal fruiting-frequency multiplier, same
  // shape as area_ha above -- optional so older exports (before this
  // field existed) still load.
  G_season?: number | null;
```

In `parseData`'s scores-array validation predicate, add `(s.G_season === undefined || numeric(s.G_season)) &&` next to the existing `(s.area_ha === undefined || numeric(s.area_ha)) &&` line.

- [ ] **Step 8: Run frontend test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (all existing + 1 new test)

- [ ] **Step 9: Commit**

```bash
git add pipeline/export.py tests/test_export.py frontend/src/model.ts frontend/src/model.test.ts
git commit -m "feat: export G_season to scores_{day}.json and the frontend Score type (plan 2.1 Zmiana 1, step 4/4)"
```

---

## Task 5: Moisture midpoint calibration (0.35 → 0.50)

**Files:**
- Modify: `profiles/boletus_edulis.yaml:111`

**Interfaces:**
- None (pure config change; `pipeline.scoring.score_moisture` already reads `cfg["moisture_midpoint"]` from the profile).

This task has no new unit test (the existing `tests/test_scoring.py::test_score_moisture_at_midpoint_is_half` already asserts the general midpoint property against whatever `profile["fruiting"]["moisture_midpoint"]` is, via its own inline fixture profile dict, not the real YAML -- check this before starting).

- [ ] **Step 1: Confirm no test hard-codes the old midpoint value**

Run: `grep -rn "0\.35" tests/ profiles/`
Expected: only `profiles/boletus_edulis.yaml:111` itself (`moisture_midpoint: 0.35`) and possibly an unrelated `0.35`-valued constant elsewhere (e.g. `dry_pct_threshold: 0.3` is not `0.35` -- check the actual grep output before proceeding; if a test does hard-code `0.35` as this profile's real midpoint, update that assertion in the same commit as Step 2 below).

- [ ] **Step 2: Change the profile**

In `profiles/boletus_edulis.yaml`, change line 111 from:

```yaml
  moisture_midpoint: 0.35
```

to:

```yaml
  # Plan 2.1 "Zmiana 2" (user review 2026-09-25): 0.35 meant the AVERAGE
  # moisture percentile (0.5) already scored M=0.82 -> F="Bardzo dobre" --
  # confirmed on the real Bedziemysl 2026-09-25 export, where ALL 3656
  # mask-passing stands classified "Bardzo dobre" (zero differentiation
  # from F). 0.50 makes percentile 0.5 -> "Dobre" instead, matching the
  # intended reading of "average conditions". moisture_slope unchanged
  # per explicit user instruction -- do not change it without asking.
  moisture_midpoint: 0.50
```

- [ ] **Step 3: Run the full Python suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: PASS. If any test fails, it was silently depending on the old 0.35 midpoint value in a way Step 1's grep missed -- inspect it and update its expected numbers to match the new midpoint (do not revert the profile change).

- [ ] **Step 4: Compute and show the before/after scenario table**

Run this (no network, pure function calls) and include its output in the task's completion report:

```bash
./.venv/Scripts/python.exe -c "
import copy
from pipeline.habitat import load_profile
from pipeline.scoring import score_moisture, compute_fruiting, classify_fruiting

profile = load_profile('profiles/boletus_edulis.yaml')  # already has 0.50 after Step 2
old = copy.deepcopy(profile)
old['fruiting']['moisture_midpoint'] = 0.35

for label, p in [('before (0.35)', old), ('after (0.50)', profile)]:
    print(f'--- {label} ---')
    for pct in [0.15, 0.35, 0.50, 0.70, 0.90]:
        m = score_moisture(pct, pct, p)
        f = compute_fruiting(m, 1.0, 1.0, g_season=1.0)
        print(f'  percentile={pct:.2f} M={m:.3f} F={f:.3f} class={classify_fruiting(f, p)}')
"
```

Expected output (verified during planning, 2026-09-25):

```
--- before (0.35) ---
  percentile=0.15 M=0.119 F=0.279 class=Umiarkowane
  percentile=0.35 M=0.500 F=0.660 class=Dobre
  percentile=0.50 M=0.818 F=0.886 class=Bardzo dobre
  percentile=0.70 M=0.971 F=0.982 class=Bardzo dobre
  percentile=0.90 M=0.996 F=0.998 class=Bardzo dobre
--- after (0.50) ---
  percentile=0.15 M=0.029 F=0.120 class=Słabe warunki
  percentile=0.35 M=0.182 F=0.360 class=Umiarkowane
  percentile=0.50 M=0.500 F=0.660 class=Dobre
  percentile=0.70 M=0.881 F=0.927 class=Bardzo dobre
  percentile=0.90 M=0.982 F=0.989 class=Bardzo dobre
```

If the executor's own run reproduces different numbers, stop and report the discrepancy instead of continuing silently.

- [ ] **Step 5: Compute the real Będziemyśl before/after class distribution (no network)**

This reuses `cache/weather_points`/`cache/climatology_points`/`cache/bdl_tiles_v2`, already fully populated for lat=50.0555, lon=21.7889, radius_km=20, target_date=2026-09-25 (the last real run). A `call_api` that raises guarantees no network call is actually made:

```bash
./.venv/Scripts/python.exe -c "
import copy
from collections import Counter
from datetime import date
from functools import partial
from pathlib import Path

from pipeline.bdl import fetch_bdl
from pipeline.bdl_packages import load_packages
from pipeline.habitat import load_profile
from pipeline.orchestrate import run_poc
from pipeline.prepare_trip import _radius_scaled_spacing
from pipeline.rdlp import fetch_rdlp_boundaries_cached, resolve_rdlp_layer
from pipeline.scoring import classify_fruiting
from pipeline.search_area import search_tiles, fetch_search_stands, within_radius
from pipeline.tiles import tile_bbox_2180
from pipeline.weather import fetch_weather_raw, fetch_climatology_raw
from pipeline.orchestrate import WEATHER_GRID_SPACING_M, CLIMATOLOGY_GRID_SPACING_M

def _no_network(*args, **kwargs):
    raise AssertionError('network call attempted -- cache should have covered this')

cache_dir = Path('cache')
lat, lon, radius_km = 50.0555, 21.7889, 20.0
target_date = date(2026, 9, 25)

center, tiles = search_tiles(lat, lon, radius_km)
rdlp_gdf = fetch_rdlp_boundaries_cached(cache_dir)
layer = resolve_rdlp_layer(lat, lon, rdlp_gdf)
context_stands, _ = fetch_search_stands(tiles, rdlp_gdf, cache_dir, fetch_bdl)
stands = within_radius(context_stands, center, radius_km)
package_index = load_packages(cache_dir / 'bdl_packages')
bbox = tile_bbox_2180(lat, lon, size_km=2 * radius_km)
grid_spacing_m = _radius_scaled_spacing(WEATHER_GRID_SPACING_M, radius_km)
climatology_grid_spacing_m = _radius_scaled_spacing(CLIMATOLOGY_GRID_SPACING_M, radius_km)

profile_after = load_profile('profiles/boletus_edulis.yaml')
profile_before = copy.deepcopy(profile_after)
profile_before['fruiting']['moisture_midpoint'] = 0.35

for label, profile in [('before (0.35)', profile_before), ('after (0.50)', profile_after)]:
    result = run_poc(
        layer=layer, bbox_2180=bbox, profile=profile,
        bdl_fetcher=lambda _l, _b: stands.copy(),
        weather_fetcher=partial(fetch_weather_raw, call_api=_no_network, cache_dir=cache_dir),
        climatology_fetcher=partial(fetch_climatology_raw, call_api=_no_network, cache_dir=cache_dir),
        grid_spacing_m=grid_spacing_m, climatology_grid_spacing_m=climatology_grid_spacing_m,
        target_date=target_date, package_index=package_index,
    )
    masked = result[result['mask']]
    print(label, 'n=', len(masked))
    print('  F classes:', Counter(classify_fruiting(f, profile) for f in masked['F']))
    print('  F_loc classes:', Counter(classify_fruiting(f, profile) for f in masked['F_loc']))
"
```

Report this output verbatim in the task's completion summary — this is the "rozkład klas F ... na realnym eksporcie Będziemyśla z cache" the user asked to see. **If the resulting class distribution still looks degenerate (e.g. still ~100% in one class) after this change, propose a `fruiting_classes` adjustment but do not edit `profiles/boletus_edulis.yaml`'s `fruiting_classes` block without explicit user approval** — stop and ask instead.

- [ ] **Step 6: Commit**

```bash
git add profiles/boletus_edulis.yaml
git commit -m "fix: recalibrate moisture_midpoint 0.35 -> 0.50 so average conditions read as Dobre not Bardzo dobre (plan 2.1 Zmiana 2)"
```

---

## Task 6: Tie-break module (ground cover + stand density)

**Files:**
- Create: `pipeline/tie_break.py`
- Modify: `profiles/boletus_edulis.yaml` (no new keys needed -- tie-break's preference tables are deliberately code constants, not profile config, matching this module's "never touches scoring config either" spirit; see Task 6 docstring)
- Test: `tests/test_tie_break.py`

**Interfaces:**
- Produces: `pipeline.tie_break.TieBreakRaw` (dataclass: `veg_cover_cd: str | None`, `standdensity_index: float | None`), `pipeline.tie_break.load_tie_break_raw(packages_dir: Path) -> dict[str, TieBreakRaw]`, `pipeline.tie_break.compute_tie_break(veg_cover_cd: str | None, standdensity_index: float | None) -> float`, `pipeline.tie_break.tie_break_for_stand(adr_for: str, index: dict[str, TieBreakRaw]) -> float`, `pipeline.tie_break.veg_cover_label(veg_cover_cd: str | None) -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tie_break.py
import geopandas as gpd
import pytest
from shapely.geometry import box

from pipeline.tie_break import (
    TieBreakRaw, load_tie_break_raw, compute_tie_break, tie_break_for_stand, veg_cover_label,
)

_SUBAREA_HEADER = "arodes_int_num\ta_year\tarea_type_cd\tsite_type_cd\tmoisture_cd\tdegradation_cd\tsoil_subtype_cd\tplant_comm_cd\tstand_struct_cd\tforest_func_cd\tsilviculture_cd\trotation_age\tsub_area\tveg_cover_cd\tdamage_degree\tcause_cd\n"
_STOREY_HEADER = "arodes_int_num\ta_year\tdensity_cd\tmixture_cd\tstanddensity_index\ttree_stock_cd\tst_rank_order_act\tstorey_cd\n"


def _write_package(package_dir, subarea_rows, subarea_text, storey_text):
    package_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(subarea_rows, geometry=[box(0, 0, 100, 100)] * len(subarea_rows), crs="EPSG:2180")
    gdf.to_file(package_dir / "G_SUBAREA.shp")
    (package_dir / "f_subarea.txt").write_text(subarea_text, encoding="utf-8")
    (package_dir / "f_arod_storey.txt").write_text(storey_text, encoding="utf-8")


def test_load_tie_break_raw_returns_empty_dict_for_missing_directory(tmp_path):
    assert load_tie_break_raw(tmp_path / "does_not_exist") == {}


def test_load_tie_break_raw_full_record(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tŚCIO\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t0.9\t\t1\tDRZEW\n",
    )
    raw = load_tie_break_raw(tmp_path)["AA-1"]
    assert raw.veg_cover_cd == "SCIO"  # normalize_code transliterates the diacritic
    assert raw.standdensity_index == pytest.approx(0.9)


def test_load_tie_break_raw_blank_veg_cover_cell_is_none_not_nan(tmp_path):
    # Real-data quirk already hit twice in B2/B3 (pipeline.bdl_packages,
    # pipeline.bdl_package_details): a blank CELL in an existing row reads
    # as pandas NaN (float), not "". Must not crash json.dumps(allow_nan=False)
    # downstream (pipeline.export.build_details_record).
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\t\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t0.9\t\t1\tDRZEW\n",
    )
    raw = load_tie_break_raw(tmp_path)["AA-1"]
    assert raw.veg_cover_cd is None


def test_load_tie_break_raw_blank_density_index_cell_is_none(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tZAD\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t\t\t1\tDRZEW\n",
    )
    raw = load_tie_break_raw(tmp_path)["AA-1"]
    assert raw.standdensity_index is None


def test_load_tie_break_raw_dedupes_repeated_subarea_geometry_rows(tmp_path):
    # Same real-data quirk as pipeline.bdl_packages/bdl_package_details:
    # one wydzielenie can appear as several G_SUBAREA rows.
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}, {"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tZAD\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t0.9\t\t1\tDRZEW\n",
    )
    result = load_tie_break_raw(tmp_path)
    assert list(result.keys()) == ["AA-1"]


def test_veg_cover_label_known_codes():
    assert veg_cover_label("ZAD") == "zadarniona"
    assert veg_cover_label("SCIO") == "ścioła"
    assert veg_cover_label("MSZC") == "mszysto-czernicowa"
    assert veg_cover_label("NAGA") == "naga"


def test_veg_cover_label_none_for_missing_code():
    assert veg_cover_label(None) is None


def test_compute_tie_break_prefers_moss_litter_over_bare_ground():
    good = compute_tie_break("MSZC", 0.85)
    bad = compute_tie_break("NAGA", 0.85)
    assert good > bad


def test_compute_tie_break_prefers_intermediate_density_over_extremes():
    mid = compute_tie_break("ZAD", 0.85)
    sparse = compute_tie_break("ZAD", 0.1)
    dense = compute_tie_break("ZAD", 3.0)
    assert mid > sparse
    assert mid > dense


def test_compute_tie_break_neutral_when_both_missing():
    assert compute_tie_break(None, None) == pytest.approx(0.5)


def test_compute_tie_break_is_bounded_0_to_1():
    for veg in [None, "MSZC", "NAGA", "ZAD"]:
        for idx in [None, 0.0, 0.5, 1.0, 5.0]:
            value = compute_tie_break(veg, idx)
            assert 0.0 <= value <= 1.0


def test_tie_break_for_stand_falls_back_to_neutral_when_adr_for_uncovered():
    assert tie_break_for_stand("NOT-IN-INDEX", {}) == pytest.approx(0.5)


def test_tie_break_for_stand_uses_raw_entry_when_present():
    index = {"AA-1": TieBreakRaw(veg_cover_cd="MSZC", standdensity_index=0.85)}
    assert tie_break_for_stand("AA-1", index) == compute_tie_break("MSZC", 0.85)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_tie_break.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.tie_break'`

- [ ] **Step 3: Implement `pipeline/tie_break.py`**

```python
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.bdl import normalize_code

# Plan 2.1 "Zmiana 4" (user review 2026-09-25): ordinal preference among
# BDL veg_cover_cd (pokrycie gleby) values, verified against the
# Instrukcja Urzadzania Lasu's own "Wykaz skrotow i symboli stosowanych w
# opisach taksacyjnych" glossary (no in-package dictionary exists for this
# field -- confirmed absent from every f_*_dic.txt under
# cache/bdl_packages/*/). Meanings: ZAD=zadarniona (turfed), SZAD=silnie
# zadarniona (heavily turfed), SZCH=silnie zachwaszczona (heavily weedy),
# ZIEL=zielna (herbaceous), SCIO=sciola (needle/leaf litter),
# MSZ=mszysta (mossy), MSZC=mszysto-czernicowa (moss-bilberry),
# NAGA=naga (bare ground). MSZC/MSZ/SCIO (undisturbed forest floor) tier
# highest, ZAD/ZIEL (grassy/herbaceous, some disturbance) mid,
# SZAD/SZCH/NAGA (heavily disturbed/bare) lowest -- [E] ordinal preference
# for sorting only, not a validated ecological weight, never blended into H/R.
_VEG_COVER_LABELS = {
    "ZAD": "zadarniona",
    "SZAD": "silnie zadarniona",
    "SZCH": "silnie zachwaszczona",
    "ZIEL": "zielna",
    "SCIO": "ścioła",
    "MSZ": "mszysta",
    "MSZC": "mszysto-czernicowa",
    "NAGA": "naga",
}
_VEG_COVER_TIERS = {
    "MSZC": 1.0, "MSZ": 1.0, "SCIO": 1.0,
    "ZAD": 0.6, "ZIEL": 0.6,
    "SZAD": 0.2, "SZCH": 0.2, "NAGA": 0.2,
}
_NEUTRAL = 0.5  # missing data -- never penalized, never preferred


@dataclass(frozen=True)
class TieBreakRaw:
    """Raw per-wydzielenie inputs for compute_tie_break, from a BDL data
    package (plan 2.1 "Zmiana 4"). Deliberately its own module/dataclass,
    never imported by pipeline.orchestrate/habitat/scoring/mvp -- the same
    structural guarantee pipeline.bdl_package_details (B3) already uses,
    so this data cannot silently affect H/R_final."""

    veg_cover_cd: str | None
    standdensity_index: float | None


def veg_cover_label(veg_cover_cd: str | None) -> str | None:
    """Word form of a veg_cover_cd for display (details_{day}.json / the
    frontend card) -- no BDL dictionary exists for this field, so the 8
    codes seen in real Będziemyśl data are hard-coded here (see
    _VEG_COVER_LABELS' own comment for the source)."""
    if veg_cover_cd is None:
        return None
    return _VEG_COVER_LABELS.get(normalize_code(veg_cover_cd), veg_cover_cd)


def _veg_cover_score(veg_cover_cd: str | None) -> float:
    if veg_cover_cd is None:
        return _NEUTRAL
    return _VEG_COVER_TIERS.get(normalize_code(veg_cover_cd), _NEUTRAL)


def _density_index_score(standdensity_index: float | None) -> float:
    """Intermediate zadrzewienie (stand density index, f_arod_storey.
    standdensity_index on the DRZEW storey) preferred over very sparse or
    very dense stands, per user brief 2026-09-25 (Martinez-Pena et al.
    2012: too-sparse or too-dense stands are less productive, optimum
    intermediate). Real Będziemyśl DRZEW-storey data (n=13576, 100%
    filled): median 0.9, IQR 0.7-1.0, 92.9% <= 1.5, only 0.2% >= 2.0 --
    plateau across [0.7, 1.0], linear falloff to 0 at the edges (0.0 on
    the low side, 2.0 on the high side) -- [E] plan decision, ordinal
    preference for sorting only, not a validated ecological weight."""
    if standdensity_index is None:
        return _NEUTRAL
    idx = standdensity_index
    if 0.7 <= idx <= 1.0:
        return 1.0
    if idx < 0.7:
        return max(0.0, idx / 0.7)
    return max(0.0, 1.0 - (idx - 1.0) / 1.0)


def compute_tie_break(veg_cover_cd: str | None, standdensity_index: float | None) -> float:
    """0-1 ordinal secondary sort key (plan 2.1 "Zmiana 4") -- ground cover
    tier averaged with the density-index preference curve above. Used
    EXCLUSIVELY as a secondary sort key (pipeline.regions._summarize_cluster,
    frontend/src/model.ts's joinData) among wydzielenia whose R_final is
    otherwise tied at 2 decimal places -- never blended into H or R_final
    itself (see this module's own docstring for the structural, not just
    tested, guarantee)."""
    return 0.5 * _veg_cover_score(veg_cover_cd) + 0.5 * _density_index_score(standdensity_index)


def tie_break_for_stand(adr_for: str, index: dict[str, TieBreakRaw]) -> float:
    """Convenience wrapper for pipeline/prepare_trip.py's per-row loop --
    a stand whose adr_for isn't covered by any downloaded BDL package
    (index miss) gets the same neutral 0.5 compute_tie_break(None, None)
    would return for missing fields, never a crash."""
    raw = index.get(adr_for)
    if raw is None:
        return compute_tie_break(None, None)
    return compute_tie_break(raw.veg_cover_cd, raw.standdensity_index)


def _load_one_package(package_dir: Path) -> dict[str, TieBreakRaw]:
    g_subarea = gpd.read_file(package_dir / "G_SUBAREA.shp")[["a_i_num", "adr_for"]]
    g_subarea["a_i_num"] = g_subarea["a_i_num"].astype(str)
    g_subarea["adr_for"] = g_subarea["adr_for"].astype(str)
    # Same real-data quirk as pipeline.bdl_packages/bdl_package_details:
    # one wydzielenie can be stored as several G_SUBAREA rows.
    g_subarea = g_subarea.drop_duplicates(["a_i_num", "adr_for"])

    subarea = pd.read_csv(package_dir / "f_subarea.txt", sep="\t", dtype=str, encoding="utf-8")
    subarea["veg_cover_cd"] = subarea["veg_cover_cd"].str.strip().map(normalize_code)
    subarea = subarea.rename(columns={"arodes_int_num": "a_i_num"})
    subarea["a_i_num"] = subarea["a_i_num"].astype(str)
    subarea_joined = subarea.merge(g_subarea, on="a_i_num", how="inner")
    # A present row can still have a blank veg_cover_cd CELL -- reads as
    # pandas NaN (float), not "" (same class of bug already fixed twice in
    # pipeline.bdl_package_details -- isinstance check, not truthiness).
    veg_cover_by_stand = {
        adr_for: (cd if isinstance(cd, str) and cd else None)
        for adr_for, cd in zip(subarea_joined["adr_for"], subarea_joined["veg_cover_cd"])
    }

    storey = pd.read_csv(package_dir / "f_arod_storey.txt", sep="\t", dtype=str, encoding="utf-8")
    storey = storey.rename(columns={"arodes_int_num": "a_i_num"})
    storey["a_i_num"] = storey["a_i_num"].astype(str)
    storey["storey_cd"] = storey["storey_cd"].str.strip()
    drzew_storey = storey[storey["storey_cd"] == "DRZEW"].merge(g_subarea, on="a_i_num", how="inner")
    density_index_by_stand: dict[str, float | None] = {}
    for adr_for, raw in zip(drzew_storey["adr_for"], drzew_storey["standdensity_index"]):
        density_index_by_stand[adr_for] = float(raw) if isinstance(raw, str) and raw.strip() else None

    all_adr_for = set(veg_cover_by_stand) | set(density_index_by_stand)
    return {
        adr_for: TieBreakRaw(
            veg_cover_cd=veg_cover_by_stand.get(adr_for),
            standdensity_index=density_index_by_stand.get(adr_for),
        )
        for adr_for in all_adr_for
    }


def load_tie_break_raw(packages_dir: Path) -> dict[str, TieBreakRaw]:
    """Auto-discovers every unpacked BDL data package under `packages_dir`
    (same directories pipeline.bdl_packages.load_packages /
    pipeline.bdl_package_details.load_package_details read) and indexes
    veg_cover_cd + standdensity_index by adr_for. Missing/empty directory,
    or a subdirectory missing the required files, returns {} / skips it,
    never raises -- pipeline.tie_break.tie_break_for_stand's neutral
    fallback handles the resulting misses."""
    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        return {}
    index: dict[str, TieBreakRaw] = {}
    required = ("G_SUBAREA.shp", "f_subarea.txt", "f_arod_storey.txt")
    for package_dir in sorted(p for p in packages_dir.iterdir() if p.is_dir()):
        if not all((package_dir / name).exists() for name in required):
            continue
        index.update(_load_one_package(package_dir))
    return index
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_tie_break.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/tie_break.py tests/test_tie_break.py
git commit -m "feat: add tie_break module for ground cover + stand density ordinal preference (plan 2.1 Zmiana 4, step 1/4)"
```

---

## Task 7: Wire tie_break into prepare_trip.py + region-sort regression test

**Files:**
- Modify: `pipeline/prepare_trip.py` (imports; compute `enriched["tie_break"]` before `group_into_regions`)
- Test: `tests/test_prepare_trip.py`

**Interfaces:**
- Consumes: `pipeline.tie_break.load_tie_break_raw`, `pipeline.tie_break.tie_break_for_stand` (Task 6).
- Produces: `enriched["tie_break"]` column, present before `pipeline.regions.group_into_regions` is called (Task 8 depends on this).

- [ ] **Step 1: Write the failing regression test**

Add to `tests/test_prepare_trip.py`, mirroring `_enriched_for_b3_regression`/`test_b3_detail_card_step_does_not_change_r_or_h`:

```python
def test_tie_break_step_does_not_change_r_or_h(tmp_path):
    # Plan 2.1 "Zmiana 4": computing tie_break (before group_into_regions)
    # must have zero effect on R_final/H -- pipeline.tie_break is never
    # imported by pipeline.orchestrate/habitat/scoring/mvp (structural
    # guarantee), this is the explicit regression check, same pattern as
    # the B3 detail-card regression test above.
    enriched = _enriched_for_b3_regression()
    r_before = enriched["R_final"].copy()
    h_before = enriched["H"].copy()

    empty_packages_dir = tmp_path / "bdl_packages"  # no packages cached -- the common case
    tie_break_raw_index = load_tie_break_raw(empty_packages_dir)
    enriched["tie_break"] = [
        tie_break_for_stand(row["adr_for"], tie_break_raw_index) for _, row in enriched.iterrows()
    ]

    pd.testing.assert_series_equal(enriched["R_final"], r_before)
    pd.testing.assert_series_equal(enriched["H"], h_before)
    assert enriched["tie_break"].tolist() == [0.5, 0.5]  # neutral -- no package data
```

Add the import at the top of `tests/test_prepare_trip.py`: `from pipeline.tie_break import load_tie_break_raw, tie_break_for_stand`.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_prepare_trip.py -k tie_break -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement**

In `pipeline/prepare_trip.py`, add the import (alongside the other `pipeline.*` imports near the top):

```python
from pipeline.tie_break import load_tie_break_raw, tie_break_for_stand
```

In `run_trip_preparation`, insert the tie_break computation between the `enrich_with_mvp_layers(...)` call and the `group_into_regions(...)` call (it must run BEFORE `group_into_regions`, since Task 8 uses `enriched["tie_break"]` as a secondary sort key inside it):

```python
    print("Enriching with legal mask + presja + confidence + explanations...")
    enriched = enrich_with_mvp_layers(
        scored, profile, gdos_gdf, osm_features,
        zakaz_checker=check_periodic_ban, top_n_for_ban_check=50,
        roads_routing_gdf=osm_features["roads"], entrances_gdf=entrances,
        top_n_for_routing=profile["entrances"]["top_n_for_routing"],
    )

    # Plan 2.1 "Zmiana 4": must run before group_into_regions below --
    # pipeline.regions._summarize_cluster uses tie_break as a secondary
    # sort key for region member ordering. Reuses the same
    # cache/bdl_packages/ directory as load_packages/load_package_details
    # above; a stand whose adr_for isn't covered gets a neutral 0.5
    # (pipeline.tie_break.tie_break_for_stand).
    tie_break_raw_index = load_tie_break_raw(cache_dir / "bdl_packages")
    enriched["tie_break"] = [
        tie_break_for_stand(row["adr_for"], tie_break_raw_index) for _, row in enriched.iterrows()
    ]

    print("Grouping into search regions...")
    regions = group_into_regions(enriched, profile)
```

Also thread `tie_break_raw_index` down to the B3 detail-card block, since Task 9 will need it for `write_details_json` (avoids a duplicate `load_tie_break_raw` call):

```python
    print("Building wydzielenie detail cards (paczka BDL + sasiedztwo)...")
    dictionaries = load_dictionaries(cache_dir / "bdl_packages")
    package_details_index = load_package_details(cache_dir / "bdl_packages")
    neighbors_by_stand = {
        row["adr_for"]: find_neighbor_labels(row, context_stands, dictionaries)
        for _, row in enriched.iterrows()
    }
```

(no change to this block yet -- Task 9 will add `tie_break_raw_index` to the `write_details_json(...)` call below it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_prepare_trip.py -v`
Expected: PASS (all existing + 1 new test)

- [ ] **Step 5: Commit**

```bash
git add pipeline/prepare_trip.py tests/test_prepare_trip.py
git commit -m "feat: wire tie_break computation into run_trip_preparation before region grouping (plan 2.1 Zmiana 4, step 2/4)"
```

---

## Task 8: Use tie_break as secondary sort key for region member ordering

**Files:**
- Modify: `pipeline/regions.py:56-69` (`_summarize_cluster`)
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: `members["tie_break"]` column when present (falls back to a neutral constant when absent, so every existing `tests/test_regions.py` fixture that doesn't set this column keeps passing unmodified).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_regions.py`:

```python
def test_summarize_cluster_stand_ids_ordered_by_r_final_then_tie_break():
    members = gpd.GeoDataFrame({
        "stand_id": ["low_tb", "high_tb", "third"],
        "R_final": [50.001, 50.004, 40.0],  # first two round to 50.00 at 2 decimals -- tied
        "tie_break": [0.2, 0.9, 0.5],
        "geometry": [box(0, 0, 10, 10), box(10, 10, 20, 20), box(20, 20, 30, 30)],
    }, crs="EPSG:2180")
    summary = _summarize_cluster(members, top_n=3)
    assert summary["stand_ids"] == ["high_tb", "low_tb", "third"]


def test_summarize_cluster_falls_back_to_neutral_tie_break_when_column_absent():
    # Existing callers/fixtures that don't set a "tie_break" column (most
    # of this file) must keep their current ordering, not crash.
    members = gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "R_final": [50.0, 40.0],
        "geometry": [box(0, 0, 10, 10), box(10, 10, 20, 20)],
    }, crs="EPSG:2180")
    summary = _summarize_cluster(members, top_n=2)
    assert summary["stand_ids"] == ["A", "B"]


def test_group_into_regions_on_a_uniform_r_cluster_orders_members_by_tie_break():
    # Same dense, uniformly-excellent grid as
    # test_group_into_regions_on_a_synthetic_continuous_forest_does_not_produce_one_giant_region
    # above (all R_final tied at 90.0, so no member ordering signal comes
    # from R at all) -- with a distinct tie_break per stand added, member
    # order within the accepted region must follow it, not spatial-index
    # iteration order.
    grid_n = 31
    spacing = 200.0
    rows = []
    counter = 0
    for i in range(grid_n):
        for j in range(grid_n):
            x = 380000 + i * spacing
            y = 486000 + j * spacing
            rows.append({
                "stand_id": f"G{i}_{j}", "R_final": 90.0, "mask_full": True,
                "tie_break": (counter % 100) / 100.0,
                "geometry": box(x, y, x + 100.0, y + 100.0),
            })
            counter += 1
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")

    profile = _regions_profile(top_pct=1.0, radius_m=800.0, min_area_ha=5.0, min_separation_m=3000.0, max_regions=5)
    result = group_into_regions(stands, profile)

    assert len(result) >= 1
    tie_break_by_id = dict(zip(stands["stand_id"], stands["tie_break"]))
    for _, region in result.iterrows():
        member_tie_breaks = [tie_break_by_id[sid] for sid in region["stand_ids"]]
        assert member_tie_breaks == sorted(member_tie_breaks, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_regions.py -k tie_break -v`
Expected: FAIL — `test_summarize_cluster_stand_ids_ordered_by_r_final_then_tie_break` and `test_group_into_regions_on_a_uniform_r_cluster_orders_members_by_tie_break` both fail (current `stand_ids` order is whatever `members`/spatial-index iteration order was, not R/tie_break-sorted); the neutral-fallback test may already pass by coincidence (confirm which, don't assume).

- [ ] **Step 3: Implement**

Change `_summarize_cluster` in `pipeline/regions.py` from:

```python
def _summarize_cluster(members: gpd.GeoDataFrame, top_n: int) -> dict:
    """Region score = median R_final of the top `top_n` candidate stands in
    the cluster (spec §5.6 step 3) -- deliberately not a sum, so a large
    forest complex full of just-above-threshold stands does not
    automatically outrank a small complex of a few excellent stands. If the
    cluster has fewer than `top_n` members, `.head(top_n)` on a short frame
    just returns what's there -- no special-casing needed."""
    top = members.sort_values("R_final", ascending=False).head(top_n)
    return {
        "rank_score": float(top["R_final"].median()),
        "stand_count": int(len(members)),
        "stand_ids": members["stand_id"].tolist(),
        "geometry": unary_union(list(members.geometry)),
    }
```

to:

```python
def _summarize_cluster(members: gpd.GeoDataFrame, top_n: int) -> dict:
    """Region score = median R_final of the top `top_n` candidate stands in
    the cluster (spec §5.6 step 3) -- deliberately not a sum, so a large
    forest complex full of just-above-threshold stands does not
    automatically outrank a small complex of a few excellent stands. If the
    cluster has fewer than `top_n` members, `.head(top_n)` on a short frame
    just returns what's there -- no special-casing needed.

    `stand_ids`' own ORDER (plan 2.1 "Zmiana 4"): R_final rounded to 2
    decimal places, then pipeline.tie_break's ground-cover/density
    preference as a secondary key among stands tied at that precision --
    same 2-decimal precision as frontend/src/model.ts's joinData sort,
    chosen against a real Będziemyśl export (top-500 R_final: 2 decimals
    groups only near-exact ties, max group size 4, vs. whole-point
    rounding's max group size 67 -- too coarse, would let tie_break
    override R's own ranking signal). A "tie_break" column absent (older
    caller/test fixture) falls back to a neutral constant for every row,
    which combined with `kind="stable"` reproduces the exact pre-this-step
    order."""
    top = members.sort_values("R_final", ascending=False).head(top_n)
    ordered = members.assign(
        _r_round=members["R_final"].round(2),
        _tie_break=members.get("tie_break", 0.5),
    ).sort_values(["_r_round", "_tie_break"], ascending=[False, False], kind="stable")
    return {
        "rank_score": float(top["R_final"].median()),
        "stand_count": int(len(members)),
        "stand_ids": ordered["stand_id"].tolist(),
        "geometry": unary_union(list(members.geometry)),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_regions.py -v`
Expected: PASS (all existing tests unchanged + 3 new tests). Existing `test_summarize_cluster_stand_ids_and_count` uses `sorted(summary["stand_ids"]) == ["A", "B"]` (order-insensitive), so it's unaffected by this change.

- [ ] **Step 5: Commit**

```bash
git add pipeline/regions.py tests/test_regions.py
git commit -m "feat: order region member stand_ids by rounded R_final then tie_break (plan 2.1 Zmiana 4, step 3/4)"
```

---

## Task 9: Export tie_break + veg_cover/density card fields

**Files:**
- Modify: `pipeline/export.py:7-19` (`SCORE_FIELDS`), `pipeline/export.py:113-169` (`build_details_record`, `write_details_json`)
- Modify: `pipeline/prepare_trip.py` (thread `tie_break_raw_index` into `write_details_json`)
- Modify: `tests/test_prepare_trip.py` (`_enriched_for_b3_regression` fixture + regression test call)
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `record["tie_break"]` in `scores_{day}.json`; `record["veg_cover"]`/`record["standdensity_index"]` in `details_{day}.json`.
- Consumes: `pipeline.tie_break.TieBreakRaw`, `pipeline.tie_break.veg_cover_label` (Task 6).

- [ ] **Step 1: Write the failing tests**

Add `"tie_break": [0.75, 0.5]` to `_enriched_stands()` in `tests/test_export.py` (after `"s_host_package_date": ["2026-06-23", None],`), then add:

```python
def test_build_score_record_includes_tie_break():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["tie_break"] == pytest.approx(0.75)


def test_build_details_record_includes_veg_cover_and_density_index_with_package():
    tie_break_index = {"AA-1": TieBreakRaw(veg_cover_cd="MSZC", standdensity_index=0.9)}
    record = build_details_record(
        "AA-1@2026", "AA-1", "DRZEW", None, "2026-09-25",
        {}, {}, {}, tie_break_index,
    )
    assert record["veg_cover"] == "mszysto-czernicowa"
    assert record["standdensity_index"] == pytest.approx(0.9)


def test_build_details_record_veg_cover_and_density_index_null_without_coverage():
    record = build_details_record(
        "AA-1@2026", "AA-1", "DRZEW", None, "2026-09-25",
        {}, {}, {}, {},
    )
    assert record["veg_cover"] is None
    assert record["standdensity_index"] is None
```

Add the import at the top of `tests/test_export.py`: `from pipeline.tie_break import TieBreakRaw`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export.py -k "tie_break or veg_cover" -v`
Expected: FAIL — `KeyError`/`TypeError: build_details_record() takes ... positional arguments but 9 were given`.

- [ ] **Step 3: Implement**

In `pipeline/export.py`, add the import:

```python
from pipeline.tie_break import TieBreakRaw, veg_cover_label
```

Add `"tie_break"` to `SCORE_FIELDS`:

```python
SCORE_FIELDS = [
    "stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation",
    "distance_method", "entrance_status", "d_park_m",
    "forecast_days",
    "G_season",
    "s_host_source", "s_host_package_date",
    # Plan 2.1 "Zmiana 4": ground-cover/density ordinal secondary sort key
    # (pipeline.tie_break) -- presentation-only, see that module's docstring.
    "tie_break",
]
```

Change `build_details_record`'s signature and body from:

```python
def build_details_record(stand_id: str, adr_for: str, stand_stru, prot_categ, day: str,
                           package_details_index: dict, neighbors_by_stand: dict, dictionaries: dict) -> dict:
    """..."""
    details = package_details_index.get(adr_for)
    prot_categ_name = None
    if prot_categ is not None and not (isinstance(prot_categ, float) and math.isnan(prot_categ)):
        prot_categ_name = dictionaries.get("prot_categ", {}).get(prot_categ, prot_categ)
    return {
        "stand_id": stand_id,
        "day": day,
        "drzew_species": _species_entries(details.drzew_species, dictionaries) if details else [],
        "density": (
            dictionaries.get("density", {}).get(details.density_cd, details.density_cd)
            if details and details.density_cd else None
        ),
        "podszyt_species": _species_entries(details.podszyt_species, dictionaries) if details else [],
        "soil_type": (
            dictionaries.get("soil_subtype", {}).get(details.soil_subtype_cd, details.soil_subtype_cd)
            if details and details.soil_subtype_cd else None
        ),
        "package_date": details.package_date if details else None,
        "neighbors": neighbors_by_stand.get(adr_for, []),
        "stand_stru": _json_safe(stand_stru),
        "prot_categ": prot_categ_name,
    }
```

to:

```python
def build_details_record(stand_id: str, adr_for: str, stand_stru, prot_categ, day: str,
                           package_details_index: dict, neighbors_by_stand: dict, dictionaries: dict,
                           tie_break_index: dict) -> dict:
    """One card's worth of plan 2.1 step B3 detail (spec §5.3 pkt 3) plus,
    since plan 2.1 "Zmiana 4", ground cover (word form) and the stand
    density index -- from pipeline.tie_break, empty/null when `adr_for`
    isn't covered by any package. Purely additive presentation fields:
    never touches H/F/R (see pipeline.tie_break's own module docstring)."""
    details = package_details_index.get(adr_for)
    prot_categ_name = None
    if prot_categ is not None and not (isinstance(prot_categ, float) and math.isnan(prot_categ)):
        prot_categ_name = dictionaries.get("prot_categ", {}).get(prot_categ, prot_categ)
    tie_break_raw = tie_break_index.get(adr_for)
    return {
        "stand_id": stand_id,
        "day": day,
        "drzew_species": _species_entries(details.drzew_species, dictionaries) if details else [],
        "density": (
            dictionaries.get("density", {}).get(details.density_cd, details.density_cd)
            if details and details.density_cd else None
        ),
        "podszyt_species": _species_entries(details.podszyt_species, dictionaries) if details else [],
        "soil_type": (
            dictionaries.get("soil_subtype", {}).get(details.soil_subtype_cd, details.soil_subtype_cd)
            if details and details.soil_subtype_cd else None
        ),
        "package_date": details.package_date if details else None,
        "neighbors": neighbors_by_stand.get(adr_for, []),
        "stand_stru": _json_safe(stand_stru),
        "prot_categ": prot_categ_name,
        "veg_cover": veg_cover_label(tie_break_raw.veg_cover_cd) if tie_break_raw else None,
        "standdensity_index": _json_safe(tie_break_raw.standdensity_index) if tie_break_raw else None,
    }
```

Change `write_details_json`'s signature and body from:

```python
def write_details_json(stands: gpd.GeoDataFrame, package_details_index: dict, neighbors_by_stand: dict,
                         dictionaries: dict, day: str, out_path) -> pathlib.Path:
    """..."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        build_details_record(
            row["stand_id"], row["adr_for"], row.get("stand_stru"), row.get("prot_categ"),
            day, package_details_index, neighbors_by_stand, dictionaries,
        )
        for _, row in stands.iterrows()
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path
```

to:

```python
def write_details_json(stands: gpd.GeoDataFrame, package_details_index: dict, neighbors_by_stand: dict,
                         dictionaries: dict, day: str, out_path, tie_break_index: dict) -> pathlib.Path:
    """... (same docstring as before, plus:) `tie_break_index` (plan 2.1
    "Zmiana 4"): pipeline.tie_break.load_tie_break_raw's adr_for -> raw
    output, used only to render veg_cover/standdensity_index on the card
    (build_details_record) -- the numeric tie_break sort value itself
    lives in scores_{day}.json, not here."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        build_details_record(
            row["stand_id"], row["adr_for"], row.get("stand_stru"), row.get("prot_categ"),
            day, package_details_index, neighbors_by_stand, dictionaries, tie_break_index,
        )
        for _, row in stands.iterrows()
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path
```

Update every other `build_details_record`/`write_details_json` call site in `tests/test_export.py` (the existing tests `test_build_details_record_full_shape_with_package`, `test_build_details_record_empty_package_fields_when_no_package`, `test_build_details_record_neighbors_and_stand_stru_present_without_package`, `test_build_details_record_falls_back_to_raw_code_without_dictionary_entry`, `test_write_details_json_one_record_per_stand`) to pass an extra `{}` (empty `tie_break_index`) as the final argument.

In `pipeline/prepare_trip.py`, update the `write_details_json(...)` call to pass the already-loaded `tie_break_raw_index` (from Task 7):

```python
    details_path = write_details_json(
        enriched, package_details_index, neighbors_by_stand, dictionaries,
        day=day, out_path=out_dir / f"details_{day}.json",
        tie_break_index=tie_break_raw_index,
    )
```

In `tests/test_prepare_trip.py`, update `test_b3_detail_card_step_does_not_change_r_or_h`'s `write_details_json(...)` call to also pass `tie_break_index=tie_break_raw_index` (compute it the same way `test_tie_break_step_does_not_change_r_or_h` does, right before this call, reusing `empty_packages_dir`), and update `test_tie_break_step_does_not_change_r_or_h` (Task 7) if it also calls `write_details_json` -- it currently doesn't, no change needed there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export.py tests/test_prepare_trip.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/export.py pipeline/prepare_trip.py tests/test_export.py tests/test_prepare_trip.py
git commit -m "feat: export tie_break to scores.json and veg_cover/standdensity_index to details.json (plan 2.1 Zmiana 4, step 4/4)"
```

---

## Task 10: Frontend — tie_break sort key + card fields

**Files:**
- Modify: `frontend/src/model.ts` (`Score.tie_break`, `StandDetail.veg_cover`/`standdensity_index`, `joinData` sort, `parseData` validation)
- Modify: `frontend/src/main.ts` (`packageSection` rendering)
- Test: `frontend/src/model.test.ts`

**Interfaces:**
- Consumes: `Score.tie_break?: number | null`, `StandDetail.veg_cover: string | null`, `StandDetail.standdensity_index: number | null`.
- Produces: `joinData`'s sort order now uses (R rounded to 2 decimals, tie_break, stand_id) instead of (R, stand_id) — this also fixes region-member display order, since `visibleEntries()` in `main.ts` filters the same globally-sorted `entries` array rather than re-deriving order from `region.stand_ids` (confirmed while reading `main.ts`).

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/model.test.ts`, inside (or right after) the existing `describe("data and classification", ...)` block, reusing that file's own `score(id, r, mask)` helper and top-level `stands` fixture (ids `"A"`/`"B"` -- sufficient here, no need for a third stand):

```ts
describe("joinData tie_break secondary sort", () => {
  it("prefers the higher tie_break when R rounds to the same value at 2 decimals", () => {
    const entries = joinData(
      [
        { ...score("A", 50.001), tie_break: 0.2 },
        { ...score("B", 50.004), tie_break: 0.9 }, // rounds to the same 50.00 as A
      ],
      stands,
    );
    expect(entries.map((e) => e.score.stand_id)).toEqual(["B", "A"]);
  });

  it("falls back to stand_id when tie_break is absent on both sides (older export)", () => {
    const entries = joinData([score("B", 50.0), score("A", 50.0)], stands);
    expect(entries.map((e) => e.score.stand_id)).toEqual(["A", "B"]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- -t "tie_break"`
Expected: FAIL (TypeScript error on the unknown `tie_break` property, or wrong order since `joinData` doesn't read it yet)

- [ ] **Step 3: Implement**

In `frontend/src/model.ts`, add to the `Score` type (after the `G_season?` field from Task 4):

```ts
  // Plan 2.1 "Zmiana 4": ground-cover/density ordinal secondary sort key
  // (pipeline.tie_break), same optional-field pattern as area_ha/G_season.
  tie_break?: number | null;
```

Change `joinData`'s sort (line 216) from:

```ts
    .sort((a, b) => b.R! - a.R! || a.stand_id.localeCompare(b.stand_id))
```

to:

```ts
    .sort((a, b) => {
      // Plan 2.1 "Zmiana 4": R rounded to 2 decimal places is the primary
      // key (same precision pipeline.regions._summarize_cluster uses for
      // region member ordering, chosen against a real Będziemyśl export --
      // see that function's own docstring), tie_break the secondary key
      // among stands tied at that precision, stand_id the final
      // deterministic tiebreaker.
      const ra = Math.round(a.R! * 100);
      const rb = Math.round(b.R! * 100);
      if (rb !== ra) return rb - ra;
      const ta = a.tie_break ?? -1;
      const tb = b.tie_break ?? -1;
      if (tb !== ta) return tb - ta;
      return a.stand_id.localeCompare(b.stand_id);
    })
```

In `parseData`'s scores-array validation predicate, add `(s.tie_break === undefined || numeric(s.tie_break)) &&` next to the `G_season` check added in Task 4.

Add to the `StandDetail` type (after `prot_categ: string | null;`):

```ts
  // Plan 2.1 "Zmiana 4": word-form ground cover + numeric stand density
  // index, next to the existing `density` (zwarcie) field -- null when
  // adr_for isn't covered by any package, same as the other package-only
  // fields above.
  veg_cover: string | null;
  standdensity_index: number | null;
```

In `parseData`'s details-array validation predicate, add `nullableString(d.veg_cover) &&` and `(d.standdensity_index === null || finite(d.standdensity_index)) &&` next to the existing `nullableString(d.prot_categ)` line.

In `frontend/src/main.ts`, change `packageSection` (line 181) from:

```ts
  return `<div class="package-detail"><p><strong>Skład gatunkowy (warstwa drzew)</strong></p>${speciesList(detail.drzew_species)}<p><strong>Zwarcie</strong> ${escape(densityLabel(detail.density))}</p><p><strong>Podszyt</strong></p>${speciesList(detail.podszyt_species)}<p><strong>Typ gleby</strong> ${detail.soil_type ? escape(detail.soil_type) : "brak danych"}</p>${detail.package_date ? `<p class="muted">Dane paczki BDL z dnia ${escape(detail.package_date)}.</p>` : ""}</div>`;
```

to:

```ts
  return `<div class="package-detail"><p><strong>Skład gatunkowy (warstwa drzew)</strong></p>${speciesList(detail.drzew_species)}<p><strong>Zwarcie</strong> ${escape(densityLabel(detail.density))}</p><p><strong>Pokrycie gleby</strong> ${detail.veg_cover ? escape(detail.veg_cover) : "brak danych"}</p><p><strong>Zadrzewienie</strong> ${finite(detail.standdensity_index) ? `${detail.standdensity_index!.toFixed(1)} (skala ok. 0–2, 1,0 = pełne)` : "brak danych"}</p><p><strong>Podszyt</strong></p>${speciesList(detail.podszyt_species)}<p><strong>Typ gleby</strong> ${detail.soil_type ? escape(detail.soil_type) : "brak danych"}</p>${detail.package_date ? `<p class="muted">Dane paczki BDL z dnia ${escape(detail.package_date)}.</p>` : ""}</div>`;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test`
Expected: PASS (all existing + 2 new tests)

- [ ] **Step 5: Type-check and build**

Run: `cd frontend && npx tsc --noEmit && npx vite build`
Expected: both succeed with no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/model.ts frontend/src/main.ts frontend/src/model.test.ts
git commit -m "feat: frontend tie_break sort key + ground-cover/density card fields (plan 2.1 Zmiana 4, frontend)"
```

---

## Task 11: Full verification, real-data before/after, docs handoff

**Files:**
- Modify: `docs/CODEX-HANDOFF.md` (new note at the top, per this repo's `CLAUDE.md` instruction)

- [ ] **Step 1: Full Python test suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: PASS, every test (report the final count, e.g. "N passed").

- [ ] **Step 2: Full frontend suite**

Run:
```bash
cd frontend
npm test
npx tsc --noEmit
npx vite build
```
Expected: all three succeed.

- [ ] **Step 3: Real Będziemyśl rerun — top-20 and region member order, before/after**

Reuse the exact network-free rerun script from Task 5 Step 5 (same cache, same target_date=2026-09-25), but this time run it against `profiles/boletus_edulis.yaml` as committed after every task above (G_season wired, moisture_midpoint=0.50, tie_break wired through `enrich_with_mvp_layers` + `group_into_regions`), and also run the "before" side (git-stash or a checked-out copy of the profile/code as it stood before this plan started, e.g. `git show <base-commit>:profiles/boletus_edulis.yaml` plus the pre-plan `pipeline/orchestrate.py`/`pipeline/regions.py`) — comparing:

1. Top-20 `stand_id` + `R` before vs. after (order and membership can both shift: G_season/moisture recalibration change F/F_loc/R values themselves).
2. For each of the (up to) 5 accepted regions, print `region["stand_ids"]` before vs. after and highlight any reordering attributable to tie_break (same R at 2 decimals, different tie_break).
3. F/F_loc class distribution (`Counter`) before vs. after, same as Task 5 Step 5.

Report all three in the completion summary — this is the "Pokaż mi, jak zmienia się top-20 i kolejność członków 5 rejonów" the user asked for.

- [ ] **Step 4: Update docs/CODEX-HANDOFF.md**

Add a new note at the very top of `docs/CODEX-HANDOFF.md` (above the current "## 2026-09-25 — aktualne (21)" entry), following the file's existing note format (see the existing entries for the exact style: `## YYYY-MM-DD — aktualne (N): title`, then "Co zrobione:", real numbers, "Nie ruszono:"). Include:
- What changed (G_season module + wiring, moisture_midpoint 0.35→0.50, tie_break module + wiring into regions/export/frontend).
- The before/after numbers from Task 5 Step 5 and this task's Step 3.
- Test counts (Python: old count → new count; frontend: old → new).
- Explicitly note: H and R_final's own FORMULA are unchanged; tie_break is structurally excluded from `pipeline.orchestrate`/`habitat`/`scoring`/`mvp` imports (name the exact modules, matching the B2/B3 note style).
- "Nie ruszono": anything explicitly out of scope (e.g. `fruiting_classes`, unless Task 5 Step 5 surfaced a real need and the user explicitly approved a change — in which case note that change here instead).

- [ ] **Step 5: Commit**

```bash
git add docs/CODEX-HANDOFF.md
git commit -m "docs: record G_season + moisture calibration + tie_break implementation in CODEX-HANDOFF"
```
