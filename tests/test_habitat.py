import math
import pytest

from pipeline.habitat import (
    load_profile, host_affinity, score_host, score_host_composition,
    score_site, score_age, compute_habitat, passes_mask,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def test_host_affinity_looks_up_known_species():
    assert host_affinity("BK", PROFILE) == pytest.approx(0.9)


def test_host_affinity_falls_back_to_unknown_default():
    assert host_affinity("ZZZ", PROFILE) == pytest.approx(PROFILE["unknown_host_affinity"])


def test_score_host_pure_stand_matches_affinity():
    assert score_host("SO", 10, PROFILE) == pytest.approx(1.0)


def test_score_host_mixes_with_unknown_admixture_default():
    # DB affinity 0.8, share=0.5 -> 0.5*0.8 + 0.5*0.5
    assert score_host("DB", 5, PROFILE) == pytest.approx(0.5 * 0.8 + 0.5 * 0.5)


def test_score_host_treats_nan_part_cd_as_zero_share():
    # part_cd comes from pd.to_numeric(errors="coerce"), so a missing value is
    # NaN. NaN is truthy, so `part_cd or 0` used to let it through and the NaN
    # propagated through H into R.
    value = score_host("SO", float("nan"), PROFILE)
    assert not math.isnan(value)
    assert value == pytest.approx(PROFILE["unknown_host_affinity"])
    assert score_host("SO", None, PROFILE) == pytest.approx(PROFILE["unknown_host_affinity"])


def test_compute_habitat_finite_with_nan_part_cd():
    row = {"species_cd": "SO", "part_cd": float("nan"), "site_type": "BMSW", "spec_age": 60}
    h = compute_habitat(row, PROFILE)
    assert h is not None and not math.isnan(h)


def test_score_site_known_codes():
    assert score_site("BMSW", PROFILE) == (pytest.approx(1.00), 1)
    assert score_site("BS", PROFILE) == (pytest.approx(0.45), 0)


def test_score_site_unknown_code_falls_back():
    assert score_site("XYZ", PROFILE) == (pytest.approx(0.5), 1)


def test_score_age_masks_young_stands():
    assert score_age(5, PROFILE) is None


def test_score_age_interpolates_first_segment():
    # 12-20: 0.3 -> 0.6
    assert score_age(15, PROFILE) == pytest.approx(0.3 + (15 - 12) / (20 - 12) * (0.6 - 0.3))


def test_score_age_plateau_and_old_growth():
    assert score_age(60, PROFILE) == pytest.approx(1.0)
    assert score_age(150, PROFILE) == pytest.approx(0.9)


def test_compute_habitat_combines_weighted_geometric_mean():
    row = {"species_cd": "SO", "part_cd": 10, "site_type": "BMSW", "spec_age": 60}
    assert compute_habitat(row, PROFILE) == pytest.approx(1.0)

    row2 = {"species_cd": "DB", "part_cd": 10, "site_type": "LSW", "spec_age": 27}
    s_host = score_host("DB", 10, PROFILE)
    s_site, _ = score_site("LSW", PROFILE)
    s_age = score_age(27, PROFILE)
    expected = s_host ** 0.40 * s_site ** 0.35 * s_age ** 0.25
    assert compute_habitat(row2, PROFILE) == pytest.approx(expected)


def test_score_host_composition_weighted_sum_of_real_shares():
    # SO 0.7*1.0 + BK 0.3*0.9 -- plan 2.1 step B2, real package composition
    # replacing the panujacy+0.5 blend.
    s_host, unknown = score_host_composition([("SO", 0.7), ("BK", 0.3)], PROFILE)
    assert s_host == pytest.approx(0.7 * 1.0 + 0.3 * 0.9)
    assert unknown == 0


def test_score_host_composition_pure_stand_equals_one():
    s_host, unknown = score_host_composition([("SO", 1.0)], PROFILE)
    assert s_host == pytest.approx(1.0)
    assert unknown == 0


def test_score_host_composition_unknown_species_falls_back_and_counts():
    # Unknown species_cd gets unknown_host_affinity (same fallback as an
    # unquantified WFS admixture), and is counted rather than silently
    # dropped (B2: diagnostic, not an error).
    s_host, unknown = score_host_composition([("SO", 0.6), ("ZZZ", 0.4)], PROFILE)
    assert s_host == pytest.approx(0.6 * 1.0 + 0.4 * PROFILE["unknown_host_affinity"])
    assert unknown == 1


def test_score_host_composition_empty_list():
    s_host, unknown = score_host_composition([], PROFILE)
    assert s_host == 0.0
    assert unknown == 0


def test_compute_habitat_uses_s_host_override_when_given():
    row = {"species_cd": "SO", "part_cd": 10, "site_type": "BMSW", "spec_age": 60}
    default = compute_habitat(row, PROFILE)
    overridden = compute_habitat(row, PROFILE, s_host=0.5)
    assert overridden != default
    s_site, _ = score_site("BMSW", PROFILE)
    s_age = score_age(60, PROFILE)
    w = PROFILE["weights"]
    expected = 0.5 ** w["host"] * s_site ** w["site"] * s_age ** w["age"]
    assert overridden == pytest.approx(expected)


def test_compute_habitat_none_override_matches_default_behaviour():
    row = {"species_cd": "DB", "part_cd": 5, "site_type": "LSW", "spec_age": 27}
    assert compute_habitat(row, PROFILE, s_host=None) == compute_habitat(row, PROFILE)


def test_compute_habitat_none_when_masked_by_age():
    row = {"species_cd": "SO", "part_cd": 10, "site_type": "BMSW", "spec_age": 5}
    assert compute_habitat(row, PROFILE) is None


def test_passes_mask_rejects_zero_affinity_dominant_species():
    row = {"area_type": "D-STAN", "spec_age": 60, "species_cd": "OL", "part_cd": 9}
    assert passes_mask(row, PROFILE) is False


def test_passes_mask_accepts_normal_stand():
    row = {"area_type": "D-STAN", "spec_age": 60, "species_cd": "SO", "part_cd": 10}
    assert passes_mask(row, PROFILE) is True


def test_passes_mask_rejects_non_stand_area_type():
    row = {"area_type": "ZRAB", "spec_age": 60, "species_cd": "SO", "part_cd": 10}
    assert passes_mask(row, PROFILE) is False
