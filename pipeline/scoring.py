import math


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_moisture(pct_cwb26: float, pct_sm: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    mean_pct = (pct_cwb26 + pct_sm) / 2.0
    return _logistic((mean_pct - cfg["moisture_midpoint"]) / cfg["moisture_slope"])


def score_temperature(tmean20: float, tmean5: float, p5: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    base = math.exp(-((tmean20 - cfg["temp_optimum_c"]) ** 2) / (2 * cfg["temp_sigma_c"] ** 2))
    if tmean5 > cfg["heat_penalty_tmean5_c"] and p5 < cfg["heat_penalty_p5_mm"]:
        base *= cfg["heat_penalty_factor"]
    return base


def score_frost(tmin3: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    if tmin3 < cfg["frost_tmin3_hard_c"]:
        return cfg["frost_hard_factor"]
    if tmin3 < cfg["frost_tmin3_soft_c"]:
        return cfg["frost_soft_factor"]
    return 1.0


def compute_fruiting(m: float, t: float, k_frost: float, g_season: float = 1.0) -> float:
    return g_season * (m ** 0.6) * (t ** 0.4) * k_frost


def apply_moisture_modulation(f: float, moisture_cls: int, pct_m: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    if pct_m < cfg["dry_pct_threshold"]:
        multiplier = cfg["dry_multiplier_by_moisture"][moisture_cls]
    elif pct_m > cfg["wet_pct_threshold"]:
        multiplier = cfg["wet_multiplier_by_moisture"][moisture_cls]
    else:
        multiplier = 1.0
    return max(0.0, min(1.0, f * multiplier))


def classify_fruiting(f: float, profile: dict) -> str:
    for cls in profile["fruiting_classes"]:
        if f < cls["max"]:
            return cls["label"]
    return profile["fruiting_classes"][-1]["label"]


def compute_ranking(mask: bool, h: float | None, f_loc: float | None,
                      p: float = 0.0, alpha: float = 0.3) -> float:
    if not mask or h is None or f_loc is None:
        return 0.0
    return 100.0 * h * f_loc * (1.0 - alpha * p)
