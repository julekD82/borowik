CONFIDENCE_ORDER = {"NISKA": 0, "SREDNIA": 1, "WYSOKA": 2}


def score_data_quality(row: dict, profile: dict) -> float:
    cfg = profile["confidence"]["data_quality_factors"]
    species_known = row.get("species_cd") in profile["host_affinity"]
    kompletnosc = cfg["kompletnosc_gatunek_panujacy"] if species_known else cfg["kompletnosc_gatunek_nieznany"]
    return kompletnosc * cfg["swiezosc_bez_s2"] * cfg["pogoda_nwp_2km"]


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
    if factors["pogoda_nwp_2km"] < 1.0:
        reasons.append(cfg["reasons"]["weather_nwp"])
    species_known = row.get("species_cd") in profile["host_affinity"]
    if species_known:
        reasons.append(cfg["reasons"]["species_dominant_only"])
    else:
        reasons.append(cfg["reasons"]["species_unknown"])
    return final_class, reasons
