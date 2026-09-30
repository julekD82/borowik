import math
import pytest

from pipeline.habitat import (
    load_profile, host_affinity, score_host, score_host_composition,
    score_site, score_age, compute_habitat, passes_mask, blend_host_with_lower_storeys,
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


def _curve_profile():
    import copy
    p = copy.deepcopy(PROFILE)
    p["habitat"] = {"age_mode": "curve"}
    return p


def test_score_age_interpolates_first_segment():
    # tryb curve (dawna krzywa, nadal dostepna): 12-20: 0.3 -> 0.6
    assert score_age(15, _curve_profile()) == pytest.approx(0.3 + (15 - 12) / (20 - 12) * (0.6 - 0.3))


def test_score_age_plateau_and_old_growth():
    assert score_age(60, _curve_profile()) == pytest.approx(1.0)
    assert score_age(150, _curve_profile()) == pytest.approx(0.9)


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


# --- Plan 1.6.3: S_host blended with lower-storey composition -----------

def test_blend_host_with_lower_storeys_zero_weight_is_a_no_op():
    s_host, unknown = blend_host_with_lower_storeys(0.8, [("BRZ", 1.0)], 0.0, PROFILE)
    assert s_host == pytest.approx(0.8)
    assert unknown == 0


def test_blend_host_with_lower_storeys_no_lower_composition_falls_back_to_drzew():
    # Plan text: "gdy brak nizszych pieter -- S_host_nizsze = S_host_drzew",
    # so the blend is a no-op at ANY weight when species_lower is empty.
    s_host, unknown = blend_host_with_lower_storeys(0.8, [], 0.5, PROFILE)
    assert s_host == pytest.approx(0.8)
    assert unknown == 0


def test_blend_host_with_lower_storeys_normalizes_shares_not_summing_to_one():
    # Pooled PODSZ (SO 0.6) + PRZES (BK 0.6) sums to 1.2 -- S_host_nizsze is
    # the SHARE-WEIGHTED AVERAGE affinity (1.2*... / 1.2), not the raw
    # weighted sum, so it stays a comparable 0-1 score like S_host_drzew.
    s_host_lower_expected = (0.6 * 1.0 + 0.6 * 0.9) / 1.2  # SO=1.0, BK=0.9
    s_host, unknown = blend_host_with_lower_storeys(
        0.5, [("SO", 0.6), ("BK", 0.6)], 1.0, PROFILE,
    )
    assert s_host == pytest.approx(s_host_lower_expected)
    assert unknown == 0


def test_blend_host_with_lower_storeys_blends_at_intermediate_weight():
    s_host_lower = 1.0  # pure SO understory
    s_host, unknown = blend_host_with_lower_storeys(0.4, [("SO", 1.0)], 0.25, PROFILE)
    assert s_host == pytest.approx((1 - 0.25) * 0.4 + 0.25 * s_host_lower)
    assert unknown == 0


def test_blend_host_with_lower_storeys_counts_unknown_species():
    _, unknown = blend_host_with_lower_storeys(0.5, [("ZZZ", 1.0)], 0.5, PROFILE)
    assert unknown == 1


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


def _neutral_profile():
    import copy
    p = copy.deepcopy(PROFILE)
    p["habitat"] = {"age_mode": "neutral"}
    return p


def test_default_profile_age_mode_is_neutral():
    # Decyzja wlasciciela po walidacji Fazy 2: neutral jest domyslny.
    assert PROFILE["habitat"]["age_mode"] == "neutral"
    assert score_age(15, PROFILE) == 1.0
    assert score_age(150, PROFILE) == 1.0
    assert score_age(5, PROFILE) is None  # maska < 12 lat bez zmian


def test_curve_mode_remains_available_and_unchanged():
    p = _curve_profile()
    assert score_age(15, p) == pytest.approx(0.3 + (15 - 12) / (20 - 12) * (0.6 - 0.3))
    assert score_age(30, p) == pytest.approx(0.6 + (30 - 20) / (35 - 20) * (1.0 - 0.6))
    assert score_age(150, p) == pytest.approx(0.9)


def test_neutral_age_mode_gives_one_for_mask_passing_ages_and_keeps_the_mask():
    p = _neutral_profile()
    assert score_age(12, p) == 1.0
    assert score_age(15, p) == 1.0
    assert score_age(80, p) == 1.0
    assert score_age(150, p) == 1.0      # bez kary za > 120 lat
    assert score_age(5, p) is None       # maska wieku nadal dziala
    assert score_age(None, p) is None


def test_neutral_age_mode_makes_h_independent_of_age():
    p = _neutral_profile()
    row = {"species_cd": "SO", "part_cd": 10, "site_type": "BMSW"}
    h_young = compute_habitat({**row, "spec_age": 15}, p)
    h_old = compute_habitat({**row, "spec_age": 100}, p)
    assert h_young == pytest.approx(h_old)
    assert compute_habitat({**row, "spec_age": 5}, p) is None


def test_missing_habitat_section_defaults_to_neutral():
    import copy
    p = copy.deepcopy(PROFILE)
    p.pop("habitat")
    assert score_age(15, p) == 1.0


import pytest

from pipeline.habitat import load_profile as _load_profile_mask, mask_reasons, passes_mask

_PROFILE_MASK = _load_profile_mask("profiles/boletus_edulis.yaml")


def _mask_row(**over):
    base = {"area_type": "D-STAN", "spec_age": 60, "species_cd": "SO", "part_cd": 10, "site_type": "BMSW"}
    return {**base, **over}


@pytest.mark.parametrize("over, expected", [
    ({}, []),
    ({"area_type": "ZRAB"}, ["not_dstan"]),
    ({"spec_age": None}, ["no_age"]),
    ({"spec_age": 5}, ["too_young"]),
    ({"species_cd": "OL", "part_cd": 8}, ["excluded_species"]),
    ({"species_cd": "OL", "part_cd": 7}, []),
    ({"area_type": "ZRAB", "spec_age": 5}, ["not_dstan", "too_young"]),
])
def test_mask_reasons_lists_every_failed_condition(over, expected):
    row = _mask_row(**over)
    assert mask_reasons(row, _PROFILE_MASK) == expected
    assert passes_mask(row, _PROFILE_MASK) is (expected == [])
