import math
import pytest

from pipeline.habitat import load_profile
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting,
    apply_moisture_modulation, classify_fruiting, moisture_percentile,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_score_moisture_at_midpoint_is_half():
    # Plan 2.1 "Zmiana 2": profiles/boletus_edulis.yaml's real
    # moisture_midpoint changed 0.35 -> 0.50 -- this test always asserts
    # the logistic is 0.5 AT whatever the profile's own midpoint is, so it
    # reads that value from PROFILE rather than hard-coding it again.
    midpoint = PROFILE["fruiting"]["moisture_midpoint"]
    assert score_moisture(midpoint, midpoint, PROFILE) == pytest.approx(0.5)


def test_score_moisture_above_midpoint_is_higher():
    # 0.6 is 0.10 (one moisture_slope) above the new 0.50 midpoint ->
    # exponent 1.0, same derivation as before, updated for the new midpoint.
    assert score_moisture(0.6, 0.6, PROFILE) == pytest.approx(1 / (1 + math.exp(-1.0)))


def _with_sm_weight(weight):
    profile = {**PROFILE, "fruiting": {**PROFILE["fruiting"], "soil_moisture_weight": weight}}
    return profile


def test_moisture_percentile_ignores_soil_moisture_at_zero_weight():
    assert moisture_percentile(0.7, 0.0, _with_sm_weight(0.0)) == pytest.approx(0.7)


def test_moisture_percentile_blends_by_soil_moisture_weight():
    assert moisture_percentile(0.8, 0.4, _with_sm_weight(0.25)) == pytest.approx(0.7)


def test_profile_drops_model_soil_moisture_from_m():
    # 2026-09-27 user decision: Open-Meteo's forecast soil moisture was being
    # ranked against an ERA5-Land climatology from a different model (live
    # ~0.14 vs climatology median ~0.23 m3/m3), so pct_sm sat at 0.00-0.04
    # almost everywhere and jumped to ~0.48 in ~10 km model soil blocks --
    # M ended up driven by those blocks, not by rain. Until A2 brings its own
    # water balance, M comes from the (radar) rain balance only.
    assert PROFILE["fruiting"]["soil_moisture_weight"] == 0.0


def test_score_moisture_uses_weighted_percentile():
    expected = 1 / (1 + math.exp(-(0.7 - PROFILE["fruiting"]["moisture_midpoint"]) / PROFILE["fruiting"]["moisture_slope"]))
    assert score_moisture(0.7, 0.0, PROFILE) == pytest.approx(expected)


def test_score_temperature_at_optimum_no_penalty():
    assert score_temperature(tmean20=13.0, tmean5=13.0, p5=10.0, profile=PROFILE) == pytest.approx(1.0)


def test_score_temperature_heat_penalty_applies():
    base = math.exp(-(20.0 - 13.0) ** 2 / 32)
    assert score_temperature(tmean20=20.0, tmean5=20.0, p5=2.0, profile=PROFILE) == pytest.approx(base * 0.3)


def test_score_temperature_no_heat_penalty_when_wet():
    base = math.exp(-(20.0 - 13.0) ** 2 / 32)
    assert score_temperature(tmean20=20.0, tmean5=20.0, p5=10.0, profile=PROFILE) == pytest.approx(base)


def test_score_frost_thresholds():
    assert score_frost(-3.0, PROFILE) == pytest.approx(0.2)
    assert score_frost(-1.0, PROFILE) == pytest.approx(0.6)
    assert score_frost(2.0, PROFILE) == pytest.approx(1.0)


def test_compute_fruiting_combines_m_t_k():
    f = compute_fruiting(m=0.5, t=1.0, k_frost=1.0, g_season=1.0)
    assert f == pytest.approx(0.5 ** 0.6)


def test_apply_moisture_modulation_dry_branch():
    # moisture_cls=1 (swieze), dry multiplier table index 1 -> 0.9
    result = apply_moisture_modulation(f=0.5, moisture_cls=1, pct_m=0.2, profile=PROFILE)
    assert result == pytest.approx(0.5 * 0.9)


def test_apply_moisture_modulation_wet_branch():
    # moisture_cls=2 (wilgotne), wet multiplier table index 2 -> 0.85
    result = apply_moisture_modulation(f=0.5, moisture_cls=2, pct_m=0.9, profile=PROFILE)
    assert result == pytest.approx(0.5 * 0.85)


def test_apply_moisture_modulation_clips_to_one():
    result = apply_moisture_modulation(f=0.9, moisture_cls=0, pct_m=0.9, profile=PROFILE)
    assert result == pytest.approx(1.0)


def test_apply_moisture_modulation_neutral_branch_unchanged():
    result = apply_moisture_modulation(f=0.5, moisture_cls=1, pct_m=0.5, profile=PROFILE)
    assert result == pytest.approx(0.5)


@pytest.mark.parametrize("f,expected", [
    (0.1, "Słabe warunki"),
    (0.2, "Umiarkowane"),
    (0.44, "Umiarkowane"),
    (0.45, "Dobre"),
    (0.69, "Dobre"),
    (0.70, "Bardzo dobre"),
])
def test_classify_fruiting_boundaries(f, expected):
    assert classify_fruiting(f, PROFILE) == expected


@pytest.mark.parametrize("f,expected", [
    (0.1, 0), (0.2, 1), (0.44, 1), (0.45, 2), (0.69, 2), (0.70, 3),
])
def test_classify_fruiting_level_matches_classify_fruiting_label(f, expected):
    from pipeline.scoring import classify_fruiting_level
    assert classify_fruiting_level(f, PROFILE) == expected
    classes = PROFILE["fruiting_classes"]
    assert classes[classify_fruiting_level(f, PROFILE)]["label"] == classify_fruiting(f, PROFILE)


from pipeline.scoring import compute_ranking


def test_compute_ranking_multiplies_when_passing_mask():
    assert compute_ranking(mask=True, h=0.8, f_loc=0.5) == pytest.approx(100 * 0.8 * 0.5)


def test_compute_ranking_zero_when_masked():
    assert compute_ranking(mask=False, h=0.9, f_loc=0.9) == pytest.approx(0.0)


def test_compute_ranking_zero_when_habitat_none():
    assert compute_ranking(mask=True, h=None, f_loc=0.9) == pytest.approx(0.0)


def test_compute_ranking_zero_when_fruiting_none():
    assert compute_ranking(mask=True, h=0.8, f_loc=None) == pytest.approx(0.0)


def test_compute_ranking_default_p_reproduces_faza1_behavior():
    # alpha's default (0.3) must not matter when p defaults to 0.0 -- this is
    # the regression guard that Faza 2's pressure term never changes Faza 1's R.
    assert compute_ranking(mask=True, h=0.8, f_loc=0.5) == pytest.approx(100 * 0.8 * 0.5)


def test_compute_ranking_applies_pressure_discount():
    r = compute_ranking(mask=True, h=0.8, f_loc=0.5, p=0.5, alpha=0.3)
    assert r == pytest.approx(100 * 0.8 * 0.5 * (1 - 0.3 * 0.5))


def test_compute_ranking_zero_pressure_matches_no_pressure_call():
    assert compute_ranking(mask=True, h=0.8, f_loc=0.5, p=0.0, alpha=0.3) == pytest.approx(
        compute_ranking(mask=True, h=0.8, f_loc=0.5)
    )


def test_compute_ranking_full_pressure_zeroes_ranking():
    # alpha at its spec §4.1 max (0.6) with p=1.0 is the strongest discount the
    # slider allows; confirm the formula behaves at that boundary too.
    r = compute_ranking(mask=True, h=0.8, f_loc=0.5, p=1.0, alpha=0.6)
    assert r == pytest.approx(100 * 0.8 * 0.5 * 0.4)
