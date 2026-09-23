import math
import pytest

from pipeline.habitat import load_profile
from pipeline.explain import compute_log_contributions, generate_explanation, FACTOR_WEIGHTS

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_compute_log_contributions_positive_above_median():
    values = {"host": 1.0, "site": 1.0, "age": 1.0, "moisture": 0.5, "temperature": 1.0, "frost": 1.0, "pressure_factor": 1.0}
    medians = {"host": 0.5, "site": 0.5, "age": 0.5, "moisture": 0.5, "temperature": 0.5, "frost": 1.0, "pressure_factor": 1.0}
    contributions = compute_log_contributions(values, medians)
    assert contributions["host"] == pytest.approx(FACTOR_WEIGHTS["host"] * math.log(1.0 / 0.5))
    # value == median -> log ratio is 0, but the factor is still included (not skipped)
    assert "frost" in contributions
    assert contributions["frost"] == pytest.approx(0.0)


def test_compute_log_contributions_skips_non_positive_inputs():
    values = {"host": 0.0, "site": 1.0}
    medians = {"host": 0.5, "site": 0.5}
    contributions = compute_log_contributions(values, medians)
    assert "host" not in contributions
    assert "site" in contributions


def test_compute_log_contributions_skips_missing_median():
    values = {"host": 1.0}
    medians = {}
    contributions = compute_log_contributions(values, medians)
    assert contributions == {}


def test_generate_explanation_picks_top_positives_and_negatives():
    contributions = {"host": 0.5, "site": 0.3, "age": 0.1, "moisture": -0.4, "temperature": -0.2, "frost": 0.0}
    values = {"host": 1.0, "site": 0.9, "age": 0.8, "moisture": 0.2, "temperature": 0.3, "frost": 1.0, "pressure_factor": 1.0}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.1}
    entries = generate_explanation(contributions, values, meta, PROFILE)

    factors = [e["factor"] for e in entries]
    assert factors[:2] == ["host", "site"]  # top 2 positive, descending
    assert "moisture" in factors[-2:]  # most negative included
    for entry in entries:
        assert entry["text"]
        assert isinstance(entry["contribution"], float)


def test_generate_explanation_respects_profile_max_counts():
    contributions = {"host": 0.9, "site": 0.5, "age": 0.4, "moisture": -0.9, "temperature": -0.5, "frost": -0.4}
    values = {"host": 1.0, "site": 1.0, "age": 1.0, "moisture": 0.1, "temperature": 0.1, "frost": 0.1, "pressure_factor": 1.0}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.1}
    entries = generate_explanation(contributions, values, meta, PROFILE)
    assert sum(1 for e in entries if e["contribution"] > 0) <= PROFILE["explanation"]["max_positive"]
    assert sum(1 for e in entries if e["contribution"] < 0) <= PROFILE["explanation"]["max_negative"]


def test_generate_explanation_handles_no_negative_contributions():
    contributions = {"host": 0.5, "site": 0.1}
    values = {"host": 1.0, "site": 1.0, "pressure_factor": 1.0}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.0}
    entries = generate_explanation(contributions, values, meta, PROFILE)
    assert all(e["contribution"] > 0 for e in entries)
