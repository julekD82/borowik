from datetime import date

# Reference length for the circular day-of-year interpolation below.
# pipeline.orchestrate.run_poc's own target_doy (target_date.timetuple().
# tm_yday, used for climatology percentiles, plan 2.1 step A3) is likewise
# never leap-year-corrected -- this module accepts the same class of
# imprecision rather than introducing a different convention just for
# phenology, and target_date is always within Open-Meteo's 16-day forecast
# horizon (pipeline.prepare_trip.parse_args), so the practical effect is
# negligible.
_YEAR_LEN = 365


def _month_midpoint_doy(month: int) -> int:
    """Day-of-year of the 15th of `month`, in a fixed non-leap reference
    year (2023) -- a real date() call (not a hand-maintained lookup table)
    keeps the 12 breakpoints self-consistent by construction."""
    return date(2023, month, 15).timetuple().tm_yday


_MONTH_MIDPOINTS = [_month_midpoint_doy(m) for m in range(1, 13)]


def compute_g_season(target_doy: int, profile: dict) -> float:
    """Seasonal fruiting-frequency multiplier for
    pipeline.scoring.compute_fruiting's g_season (plan 2.1 "Zmiana 1"),
    from profile["phenology"]["gbif_monthly_counts"] (normalized to its
    own maximum month = 1.0), linearly interpolated between month
    MIDPOINTS (day 15 of each month, not month boundaries) so the curve
    has no jump crossing from one month to the next, then floored at
    profile["phenology"]["g_season_floor"].

    Not smoothed beyond this required month-midpoint interpolation: the
    raw monthly counts are already a clean, single-peaked curve (strictly
    rising Jan->Sep, then falling Sep->Dec, no jagged local dips) --
    additional smoothing (e.g. a moving average) would soften the real,
    sharp post-September drop (471->350->58) that a small sample can
    still show without it being noise, so it's deliberately left out
    (user asked to propose+justify whether to smooth, plan 2.1 review).

    `target_doy` should be the trip date's day-of-year
    (date.timetuple().tm_yday) -- same "trip date, not today" input
    pipeline.orchestrate.run_poc already uses for climatology
    percentiles (plan 2.1 step A3)."""
    cfg = profile["phenology"]
    counts = cfg["gbif_monthly_counts"]
    floor = cfg["g_season_floor"]
    max_count = max(counts)
    weights = [c / max_count for c in counts]

    # Triple the 12 anchors (one cycle before, the real cycle, one cycle
    # after) so linear interpolation across the Dec->Jan wrap needs no
    # special-casing -- target_doy always falls inside the middle cycle,
    # bracketed on both sides by real neighbours.
    doys = (
        [d - _YEAR_LEN for d in _MONTH_MIDPOINTS]
        + _MONTH_MIDPOINTS
        + [d + _YEAR_LEN for d in _MONTH_MIDPOINTS]
    )
    vals = weights * 3

    idx = 0
    for i in range(len(doys) - 1):
        if doys[i] <= target_doy <= doys[i + 1]:
            idx = i
            break
    d0, d1 = doys[idx], doys[idx + 1]
    v0, v1 = vals[idx], vals[idx + 1]
    frac = (target_doy - d0) / (d1 - d0)
    value = v0 + frac * (v1 - v0)
    return max(floor, value)
