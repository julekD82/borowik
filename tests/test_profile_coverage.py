"""Durable guard against the ASCII-profile-vs-diacritic-BDL-code class of bug.

pipeline.bdl.fetch_bdl transliterates Polish diacritics in site_type/species_cd
so they match the ASCII keys of profiles/*.yaml. That only helps if the
transliterated form of every code the BDL actually emits really exists in the
profile -- otherwise habitat.score_site/score_host silently fall back to the
0.5 "unknown" defaults and the ranking quietly degrades (which is exactly what
happened before the fix: 619/1046 stands on the Kieleczka tile).

When Faza 2 widens coverage (e.g. mountain site types BWG/BMWYŻ/LMG/LWYŻ),
add the raw BDL spelling to the lists below; the test then forces the profile
to grow a matching key instead of failing silently at runtime.
"""
import pytest

from pipeline.bdl import CODE_COLUMNS, normalize_code
from pipeline.habitat import load_profile

PROFILE = load_profile("profiles/boletus_edulis.yaml")

# Raw BDL spellings (with diacritics) for every code named in spec §4.3.
BDL_SITE_TYPES = [
    "BMŚW", "BŚW", "LMŚW", "BMW", "BW", "LMW", "LŚW", "BS",
    "LW", "BMB", "BB", "LMB", "OL", "OLJ", "LŁ",
    # Uzupełnienie 2.1 (docs/projekt-borowik.md §5.3, §0.1 audit): highland
    # (wyżynny) site types found in a real 25 km run, previously falling back
    # to unknown_site_score for ~2100 stands. BDL's real site_type spelling
    # for these (confirmed against the encyklopedialesna/Wikipedia habitat
    # taxonomy, not guessed) marks świeży (fresh) with no suffix on
    # BM/LM-prefixed codes and a single "Ś" suffix on L-prefixed codes;
    # wilgotny (moist) always gets a "W" suffix. That's why e.g. "LWYŻŚ"
    # normalizes to "LWYZS" (not "LWYZSW") -- it looked truncated but isn't.
    "BMWYŻ", "LMWYŻ", "LMWYŻW", "LWYŻŚ", "LWYŻW", "LŁWYŻ", "OLJWYŻ",
]
BDL_SPECIES = [
    "SO", "ŚW", "BK", "DB", "DB.S", "DB.B", "JD", "BRZ", "GB", "MD",
    "DG", "LP", "OS", "TP", "OL", "JS", "KL", "WZ", "AK",
    # Uzupełnienie 2.1 (docs/projekt-borowik.md §5.3, §0.1 audit): species
    # codes found in a real 25 km run with no profile entry. CZM.P and JB
    # were not named in the plan's table (only its "inne pojedyncze"
    # catch-all); user decision 2026-09-24: mask both like OL/JS/KL/WZ/AK
    # (Prunus/Sorbus are AM, not EcM, genera).
    "SO.C", "SO.WE", "DB.C", "JW", "OL.S", "WB", "CZM.P", "JB",
]


@pytest.mark.parametrize("raw", BDL_SITE_TYPES)
def test_every_bdl_site_type_has_a_profile_key(raw):
    key = normalize_code(raw)
    assert key in PROFILE["site_scores"], (
        f"BDL site_type {raw!r} normalizes to {key!r}, which is missing from "
        "profiles/boletus_edulis.yaml site_scores -- it would silently score "
        "unknown_site_score"
    )


@pytest.mark.parametrize("raw", BDL_SPECIES)
def test_every_bdl_species_has_a_profile_key(raw):
    key = normalize_code(raw)
    assert key in PROFILE["host_affinity"], (
        f"BDL species_cd {raw!r} normalizes to {key!r}, which is missing from "
        "profiles/boletus_edulis.yaml host_affinity -- it would silently score "
        "unknown_host_affinity"
    )


def test_profile_keys_are_already_in_transliterated_ascii_form():
    # A profile key containing a diacritic could never be hit, because
    # fetch_bdl strips diacritics before the lookup happens.
    for table in ("site_scores", "host_affinity"):
        for key in PROFILE[table]:
            assert normalize_code(key) == key, (
                f"{table} key {key!r} contains a character that "
                f"pipeline.bdl.normalize_code rewrites to "
                f"{normalize_code(key)!r}; it is unreachable"
            )
    for species in PROFILE["zero_affinity_mask_species"]:
        assert normalize_code(species) == species


def test_code_columns_are_the_two_columns_profiles_are_keyed_on():
    assert set(CODE_COLUMNS) == {"site_type", "species_cd"}
