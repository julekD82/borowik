"""A2: flush (wysyp) timing model -- plan 2026-09-27
(docs/superpowers/plans/2026-09-27-borowik-wysyp-a2.md).

Rain pulse -> thermal clock (cold nights slow it, frost stops it) ->
Gaussian flush curve in degree-days. Answers "kiedy", never "gdzie":
this module is deliberately NOT imported by pipeline.orchestrate /
scoring / mvp / habitat, so R cannot change because of it."""
import math
from dataclasses import dataclass

import numpy as np


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
