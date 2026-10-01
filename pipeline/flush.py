"""A2: flush (wysyp) timing model -- plan 2026-09-27
(docs/archiwum/superpowers/plans/2026-09-27-borowik-wysyp-a2.md).

Rain pulse -> thermal clock (cold nights slow it, frost stops it) ->
Gaussian flush curve in degree-days. Answers "kiedy", never "gdzie":
this module is deliberately NOT imported by pipeline.orchestrate /
scoring / mvp / habitat, so R cannot change because of it."""
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline.phenology import compute_g_season
from pipeline.weather import to_local_date


@dataclass(frozen=True)
class FlushParams:
    wet_day_mm: float
    pulse_min_mm: float
    t_base_c: float
    cold_night_c: float
    cold_night_factor: float
    frost_c: float
    dd_peak: float
    dd_sigma: float


def flush_params(profile: dict, rain_scale: float = 1.0) -> FlushParams:
    cfg = profile["flush"]
    return FlushParams(
        wet_day_mm=cfg["wet_day_mm"], pulse_min_mm=cfg["pulse_min_mm"] * rain_scale,
        t_base_c=cfg["t_base_c"], cold_night_c=cfg["cold_night_c"],
        cold_night_factor=cfg["cold_night_factor"], frost_c=cfg["frost_c"],
        dd_peak=cfg["dd_peak"], dd_sigma=cfg["dd_sigma"],
    )


@dataclass(frozen=True)
class Pulse:
    start: int
    end: int
    rain_mm: float
    strength: float


def detect_pulses(precip, params: FlushParams) -> list[Pulse]:
    """Episodes of wet days (a single dry day inside allowed) whose total
    reaches pulse_min_mm. Strength 0.5 at the threshold, 1.0 at twice it."""
    p = np.asarray(precip, dtype=float)
    wet = p >= params.wet_day_mm
    pulses, i, n = [], 0, len(p)
    while i < n:
        if not wet[i]:
            i += 1
            continue
        start = end = i
        j = i + 1
        while j < n:
            if wet[j]:
                end = j
                j += 1
            elif j + 1 < n and wet[j + 1]:
                j += 1
            else:
                break
        total = float(p[start:end + 1].sum())
        if total >= params.pulse_min_mm:
            pulses.append(Pulse(start, end, total, min(1.0, total / (2.0 * params.pulse_min_mm))))
        i = end + 1
    return pulses


def degree_days_after(end: int, tmean, tmin, params: FlushParams) -> np.ndarray:
    """Thermal time accumulated on the days AFTER the pulse's last wet day:
    NaN up to and including `end`, +inf from the first frost day on."""
    tmean = np.asarray(tmean, dtype=float)
    tmin = np.asarray(tmin, dtype=float)
    dd = np.full(len(tmean), np.nan)
    total = 0.0
    for k in range(end + 1, len(tmean)):
        if tmin[k] < params.frost_c:
            dd[k:] = np.inf
            break
        rate = max(0.0, tmean[k] - params.t_base_c)
        if tmin[k] < params.cold_night_c:
            rate *= params.cold_night_factor
        total += rate
        dd[k] = total
    return dd


def wave_intensity(dd: np.ndarray, strength: float, params: FlushParams) -> np.ndarray:
    z = (np.asarray(dd, dtype=float) - params.dd_peak) / params.dd_sigma
    with np.errstate(invalid="ignore"):
        out = strength * np.exp(-0.5 * z * z)
    return np.nan_to_num(out, nan=0.0)


def flush_series(precip, tmean, tmin, params: FlushParams):
    """Daily flush index (max over waves) + the pulses and their thermal clocks."""
    pulses = detect_pulses(precip, params)
    dds = [degree_days_after(p.end, tmean, tmin, params) for p in pulses]
    index = np.zeros(len(np.asarray(precip)))
    for pulse, dd in zip(pulses, dds):
        index = np.maximum(index, wave_intensity(dd, pulse.strength, params))
    return index, pulses, dds


PHASE_LABELS = {
    "przed_fala": "grzyby dopiero rosną",
    "poczatek": "początek wysypu",
    "szczyt": "szczyt wysypu",
    "starzeje_sie": "fala się starzeje",
    "po_fali": "po fali",
}


def wave_phase(dd_today: float, params: FlushParams) -> str:
    if math.isnan(dd_today):
        return "przed_fala"  # rain still falling today: the clock has not started
    peak, sigma = params.dd_peak, params.dd_sigma
    if dd_today < peak - 2 * sigma:
        return "przed_fala"
    if dd_today < peak - 0.5 * sigma:
        return "poczatek"
    if dd_today <= peak + 0.5 * sigma:
        return "szczyt"
    if dd_today <= peak + 2 * sigma:
        return "starzeje_sie"
    return "po_fali"  # also +inf after frost


def peak_window(dd: np.ndarray, dates: list, params: FlushParams):
    """Dates when thermal time crosses peak -/+ 0.5 sigma. Past the end of
    the series: extrapolated with the mean daily rate of the last <=7
    accumulated days. None after frost or before any day accumulated."""
    dd = np.asarray(dd, dtype=float)
    if np.isinf(dd).any():
        return None
    finite = np.flatnonzero(np.isfinite(dd))
    if len(finite) == 0:
        return None
    last = finite[-1]
    k = min(7, len(finite))
    base = dd[finite[-k - 1]] if len(finite) > k else 0.0
    rate = (dd[last] - base) / k

    def crossing(threshold):
        hits = finite[dd[finite] >= threshold]
        if len(hits):
            return dates[hits[0]]
        if rate <= 0:
            return None
        return dates[last] + timedelta(days=math.ceil((threshold - dd[last]) / rate))

    lo = crossing(params.dd_peak - 0.5 * params.dd_sigma)
    hi = crossing(params.dd_peak + 0.5 * params.dd_sigma)
    return (lo, hi) if lo is not None and hi is not None else None


def fmt_day_range(a: date, b: date) -> str:
    if a == b:
        return f"{a.day}.{a.month:02d}"
    if a.month == b.month:
        return f"{a.day}–{b.day}.{b.month:02d}"
    return f"{a.day}.{a.month:02d}–{b.day}.{b.month:02d}"


def area_daily_weather(daily: pd.DataFrame, points) -> pd.DataFrame:
    """Per-LOCAL-day median over `points`. Plan 1.8b: local-date conversion
    is pipeline.weather.to_local_date, shared with pipeline.radar and
    pipeline.conditions_timeline -- see that function's docstring for why
    the noon-recentering matters around a DST transition."""
    wanted = set(points)
    sel = daily[[(la, lo) in wanted for la, lo in zip(daily["lat"], daily["lon"])]]
    local = to_local_date(sel["date"])
    return (sel.assign(local_date=local)
            .groupby("local_date")[["precipitation_mm", "tmean_c", "tmin_c"]].median()
            .sort_index()
            .rename_axis("date"))


def timeline_summary(waves: list[dict], pulse_min_mm: float) -> str:
    if not waves:
        return (f"Brak świeżej fali po większym deszczu (≥ {pulse_min_mm:.0f} mm) "
                "— wysyp mało prawdopodobny")
    parts = []
    for i, w in enumerate(waves):
        rain = fmt_day_range(date.fromisoformat(w["rain_start"]), date.fromisoformat(w["rain_end"]))
        text = f"{'Fala' if i == 0 else 'starsza fala'} po deszczu {rain}: {w['phase_label']}"
        if w["phase"] in ("przed_fala", "poczatek") and w["peak_from"]:
            peak = fmt_day_range(date.fromisoformat(w["peak_from"]), date.fromisoformat(w["peak_to"]))
            text += f", szczyt ok. {peak}"
        parts.append(text)
    return " · ".join(parts)


def build_area_timeline(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> dict:
    cfg = profile["flush"]
    params = flush_params(profile, rain_scale)
    horizon = cfg["horizon_days"]
    area = area[area.index <= today + timedelta(days=horizon - 1)]
    dates = list(area.index)
    if today not in dates:
        raise ValueError(f"brak danych pogodowych dla {today.isoformat()}")
    t = dates.index(today)
    index, pulses, dds = flush_series(area["precipitation_mm"].to_numpy(), area["tmean_c"].to_numpy(),
                                      area["tmin_c"].to_numpy(), params)
    seasonal = index * np.array([compute_g_season(d.timetuple().tm_yday, profile) for d in dates])
    days = []
    for k in range(t, min(t + horizon, len(dates))):
        value = float(seasonal[k])
        days.append({"date": dates[k].isoformat(), "index": round(value, 3),
                     "level": int(sum(value >= th for th in cfg["level_thresholds"])), "forecast": k > t})
    waves = []
    for pulse, dd in sorted(zip(pulses, dds), key=lambda x: -x[0].end):
        if pulse.end > t or (today - dates[pulse.end]).days > cfg["lookback_days"]:
            continue
        phase = wave_phase(float(dd[t]), params)
        if phase == "po_fali":
            continue
        window = peak_window(dd, dates, params)
        waves.append({
            "rain_start": dates[pulse.start].isoformat(), "rain_end": dates[pulse.end].isoformat(),
            "rain_mm": round(pulse.rain_mm, 1), "strength": round(pulse.strength, 2),
            "phase": phase, "phase_label": PHASE_LABELS[phase],
            "peak_from": window[0].isoformat() if window else None,
            "peak_to": window[1].isoformat() if window else None,
        })
        if len(waves) == cfg["max_waves"]:
            break
    return {"generated_for": today.isoformat(), "horizon_days": horizon,
            "pulse_min_mm": round(params.pulse_min_mm, 1), "waves": waves, "days": days,
            "summary": timeline_summary(waves, params.pulse_min_mm)}
