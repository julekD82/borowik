"""A2 Plan-B: fact-only conditions timeline -- plan 2026-09-27
(docs/superpowers/plans/2026-09-27-borowik-wysyp-a2.md, "Decyzja
2026-09-27: Plan-B" section).

Reuses only pipeline.flush's pulse DETECTION (never its thermal-clock/
Gaussian model, which failed its GBIF ship gate) for a fact-only rain
summary, plus F's own components (M/T/K_frost/G_season -- the same
formula whose per-STAND, per-POINT form scored 0.626 in the GBIF
backtest), computed once per horizon day instead of once per search, from
the AREA MEDIAN of the weather grid -- a different, not separately
validated, aggregation (median-of-points ranked against pooled
climatology, vs. the backtest's one-point-ranked-against-its-own-cell).
Still answers "kiedy", never "gdzie": R is untouched."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline.flush import FlushParams, area_daily_weather, detect_pulses, fmt_day_range
from pipeline.phenology import compute_g_season
from pipeline.scoring import (
    classify_fruiting_level, compute_fruiting, score_frost, score_moisture, score_temperature,
)
from pipeline.weather import climatology_window_values, compute_weather_features, percentile_rank


def with_local_date(daily: pd.DataFrame) -> pd.DataFrame:
    """Adds a `local_date` column (Open-Meteo `date` is the UTC instant of
    local midnight; naive dates from test fakes are taken as-is) -- same
    tz handling as pipeline.flush.area_daily_weather, duplicated here
    because this module needs the per-point rows (for
    compute_weather_features' rolling windows), not the area median."""
    dates = daily["date"]
    local = (dates.dt.tz_convert("Europe/Warsaw") if dates.dt.tz is not None else dates).dt.date
    return daily.assign(local_date=local)


def _pulse_params(profile: dict, rain_scale: float) -> FlushParams:
    """detect_pulses only reads wet_day_mm/pulse_min_mm -- the thermal-
    clock fields are unused placeholders, kept only so pipeline.flush's
    (frozen) FlushParams shape doesn't need touching."""
    cfg = profile["conditions"]
    return FlushParams(wet_day_mm=cfg["wet_day_mm"], pulse_min_mm=cfg["pulse_min_mm"] * rain_scale,
                        t_base_c=0.0, cold_night_c=-1e9, cold_night_factor=1.0, frost_c=-1e9,
                        dd_peak=0.0, dd_sigma=1.0)


def recent_rains(area: pd.DataFrame, today: date, profile: dict, rain_scale: float = 1.0) -> list[dict]:
    """Up to conditions.max_rains most recent qualifying pulses that have
    already ended by `today`, newest first, within conditions.lookback_days."""
    cfg = profile["conditions"]
    params = _pulse_params(profile, rain_scale)
    dates = list(area.index)
    if today not in dates:
        raise ValueError(f"brak danych pogodowych dla {today.isoformat()}")
    t = dates.index(today)
    # Detection must never see forecast days: detect_pulses' one-dry-day
    # gap can otherwise merge an already-fallen pulse with a FORECAST wet
    # day, pushing the merged pulse's end into the future and silently
    # dropping real, already-fallen rain from the summary.
    pulses = detect_pulses(area["precipitation_mm"].to_numpy()[: t + 1], params)
    out = []
    for pulse in sorted(pulses, key=lambda p: -p.end):
        if (today - dates[pulse.end]).days > cfg["lookback_days"]:
            continue
        out.append({"start": dates[pulse.start].isoformat(), "end": dates[pulse.end].isoformat(),
                    "rain_mm": round(pulse.rain_mm, 1), "days_ago": (today - dates[pulse.end]).days})
        if len(out) == cfg["max_rains"]:
            break
    return out


def rains_summary(rains: list[dict], pulse_min_mm: float) -> str:
    if not rains:
        return f"Brak deszczu ≥ {pulse_min_mm:.0f} mm w ostatnich dniach."
    labels = ["Ostatni większy deszcz", "wcześniejszy deszcz"]
    parts = []
    for i, r in enumerate(rains):
        rng = fmt_day_range(date.fromisoformat(r["start"]), date.fromisoformat(r["end"]))
        parts.append(f"{labels[min(i, 1)]}: {rng} ({r['rain_mm']:.1f} mm), {r['days_ago']} dni temu")
    return " · ".join(parts)


def build_conditions_timeline(daily: pd.DataFrame, points, clim_df: pd.DataFrame, clim_points,
                               today: date, profile: dict, rain_scale: float = 1.0) -> dict:
    cfg = profile["conditions"]
    params = _pulse_params(profile, rain_scale)
    area = area_daily_weather(daily, points)
    rains = recent_rains(area, today, profile, rain_scale)  # raises ValueError if today missing

    with_ld = with_local_date(daily)
    all_dates = set(with_ld["local_date"])
    days = []
    for k in range(cfg["horizon_days"]):
        day_k = today + timedelta(days=k)
        if day_k not in all_dates:
            break
        sub = with_ld[with_ld["local_date"] <= day_k]
        feats = compute_weather_features(sub)
        target_doy = day_k.timetuple().tm_yday
        cwb_hist = np.concatenate([climatology_window_values(clim_df, lat, lon, target_doy, "cwb26")
                                    for lat, lon in clim_points]) if clim_points else np.array([])
        pct_cwb26 = percentile_rank(float(feats["cwb26"].median()), cwb_hist)
        m = score_moisture(pct_cwb26, 0.5, profile)  # pct_sm ignored: fruiting.soil_moisture_weight == 0.0
        t = score_temperature(float(feats["tmean20"].median()), float(feats["tmean5"].median()),
                              float(feats["p5"].median()), profile)
        k_frost = score_frost(float(feats["tmin3"].median()), profile)
        g_season = compute_g_season(target_doy, profile)
        f = compute_fruiting(m, t, k_frost, g_season=g_season)
        days.append({"date": day_k.isoformat(), "F": round(f, 3),
                     "level": classify_fruiting_level(f, profile), "forecast": k > 0})
    return {"generated_for": today.isoformat(), "horizon_days": cfg["horizon_days"],
            "pulse_min_mm": round(params.pulse_min_mm, 1), "rains": rains, "days": days,
            "summary": rains_summary(rains, params.pulse_min_mm)}
