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
    return final_class, reasons
