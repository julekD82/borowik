"""Faza 4.3 (diagnoza nasycenia F, czulosc +/-10%) i 4.4 (agregacja panelu 7 dni).
Tylko z cache. Bez zmian w modelu: liczy F z surowych skladnikow po zaburzeniu
parametru, progi klas zostaja z profilu.

  python scripts/faza4_nasycenie_agregacja.py
Wynik: docs/archiwum/porownania/faza4/nasycenie_agregacja.json
"""
import copy
import functools
import glob
import json
import math
import pathlib
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from faza4_wspolne import (  # noqa: E402
    ROOT, CACHE, KIELECZKA, RADIUS_KM, PROFILE_PATH, load_stands, score_with_grid, load_profile, _no_api,
)
from pipeline.conditions_timeline import build_conditions_timeline, AGGREGATIONS  # noqa: E402
from pipeline.orchestrate import DEFAULT_PAST_DAYS, CLIMATOLOGY_GRID_SPACING_M  # noqa: E402
from pipeline.prepare_trip import points_within_radius, conditions_point_weights, _radius_scaled_spacing  # noqa: E402
from pipeline.tiles import tile_bbox_2180  # noqa: E402
from pipeline.weather import fetch_weather_raw, fetch_climatology_raw, make_grid  # noqa: E402

OUT = ROOT / "docs" / "porownania" / "faza4"


def classes(f, profile):
    edges = [c["max"] for c in profile["fruiting_classes"]]
    return np.searchsorted(np.array(edges[:-1]), f, side="right")   # jak classify_fruiting: f < max


def f_from_components(d, profile):
    """Wektorowo: F = G * M^0.6 * T^0.4 * K z surowych wielkosci (pct_m, tmean20, tmean5, p5, tmin3)."""
    c = profile["fruiting"]
    m = 1.0 / (1.0 + np.exp(-(d["pct_CWB26"].to_numpy() - c["moisture_midpoint"]) / c["moisture_slope"]))
    t = np.exp(-((d["tmean20_c"].to_numpy() - c["temp_optimum_c"]) ** 2) / (2 * c["temp_sigma_c"] ** 2))
    heat = (d["tmean5_c"].to_numpy() > c["heat_penalty_tmean5_c"]) & (d["p5_mm"].to_numpy() < c["heat_penalty_p5_mm"])
    t = np.where(heat, t * c["heat_penalty_factor"], t)
    tmin3 = d["tmin3_c"].to_numpy()
    k = np.where(tmin3 < c["frost_tmin3_hard_c"], c["frost_hard_factor"],
                 np.where(tmin3 < c["frost_tmin3_soft_c"], c["frost_soft_factor"], 1.0))
    g = d["G_season"].to_numpy()
    return g * m ** 0.6 * t ** 0.4 * k, m, t, k


def diagnose(scored, profile):
    d = scored[scored["mask"]].copy()
    f, m, t, k = f_from_components(d, profile)
    assert np.allclose(f, d["F"].to_numpy(), atol=1e-9), "rekonstrukcja F sie nie zgadza"
    lm, lt, lk = 0.6 * np.log(np.maximum(m, 1e-12)), 0.4 * np.log(np.maximum(t, 1e-12)), np.log(k)
    var = {"M": float(np.var(lm)), "T": float(np.var(lt)), "K_frost": float(np.var(lk)), "G_season": 0.0}
    tot = sum(var.values()) or 1.0
    q = [5, 25, 50, 75, 95]
    cls = classes(d["F"].to_numpy(), profile)
    labels = [c["label"] for c in profile["fruiting_classes"]]
    out = {
        "stands_in_mask": int(len(d)),
        "quantiles_5_25_50_75_95": {n: [float(np.percentile(v, x)) for x in q] for n, v in
                                    (("F", f), ("M", m), ("T", t), ("K_frost", k), ("pct_CWB26", d["pct_CWB26"]))},
        "class_share": {labels[i]: float((cls == i).mean()) for i in range(len(labels))},
        "variance_share_of_log_F": {n: v / tot for n, v in var.items()},
        "G_season": float(d["G_season"].iloc[0]),
        "share_M_above_0_9": float((m > 0.9).mean()), "share_T_above_0_9": float((t > 0.9).mean()),
        "share_frost": float((k < 1).mean()),
    }
    # czulosc +/-10% jednego parametru
    base_cls = cls
    sens = {}
    fr = profile["fruiting"]
    for name in ["moisture_midpoint", "moisture_slope", "temp_optimum_c", "temp_sigma_c", "dry_pct_threshold",
                 "wet_pct_threshold", "heat_penalty_tmean5_c", "heat_penalty_p5_mm", "heat_penalty_factor",
                 "frost_tmin3_hard_c", "frost_hard_factor", "frost_soft_factor"]:
        row = {}
        for sign in (-0.10, 0.10):
            p2 = copy.deepcopy(profile)
            p2["fruiting"][name] = fr[name] * (1 + sign)
            f2, *_ = f_from_components(d, p2)
            row[f"{sign:+.0%}"] = int((classes(f2, profile) != base_cls).sum())
        sens[name] = row
    # G_season (krzywa sezonowosci) +/-10% tylko jako miara wrazliwosci (nie zmieniamy krzywej)
    for sign in (-0.10, 0.10):
        d2 = d.copy(); d2["G_season"] = d2["G_season"] * (1 + sign)
        f2, *_ = f_from_components(d2, profile)
        sens.setdefault("G_season(x)", {})[f"{sign:+.0%}"] = int((classes(f2, profile) != base_cls).sum())
    out["class_changes_under_pm10pct_of_parameter"] = sens
    return out


def history_of_classes(profile):
    """Rozklad klas F w eksportach z cache (scores_*.json z poprzednich przebiegow)."""
    out = {}
    for path in sorted(glob.glob(str(ROOT / "notebooks" / "output" / "scores_2026-*.json"))):
        df = pd.DataFrame(json.load(open(path, encoding="utf-8")))
        df = df[df["mask"]]
        cls = classes(df["F"].to_numpy(), profile)
        labels = [c["label"] for c in profile["fruiting_classes"]]
        out[pathlib.Path(path).stem[-10:]] = {"n": int(len(df)), "F_median": float(df["F"].median()),
                                              **{labels[i]: round(float((cls == i).mean()), 3) for i in range(len(labels))}}
    return out


def panel_aggregation(scored, profile):
    bbox = tile_bbox_2180(*KIELECZKA, size_km=2 * RADIUS_KM)
    pts = points_within_radius(make_grid(bbox, spacing_m=5000.0), *KIELECZKA, RADIUS_KM)
    daily = fetch_weather_raw(pts, DEFAULT_PAST_DAYS, forecast_days=7, call_api=_no_api, cache_dir=CACHE)
    clim_pts_all = make_grid(bbox, spacing_m=_radius_scaled_spacing(CLIMATOLOGY_GRID_SPACING_M, RADIUS_KM))
    clim_pts = points_within_radius(clim_pts_all, *KIELECZKA, RADIUS_KM)
    clim = fetch_climatology_raw(clim_pts, 1991, 2020, call_api=_no_api, cache_dir=CACHE)
    tl = build_conditions_timeline(daily, pts, clim, clim_pts, date.today(), profile,
                                   point_weights=conditions_point_weights(scored))
    rows = []
    for d in tl["days"]:
        by = d["F_by_aggregation"]
        rows.append({"date": d["date"], **by, "max_diff": round(max(by.values()) - min(by.values()), 3),
                     "frost_area_share": d["frost_area_share"], "heavy_rain_area_share": d["heavy_rain_area_share"]})
    return {"points_in_radius": len(pts), "days": rows,
            "max_diff_any_day": max(r["max_diff"] for r in rows),
            "rule_switch_if_diff_gt_0_05": bool(max(r["max_diff"] for r in rows) > 0.05)}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    profile = load_profile(PROFILE_PATH)
    layer, stands = load_stands()
    scored = score_with_grid(stands, layer, profile, temp_grid_km=None, target_date=date.today(), weather_call_api=_no_api)[0]
    res = {"date": str(date.today()), "diagnoza_dzis": diagnose(scored, profile),
           "historia_klas": history_of_classes(profile), "panel_7_dni": panel_aggregation(scored, profile)}
    (OUT / "nasycenie_agregacja.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))
