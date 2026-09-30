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
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline.flush import FlushParams, area_daily_weather, detect_pulses, fmt_day_range
from pipeline.phenology import compute_g_season
from pipeline.scoring import (
    classify_fruiting_level, compute_fruiting, score_frost, score_moisture, score_temperature,
)
from pipeline.weather import (
    climatology_window_values, compute_weather_features, percentile_rank, to_local_date,
)


def with_local_date(daily: pd.DataFrame) -> pd.DataFrame:
    """Adds a `local_date` column via pipeline.weather.to_local_date (plan
    1.8b: same shared, noon-corrected tz handling as
    pipeline.flush.area_daily_weather and pipeline.radar -- this module
    needs the per-point rows (for compute_weather_features' rolling
    windows), not the area median, so it can't just reuse area_daily_weather
    itself)."""
    return daily.assign(local_date=to_local_date(daily["date"]))


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


AGGREGATIONS = ("median_of_features", "median_f_points", "median_f_stands", "area_weighted_mean")


def uncertainty_level(days_ahead: int, profile: dict) -> str:
    """Faza 4.5: "ok" / "uncertain" ("prognoza niepewna") / "indicative"
    ("orientacyjnie") wg progow profilu ui.forecast_uncertain_from_day i
    ui.forecast_indicative_from_day, liczonych w dniach naprzod od dzis (dzis = 0).
    Progi to hipoteza do zaktualizowania po weryfikacji prognoz (Faza 2.7)."""
    ui = profile.get("ui") or {}
    if days_ahead >= ui.get("forecast_indicative_from_day", 8):
        return "indicative"
    if days_ahead >= ui.get("forecast_uncertain_from_day", 4):
        return "uncertain"
    return "ok"


def weighted_median(values, weights) -> float:
    v, w = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    ok = ~np.isnan(v) & (w > 0)
    v, w = v[ok], w[ok]
    if not len(v):
        return float("nan")
    order = np.argsort(v)
    v, w = v[order], w[order]
    cum = np.cumsum(w)
    return float(v[int(np.searchsorted(cum, 0.5 * cum[-1]))])


def aggregate_point_f(f_points, method: str, area_weights=None, stand_weights=None) -> float:
    """Faza 4.4: jedna wartosc F panelu z F policzonych osobno dla punktow siatki.
    median_f_points: mediana po punktach; median_f_stands: mediana wazona liczba
    wydzielen w masce przy punkcie (= mediana po wydzieleniach); area_weighted_mean:
    srednia wazona powierzchnia lasu przy punkcie. Bez wag -> wagi rowne."""
    f = np.asarray(f_points, dtype=float)
    ones = np.ones(len(f))
    if method == "median_f_points":
        return float(np.nanmedian(f))
    if method == "median_f_stands":
        return weighted_median(f, ones if stand_weights is None else stand_weights)
    if method == "area_weighted_mean":
        w = ones if area_weights is None else np.asarray(area_weights, dtype=float)
        ok = ~np.isnan(f) & (w > 0)
        return float((f[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else float("nan")
    raise ValueError(f"nieznana agregacja panelu: {method!r}")


def _share(mask, weights) -> float:
    mask, w = np.asarray(mask, dtype=bool), np.asarray(weights, dtype=float)
    return float(w[mask].sum() / w.sum()) if w.sum() > 0 else 0.0


def _nan_to_none(value):
    """NaN nie ma reprezentacji w JSON (write_conditions_json uzywa allow_nan=False)."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _nan_to_none(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nan_to_none(v) for v in value]
    return value


DAILY_BACK_DAYS = 35


def area_daily_table(daily: pd.DataFrame, points) -> pd.DataFrame:
    """Nowy frontend (panel pogody): mediana obszaru na lokalna dobe -- opad i temperatury
    (srednia, min., maks.) -- oraz sredni udzial godzin z radaru (0 bez radaru). W odroznieniu
    od pipeline.flush.area_daily_weather (zamrozony eksperyment) ma tmax_c i radar_share.
    Kolumn nieobecnych w `daily` (np. tmax_c w starszych testach) po prostu nie ma."""
    wanted = set(points)
    sel = daily[[(la, lo) in wanted for la, lo in zip(daily["lat"], daily["lon"])]]
    sel = sel.assign(local_date=to_local_date(sel["date"]))
    cols = [c for c in ("precipitation_mm", "tmean_c", "tmin_c", "tmax_c") if c in sel.columns]
    out = sel.groupby("local_date")[cols].median()
    if "radar_frac" in sel.columns:
        out["radar_share"] = sel.groupby("local_date")["radar_frac"].mean().fillna(0.0)
    else:
        out["radar_share"] = 0.0
    return out.sort_index().rename_axis("date")


def _round_or_none(value, digits: int):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def daily_series(area: pd.DataFrame, today: date, back_days: int = DAILY_BACK_DAYS) -> list[dict]:
    """Wiersze do wykresu opadu w panelu: od dzis - back_days do konca danych (prognoza)."""
    start = today - timedelta(days=back_days)
    rows = []
    for day, r in area[area.index >= start].iterrows():
        rows.append({
            "date": day.isoformat(),
            "precip_mm": _round_or_none(r.get("precipitation_mm"), 1),
            "radar_share": round(float(r.get("radar_share", 0.0)), 2),
            "tmin_c": _round_or_none(r.get("tmin_c"), 1),
            "tmax_c": _round_or_none(r.get("tmax_c"), 1),
            "forecast": day > today,
        })
    return rows


def weather_warnings(area: pd.DataFrame, today: date, horizon_days: int, profile: dict) -> list[dict]:
    """Ostrzezenia panelu z progow profilu (bez nowych parametrow): przymrozek -- dni od
    dzis-2 do konca horyzontu z mediana tmin < frost_tmin3_soft_c; upal z susza -- dni od
    dzis do konca horyzontu ze srednia temperatura 5 dni > heat_penalty_tmean5_c i opadem
    5 dni < heat_penalty_p5_mm (ta sama regula co kara za upal w F)."""
    cfg = profile["fruiting"]
    end = today + timedelta(days=horizon_days - 1)
    frost = []
    if "tmin_c" in area.columns:
        for day, t in area["tmin_c"].items():
            if today - timedelta(days=2) <= day <= end and pd.notna(t) and t < cfg["frost_tmin3_soft_c"]:
                frost.append(day.isoformat())
    heat = []
    if {"tmean_c", "precipitation_mm"} <= set(area.columns):
        tmean5 = area["tmean_c"].rolling(5, min_periods=5).mean()
        p5 = area["precipitation_mm"].rolling(5, min_periods=5).sum()
        for day in area.index:
            if (today <= day <= end and pd.notna(tmean5[day])
                    and tmean5[day] > cfg["heat_penalty_tmean5_c"] and p5[day] < cfg["heat_penalty_p5_mm"]):
                heat.append(day.isoformat())
    return [{"type": "frost", "dates": frost}, {"type": "heat_drought", "dates": heat}]


def build_conditions_timeline(daily: pd.DataFrame, points, clim_df: pd.DataFrame, clim_points,
                               today: date, profile: dict, rain_scale: float = 1.0,
                               point_weights: dict | None = None,
                               point_clim_cells: dict | None = None) -> dict:
    """`point_weights` (Faza 4.4): {(lat, lon): {"area_ha": powierzchnia lasu (wydzielenia w
    masce) najblizsza temu punktowi, "stands": ich liczba}} -- do agregacji F po wydzieleniach /
    wazonej powierzchnia oraz do udzialu powierzchni z przymrozkiem i silnym opadem. Bez wag
    udzialy sa liczone po punktach siatki.

    Wartosc F dnia zalezy od profilu `conditions.aggregation` (domyslnie `median_of_features` =
    dotychczasowa: mediana cech po punktach, potem jeden F); pozostale metody: AGGREGATIONS.

    `point_clim_cells` (poprawka 4): {(lat, lon) punktu pogody: (lat, lon) komorki klimatologii} --
    percentyl kazdego punktu jest liczony wzgledem historii JEGO komorki (tak jak w run_poc), a nie
    wzgledem puli wszystkich komorek. Bez niego (testy, stare wywolania) obowiazuje pula."""
    cfg = profile["conditions"]
    aggregation = cfg.get("aggregation", "median_of_features")
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"nieznana agregacja panelu: {aggregation!r}")
    params = _pulse_params(profile, rain_scale)
    area = area_daily_weather(daily, points)
    table = area_daily_table(daily, points)
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
        # Faza 4.4: F liczone osobno dla kazdego punktu siatki (kazdy punkt: wlasny percentyl
        # wzgledem tej samej puli klimatologii co wyzej) -- do porownania metod agregacji,
        # udzialu przymrozku/silnego opadu i, gdy wybrano, do samej wartosci panelu.
        keys = list(zip(feats["lat"], feats["lon"]))
        if point_clim_cells:
            cell_hist = {}
            def _hist(key, _cache=cell_hist, _doy=target_doy):
                cell = point_clim_cells[key]
                if cell not in _cache:
                    _cache[cell] = climatology_window_values(clim_df, *cell, _doy, "cwb26")
                return _cache[cell]
            pct_pts = np.array([percentile_rank(float(c), _hist(key)) for c, key in zip(feats["cwb26"], keys)])
        else:
            pct_pts = np.array([percentile_rank(float(c), cwb_hist) for c in feats["cwb26"]])
        f_pts = np.array([
            compute_fruiting(score_moisture(pp, 0.5, profile),
                             score_temperature(tm20, tm5, p5, profile), score_frost(tm3, profile),
                             g_season=g_season)
            for pp, tm20, tm5, p5, tm3 in zip(pct_pts, feats["tmean20"], feats["tmean5"], feats["p5"], feats["tmin3"])])
        pw = point_weights or {}
        area_w = np.array([pw.get(key, {}).get("area_ha", 0.0) for key in keys]) if pw else np.ones(len(keys))
        stand_w = np.array([pw.get(key, {}).get("stands", 0) for key in keys]) if pw else np.ones(len(keys))
        if pw and area_w.sum() == 0:
            area_w, stand_w = np.ones(len(keys)), np.ones(len(keys))
        f_by_method = {
            "median_of_features": f,
            **{name: aggregate_point_f(f_pts, name, area_w, stand_w) for name in AGGREGATIONS[1:]},
        }
        f_panel = f_by_method[aggregation]
        day_rain = with_ld[with_ld["local_date"] == day_k].groupby(["lat", "lon"])["precipitation_mm"].sum()
        heavy = np.array([day_rain.get(key, 0.0) >= cfg.get("heavy_rain_day_mm", cfg["pulse_min_mm"]) for key in keys])
        cwb_typical = float(np.nanmedian(cwb_hist)) if len(cwb_hist) else None
        days.append({"date": day_k.isoformat(), "F": round(f_panel, 3),
                     "level": classify_fruiting_level(f_panel, profile), "forecast": k > 0,
                     # Faza 4.5: dni naprzod i oznaczenie niepewnosci prognozy (progi w profilu ui.*)
                     "days_ahead": k, "uncertainty": uncertainty_level(k, profile),
                     # Faza 4.3: skladniki (mediana po punktach), bez wplywu na F
                     "components": {
                         "cwb26_mm": round(float(feats["cwb26"].median()), 1),
                         "cwb26_typical_mm": None if cwb_typical is None else round(cwb_typical, 1),
                         "pct_cwb26": round(pct_cwb26, 3),
                         "tmean20_c": round(float(feats["tmean20"].median()), 1),
                         "temp_optimum_c": profile["fruiting"]["temp_optimum_c"],
                         "tmin3_c": round(float(feats["tmin3"].median()), 1),
                         "M": round(m, 3), "T": round(t, 3), "K_frost": k_frost, "G_season": round(g_season, 3),
                     },
                     # Faza 4.4: lokalne zjawiska, ktorych mediana nie pokazuje
                     "frost_area_share": round(_share(feats["tmin3"].to_numpy() < profile["fruiting"]["frost_tmin3_soft_c"], area_w), 3),
                     "heavy_rain_area_share": round(_share(heavy, area_w), 3),
                     "F_by_aggregation": {name: round(float(v), 3) for name, v in f_by_method.items()}})
    return _nan_to_none({
        "generated_for": today.isoformat(), "horizon_days": cfg["horizon_days"],
        "pulse_min_mm": round(params.pulse_min_mm, 1), "rains": rains, "days": days,
        "summary": rains_summary(rains, params.pulse_min_mm),
        "aggregation": aggregation,
        "lookback_days": cfg["lookback_days"],
        "daily": daily_series(table, today),
        "warnings": weather_warnings(table, today, cfg["horizon_days"], profile),
        "uncertainty_thresholds": {
            "uncertain_from_day": (profile.get("ui") or {}).get("forecast_uncertain_from_day", 4),
            "indicative_from_day": (profile.get("ui") or {}).get("forecast_indicative_from_day", 8)},
    })
