import math


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def moisture_percentile(pct_cwb26: float, pct_sm: float, profile: dict) -> float:
    """Weighted mean of the rain-balance and soil-moisture percentiles --
    the single moisture percentile both M and the site-moisture modulation
    use. profile fruiting.soil_moisture_weight (0.0 since 2026-09-27, see
    the profile comment) = the soil-moisture share."""
    w = profile["fruiting"]["soil_moisture_weight"]
    return (1.0 - w) * pct_cwb26 + w * pct_sm


def score_moisture(pct_cwb26: float, pct_sm: float, profile: dict) -> float:
    cfg = profile["fruiting"]
    mean_pct = moisture_percentile(pct_cwb26, pct_sm, profile)
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


def moisture_multiplier(pct_m: float, moisture_cls: int, profile: dict) -> float:
    """The habitat-moisture multiplier `q` (spec §4.4's F_loc = min[1; F*q]),
    factored out of apply_moisture_modulation so plan 1.2's diagnostics
    export can report it directly instead of trying to back it out of a
    clipped F_loc/F ratio."""
    cfg = profile["fruiting"]
    if pct_m < cfg["dry_pct_threshold"]:
        return cfg["dry_multiplier_by_moisture"][moisture_cls]
    if pct_m > cfg["wet_pct_threshold"]:
        return cfg["wet_multiplier_by_moisture"][moisture_cls]
    return 1.0


def apply_moisture_modulation(f: float, moisture_cls: int, pct_m: float, profile: dict) -> float:
    multiplier = moisture_multiplier(pct_m, moisture_cls, profile)
    return max(0.0, min(1.0, f * multiplier))


def classify_fruiting(f: float, profile: dict) -> str:
    for cls in profile["fruiting_classes"]:
        if f < cls["max"]:
            return cls["label"]
    return profile["fruiting_classes"][-1]["label"]


def classify_fruiting_level(f: float, profile: dict) -> int:
    """Same boundary semantics as classify_fruiting, as a 0-based index
    (plan A2 Plan-B: this is the flush timeline's per-day tile `level`,
    replacing a separate threshold table)."""
    classes = profile["fruiting_classes"]
    for i, cls in enumerate(classes):
        if f < cls["max"]:
            return i
    return len(classes) - 1


def compute_ranking(mask: bool, h: float | None, f_loc: float | None,
                      p: float = 0.0, alpha: float = 0.3) -> float:
    if not mask or h is None or f_loc is None:
        return 0.0
    return 100.0 * h * f_loc * (1.0 - alpha * p)
