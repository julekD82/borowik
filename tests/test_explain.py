import math
import pytest

from pipeline.habitat import load_profile
from pipeline.explain import compute_log_contributions, generate_explanation, FACTOR_WEIGHTS, g_season_note

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


def test_generate_explanation_host_down_distinguishes_low_share_from_poor_species_match():
    # Plan 2.1 step A4 (spec §5.3 "Poprawka wyjasnien"): BK (buk) has
    # host_affinity 0.9 in the profile -- a good match -- but at only 4/10
    # udzial: S_host = 0.4*0.9 + 0.6*0.5 = 0.66, diluted below a
    # hypothetical area median and flagged as a "down" contributor. The old
    # wording ("slabo pasuje", literally "poorly suited") wrongly implied
    # the SPECIES itself was a weak match, not just its coverage.
    contributions = {"host": -0.2}
    values = {"host": 0.66}
    meta = {
        "species_cd": "BK", "site_type": "BMSW", "age": 60, "P": 0.1,
        "part_cd": 4, "host_affinity": PROFILE["host_affinity"]["BK"],
    }
    entries = generate_explanation(contributions, values, meta, PROFILE)
    text = entries[0]["text"]
    assert "4/10" in text
    assert "słabo" not in text
    assert "0.66" in text


def test_generate_explanation_host_down_keeps_poor_species_wording_at_full_share():
    # GB (grab) has host_affinity 0.3 -- a genuinely weak partner -- at full
    # 10/10 share: S_host == affinity == 0.3, no dilution involved, so the
    # original "slabo pasuje" wording is accurate here.
    contributions = {"host": -0.5}
    values = {"host": 0.3}
    meta = {
        "species_cd": "GB", "site_type": "BMSW", "age": 60, "P": 0.1,
        "part_cd": 10, "host_affinity": PROFILE["host_affinity"]["GB"],
    }
    entries = generate_explanation(contributions, values, meta, PROFILE)
    text = entries[0]["text"]
    assert "słabo pasuje" in text
    assert "/10" not in text


def test_generate_explanation_host_down_falls_back_without_part_cd_or_affinity_meta():
    # Backward compatible: a caller that doesn't pass part_cd/host_affinity
    # in meta (e.g. the other tests in this file) still gets the original
    # wording, not a KeyError/crash.
    contributions = {"host": -0.2}
    values = {"host": 0.4}
    meta = {"species_cd": "SO", "site_type": "BMSW", "age": 60, "P": 0.1}
    entries = generate_explanation(contributions, values, meta, PROFILE)
    assert "słabo pasuje" in entries[0]["text"]


def test_generate_explanation_host_down_uses_poor_species_wording_when_affinity_itself_is_low():
    # DB.C (dab czerwony) has host_affinity 0.4 -- below the 0.5 "unknown
    # admixture" baseline -- even at a partial 6/10 share: mixing with 0.5
    # actually pulls S_host UP toward neutral here, not down, so a low
    # S_host in this case still means the dominant species itself is the
    # problem, not its share.
    contributions = {"host": -0.3}
    values = {"host": 0.4 * 0.6 + 0.5 * 0.4}
    meta = {
        "species_cd": "DB.C", "site_type": "BMSW", "age": 60, "P": 0.1,
        "part_cd": 6, "host_affinity": PROFILE["host_affinity"]["DB.C"],
    }
    entries = generate_explanation(contributions, values, meta, PROFILE)
    text = entries[0]["text"]
    assert "słabo pasuje" in text
    assert "/10" not in text


def test_g_season_note_none_when_at_or_above_threshold():
    assert g_season_note(0.5, PROFILE) is None
    assert g_season_note(1.0, PROFILE) is None


def test_g_season_note_present_and_worded_when_below_threshold():
    note = g_season_note(0.3, PROFILE)
    assert note is not None
    assert note["factor"] == "g_season"
    assert note["text"] == "poza szczytem sezonu (G_season=0.30)"
    assert note["contribution"] == pytest.approx(0.3 - 1.0)
