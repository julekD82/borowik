import math
import pytest

from pipeline.age_update import update_age


def test_disabled_returns_original_age_unchanged():
    age, status = update_age(spec_age=10, a_year=2020, analysis_year=2026, enabled=False)
    assert age == 10
    assert status == "wylaczona"


def test_enabled_shifts_age_by_years_since_description():
    age, status = update_age(spec_age=10, a_year=2020, analysis_year=2026, enabled=True)
    assert age == 16
    assert status == "skorygowano"


def test_enabled_same_year_no_shift():
    age, status = update_age(spec_age=60, a_year=2026, analysis_year=2026, enabled=True)
    assert age == 60
    assert status == "skorygowano"


def test_missing_a_year_keeps_original_age_and_flags():
    age, status = update_age(spec_age=10, a_year=None, analysis_year=2026, enabled=True)
    assert age == 10
    assert status == "brak_roku_stanu"


def test_nan_a_year_keeps_original_age_and_flags():
    age, status = update_age(spec_age=10, a_year=float("nan"), analysis_year=2026, enabled=True)
    assert age == 10
    assert status == "brak_roku_stanu"


def test_missing_spec_age_with_known_year_is_not_flagged_as_missing_year():
    # a_year is known here -- the flag is specifically about rok stanu being
    # unavailable, not about spec_age itself (score_age/passes_mask already
    # handle a bare None age on their own).
    age, status = update_age(spec_age=None, a_year=2020, analysis_year=2026, enabled=True)
    assert age is None
    assert status == "skorygowano"


def test_corrected_age_can_cross_mask_threshold():
    # spec_age below the mask_below=12 breakpoint, but old enough now that
    # analysis_year has moved on from the description year.
    age, status = update_age(spec_age=9, a_year=2020, analysis_year=2026, enabled=True)
    assert age == 15
    assert status == "skorygowano"
