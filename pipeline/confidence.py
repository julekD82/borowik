CONFIDENCE_ORDER = {"NISKA": 0, "SREDNIA": 1, "WYSOKA": 2}


def _uses_radar(row, profile) -> bool:
    coverage = row.get("rain_radar_coverage")
    return coverage is not None and coverage >= profile["radar"]["min_coverage_for_quality"]


def score_data_quality(row: dict, profile: dict) -> float:
    cfg = profile["confidence"]["data_quality_factors"]
    if row.get("s_host_source") == "paczka":
        # plan 2.1 step B2: S_host from a real BDL package's full DRZEW
        # composition (pipeline.bdl_packages) is strictly better data than
        # "just the dominant species", regardless of whether that species
        # itself is in the profile.
        kompletnosc = cfg["kompletnosc_pelny_sklad"]
    else:
        species_known = row.get("species_cd") in profile["host_affinity"]
        kompletnosc = cfg["kompletnosc_gatunek_panujacy"] if species_known else cfg["kompletnosc_gatunek_nieznany"]
    weather = cfg["pogoda_radar_1km"] if _uses_radar(row, profile) else cfg["pogoda_nwp_2km"]
    return kompletnosc * cfg["swiezosc_bez_s2"] * weather


def classify_data_quality(value: float, profile: dict) -> str:
    for cls in profile["confidence"]["data_quality_classes"]:
        if value < cls["max"]:
            return cls["label"]
    return profile["confidence"]["data_quality_classes"][-1]["label"]


def _real_gap_reasons(row: dict, profile: dict) -> list[str]:
    """Plan wdrozenia 1.7: each of these is a genuine data gap for THIS
    stand, not just an input to the smooth data-quality score above (which,
    per the technical review, rarely dips low enough to reach NISKA on its
    own -- see docs/Borowik_opis_techniczny_i_walidacja.md §12). Any one of
    them present forces the final class down to NISKA regardless of dq_class,
    while model_confidence_cap still caps the OTHER direction (never above
    SREDNIA)."""
    cfg = profile["confidence"]
    reasons_cfg = cfg["reasons"]
    reasons = []
    if row.get("insufficient_climatology"):
        reasons.append(reasons_cfg["empty_or_thin_climatology"])
    if profile["radar"]["enabled"]:
        coverage = row.get("rain_radar_coverage")
        if coverage is not None and coverage < cfg["radar_low_coverage_threshold"]:
            reasons.append(reasons_cfg["radar_low_coverage"])
    if row.get("osm_tile_skipped"):
        reasons.append(reasons_cfg["osm_tile_skipped"])
    if row.get("gdos_status") == "kafel_pominiety":
        reasons.append(reasons_cfg["gdos_tile_skipped"])
    # "site_type" in row (not just a falsy .get()): a real stand row always
    # has this WFS column, but a minimal test/synthetic row that omits it
    # entirely means "not provided here", not "provided and unrecognized" --
    # only the latter is a real data gap.
    if "site_type" in row and row.get("site_type") not in profile["site_scores"]:
        reasons.append(reasons_cfg["unknown_site_type"])
    if row.get("s_host_source") != "paczka":
        if row.get("species_cd") not in profile["host_affinity"]:
            reasons.append(reasons_cfg["species_unknown"])
    elif row.get("sklad_niepelny"):
        reasons.append(reasons_cfg["incomplete_composition"])
    return reasons


def compute_confidence(row: dict, profile: dict) -> tuple[str, list[str]]:
    cfg = profile["confidence"]
    dq_value = score_data_quality(row, profile)
    dq_class = classify_data_quality(dq_value, profile)
    model_class = cfg["model_confidence_cap"]
    final_class = dq_class if CONFIDENCE_ORDER[dq_class] <= CONFIDENCE_ORDER[model_class] else model_class

    reasons = [cfg["reasons"]["model_uncalibrated"]]
    factors = cfg["data_quality_factors"]
    if _uses_radar(row, profile):
        reasons.append(cfg["reasons"]["weather_radar"])
    elif factors["pogoda_nwp_2km"] < 1.0:
        reasons.append(cfg["reasons"]["weather_nwp"])
    if row.get("s_host_source") == "paczka":
        # "tylko gatunek panujący" no longer applies -- the whole point of
        # plan 2.1 step B2 is that this stand's S_host came from a real,
        # full species composition, not just the dominant one.
        reasons.append(cfg["reasons"]["species_full_composition"])
    else:
        species_known = row.get("species_cd") in profile["host_affinity"]
        if species_known:
            reasons.append(cfg["reasons"]["species_dominant_only"])
        else:
            reasons.append(cfg["reasons"]["species_unknown"])

    gap_reasons = _real_gap_reasons(row, profile)
    if gap_reasons:
        final_class = "NISKA"
        # gap_reasons may repeat species_unknown (already appended above via
        # the else-branch) -- de-duplicate while preserving order, so the
        # same sentence never shows twice in one card's reason list.
        for reason in gap_reasons:
            if reason not in reasons:
                reasons.append(reason)
    return final_class, reasons
