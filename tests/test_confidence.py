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


def test_score_data_quality_full_composition_beats_known_dominant_species():
    # Plan 2.1 step B2: a BDL-package-derived S_host (full DRZEW
    # composition) is a strictly better data source than "just the
    # dominant species" -- kompletnosc_pelny_sklad must exceed
    # kompletnosc_gatunek_panujacy regardless of species_cd.
    row = {"species_cd": "SO", "s_host_source": "paczka"}
    cfg = PROFILE["confidence"]["data_quality_factors"]
    expected = cfg["kompletnosc_pelny_sklad"] * cfg["swiezosc_bez_s2"] * cfg["pogoda_nwp_2km"]
    assert score_data_quality(row, PROFILE) == pytest.approx(expected)
    assert score_data_quality(row, PROFILE) > score_data_quality({"species_cd": "SO"}, PROFILE)


def test_compute_confidence_drops_dominant_only_reason_when_s_host_from_package():
    # "tylko gatunek panujacy" must disappear for a package-covered stand
    # (task requirement) -- replaced by species_full_composition.
    row = {"species_cd": "SO", "s_host_source": "paczka"}
    _final, reasons = compute_confidence(row, PROFILE)
    assert PROFILE["confidence"]["reasons"]["species_full_composition"] in reasons
    assert PROFILE["confidence"]["reasons"]["species_dominant_only"] not in reasons
    assert PROFILE["confidence"]["reasons"]["species_unknown"] not in reasons


def test_compute_confidence_package_source_still_capped_at_model_confidence():
    # Higher underlying data quality (1.0 vs 0.7) doesn't lift the
    # displayed class past model_confidence_cap (spec §10: capped through
    # phase 1-4 regardless of input quality) -- only the reason text
    # changes.
    row = {"species_cd": "SO", "s_host_source": "paczka"}
    final, _reasons = compute_confidence(row, PROFILE)
    assert final == "SREDNIA"


def test_compute_confidence_wfs_source_unaffected_by_new_path():
    # Absent/"wfs" s_host_source must reproduce the exact pre-B2 behaviour.
    row = {"species_cd": "SO"}
    row_explicit_wfs = {"species_cd": "SO", "s_host_source": "wfs"}
    assert compute_confidence(row, PROFILE) == compute_confidence(row_explicit_wfs, PROFILE)


def test_compute_confidence_never_exceeds_niska_when_data_quality_is_niska(monkeypatch):
    low_profile = {**PROFILE, "confidence": {
        **PROFILE["confidence"],
        "data_quality_factors": {**PROFILE["confidence"]["data_quality_factors"], "pogoda_nwp_2km": 0.1},
    }}
    final, _reasons = compute_confidence({"species_cd": "SO"}, low_profile)
    assert final == "NISKA"


def test_score_data_quality_uses_radar_factor_when_coverage_high():
    base = {"species_cd": "SO", "s_host_source": "wfs"}
    nwp = score_data_quality({**base, "rain_radar_coverage": 0.0}, PROFILE)
    radar = score_data_quality({**base, "rain_radar_coverage": 0.9}, PROFILE)
    f = PROFILE["confidence"]["data_quality_factors"]
    assert radar / nwp == pytest.approx(f["pogoda_radar_1km"] / f["pogoda_nwp_2km"])


# --- Plan wdrozenia 1.7: real-gap reasons force NISKA -----------------------

def test_compute_confidence_niska_when_climatology_insufficient():
    row = {"species_cd": "SO", "insufficient_climatology": True}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["empty_or_thin_climatology"] in reasons


def test_compute_confidence_niska_when_radar_coverage_low_and_radar_enabled():
    assert PROFILE["radar"]["enabled"] is True
    row = {"species_cd": "SO", "rain_radar_coverage": 0.3}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["radar_low_coverage"] in reasons


def test_compute_confidence_not_niska_for_low_radar_coverage_when_radar_disabled():
    no_radar_profile = {**PROFILE, "radar": {**PROFILE["radar"], "enabled": False}}
    row = {"species_cd": "SO", "rain_radar_coverage": 0.1}
    final, reasons = compute_confidence(row, no_radar_profile)
    assert final == "SREDNIA"
    assert no_radar_profile["confidence"]["reasons"]["radar_low_coverage"] not in reasons


def test_compute_confidence_niska_when_osm_tile_skipped():
    row = {"species_cd": "SO", "osm_tile_skipped": True}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["osm_tile_skipped"] in reasons


def test_compute_confidence_niska_when_gdos_tile_skipped():
    row = {"species_cd": "SO", "gdos_status": "kafel_pominiety"}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["gdos_tile_skipped"] in reasons


def test_compute_confidence_not_niska_for_gdos_status_brak_or_blokada():
    for status in ("brak", "blokada"):
        final, reasons = compute_confidence({"species_cd": "SO", "gdos_status": status}, PROFILE)
        assert final == "SREDNIA"
        assert PROFILE["confidence"]["reasons"]["gdos_tile_skipped"] not in reasons


def test_compute_confidence_niska_when_site_type_unknown():
    row = {"species_cd": "SO", "site_type": "NIEZNANY_KOD"}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["unknown_site_type"] in reasons


def test_compute_confidence_not_niska_for_known_site_type():
    row = {"species_cd": "SO", "site_type": "BMSW"}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "SREDNIA"
    assert PROFILE["confidence"]["reasons"]["unknown_site_type"] not in reasons


def test_compute_confidence_niska_when_species_unknown_now_a_real_gap():
    # Plan 1.7 promotes "gatunek panujacy nierozpoznany" from a DQ-score
    # input (already capped at SREDNIA either way) to an explicit real-gap
    # trigger -- unlike pre-1.7, this now forces NISKA, not just SREDNIA.
    row = {"species_cd": "ZZZ"}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["species_unknown"] in reasons


def test_compute_confidence_niska_when_package_composition_incomplete():
    row = {"species_cd": "SO", "s_host_source": "paczka", "sklad_niepelny": True}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "NISKA"
    assert PROFILE["confidence"]["reasons"]["incomplete_composition"] in reasons


def test_compute_confidence_not_niska_for_complete_package_composition():
    row = {"species_cd": "SO", "s_host_source": "paczka", "sklad_niepelny": False}
    final, reasons = compute_confidence(row, PROFILE)
    assert final == "SREDNIA"
    assert PROFILE["confidence"]["reasons"]["incomplete_composition"] not in reasons


def test_compute_confidence_no_false_positive_gaps_on_a_clean_row():
    # A row with none of the plan-1.7 columns set at all (the pre-1.7
    # fixture shape used throughout the rest of this file) must not be
    # spuriously forced to NISKA -- absence of a column means "not
    # applicable here", not "this gap occurred".
    final, reasons = compute_confidence({"species_cd": "SO"}, PROFILE)
    assert final == "SREDNIA"
    for key in ("empty_or_thin_climatology", "radar_low_coverage", "osm_tile_skipped",
                "gdos_tile_skipped", "unknown_site_type", "incomplete_composition"):
        assert PROFILE["confidence"]["reasons"][key] not in reasons


def test_compute_confidence_reason_names_radar_only_above_threshold():
    reasons_cfg = PROFILE["confidence"]["reasons"]
    _, low = compute_confidence({"species_cd": "SO", "rain_radar_coverage": 0.5}, PROFILE)
    _, high = compute_confidence({"species_cd": "SO", "rain_radar_coverage": 0.8}, PROFILE)
    _, missing = compute_confidence({"species_cd": "SO"}, PROFILE)
    assert reasons_cfg["weather_nwp"] in low and reasons_cfg["weather_radar"] not in low
    assert reasons_cfg["weather_radar"] in high and reasons_cfg["weather_nwp"] not in high
    assert reasons_cfg["weather_nwp"] in missing
