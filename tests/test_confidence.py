import pytest

from pipeline.habitat import load_profile
from pipeline.confidence import score_data_quality, classify_data_quality, compute_confidence

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_score_data_quality_known_species():
    row = {"species_cd": "SO"}
    cfg = PROFILE["confidence"]["data_quality_factors"]
    expected = cfg["kompletnosc_gatunek_panujacy"] * cfg["swiezosc_bez_s2"] * cfg["pogoda_nwp_2km"]
    assert score_data_quality(row, PROFILE) == pytest.approx(expected)


def test_score_data_quality_unknown_species_is_lower():
    row_known = {"species_cd": "SO"}
    row_unknown = {"species_cd": "ZZZ"}
    assert score_data_quality(row_unknown, PROFILE) < score_data_quality(row_known, PROFILE)


def test_classify_data_quality_boundaries():
    assert classify_data_quality(0.39, PROFILE) == "NISKA"
    assert classify_data_quality(0.40, PROFILE) == "SREDNIA"
    assert classify_data_quality(0.69, PROFILE) == "SREDNIA"
    assert classify_data_quality(0.70, PROFILE) == "WYSOKA"


def test_compute_confidence_caps_at_model_confidence():
    # data quality for a known species (0.7*1.0*0.8=0.56) classifies SREDNIA,
    # and model_confidence_cap is also SREDNIA -- final must be SREDNIA, not
    # upgraded past the model cap even if data quality were higher.
    row = {"species_cd": "SO"}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "SREDNIA"
    assert PROFILE["confidence"]["reasons"]["model_uncalibrated"] in reasons


def test_compute_confidence_includes_species_unknown_reason():
    row = {"species_cd": "ZZZ"}
    _final, reasons = compute_confidence(row, PROFILE)
    assert PROFILE["confidence"]["reasons"]["species_unknown"] in reasons


def test_compute_confidence_never_exceeds_niska_when_data_quality_is_niska(monkeypatch):
    low_profile = {**PROFILE, "confidence": {
        **PROFILE["confidence"],
        "data_quality_factors": {**PROFILE["confidence"]["data_quality_factors"], "pogoda_nwp_2km": 0.1},
    }}
    final, _reasons = compute_confidence({"species_cd": "SO"}, low_profile)
    assert final == "NISKA"
