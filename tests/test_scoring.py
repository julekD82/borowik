import math
import pytest

from pipeline.habitat import load_profile
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting,
    apply_moisture_modulation, classify_fruiting,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_score_moisture_at_midpoint_is_half():
    assert score_moisture(0.35, 0.35, PROFILE) == pytest.approx(0.5)


def test_score_moisture_above_midpoint_is_higher():
    assert score_moisture(0.6, 0.6, PROFILE) == pytest.approx(1 / (1 + math.exp(-2.5)))


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
