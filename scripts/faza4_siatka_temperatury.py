"""Faza 4.1: rzadsza siatka temperatury/ET0 (weather.temp_grid_km) -- porownanie
wariantow domyslny (5 km przy promieniu 25 km) / 10 km / 15 km dla Kieleczki.

Wszystko z cache oprocz JEDNEGO pobrania prognozy 7-dniowej dla siatki 5 km
(do horyzontu wyjazdu; siatki 10 i 15 km sa jej podzbiorami). Wywolanie API jest
zapisane w cache pod dzisiejsza data i liczone w raporcie.

  python scripts/faza4_siatka_temperatury.py

Wynik: docs/porownania/faza4/siatka_temperatury.json (+ wypis).
"""
import json
import pathlib
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from faza4_wspolne import (  # noqa: E402
    ROOT, KIELECZKA, RADIUS_KM, PROFILE_PATH, load_stands, score_with_grid,
    open_meteo_weight, load_profile, weather_grid_spacing_m,
)
from pipeline.orchestrate import DEFAULT_PAST_DAYS  # noqa: E402
from pipeline.prepare_trip import nearest_weather_point_per_stand, points_within_radius  # noqa: E402
from pipeline.tiles import tile_bbox_2180  # noqa: E402
from pipeline.weather import _default_open_meteo_call, make_grid  # noqa: E402

OUT = ROOT / "docs" / "porownania" / "faza4"
VARIANTS = [None, 10, 15]
HORIZON_DAYS = 7


def label(v):
    return "domyslny_5km" if v is None else f"{v}km"


def compare(base, other):
    m = base["mask"].to_numpy()
    d = np.abs(base.loc[m, "F"].to_numpy() - other.loc[m, "F"].to_numpy())
    cls_b = pd.cut(base.loc[m, "F"], [-1, .2, .45, .7, 2], labels=False)
    cls_o = pd.cut(other.loc[m, "F"], [-1, .2, .45, .7, 2], labels=False)
    kb, ko = base.loc[m, "K_frost"].to_numpy(), other.loc[m, "K_frost"].to_numpy()
    return {
        "stands_in_mask": int(m.sum()),
        "spearman_F": float(spearmanr(base.loc[m, "F"], other.loc[m, "F"]).statistic),
        "spearman_R": float(spearmanr(base.loc[m, "R"], other.loc[m, "R"]).statistic),
        "abs_dF_max": float(d.max()), "abs_dF_p95": float(np.percentile(d, 95)),
        "abs_dF_median": float(np.median(d)),
        "class_changes": int((cls_b.to_numpy() != cls_o.to_numpy()).sum()),
        "frost_status_changes_at_target": int(((kb < 1.0) != (ko < 1.0)).sum()),
        "frost_class_changes_at_target": int((kb != ko).sum()),
    }


def horizon_frost(stands, daily, spacing_by_variant):
    """Dla kazdego dnia horyzontu (dzis..+6): status przymrozku (tmin3 < 0 C) i
    twardego (< -2 C) na najblizszym punkcie siatki wariantu; zliczenie wydzielen,
    ktorych status w ktoryms dniu sie rozni od siatki domyslnej."""
    bbox = tile_bbox_2180(*KIELECZKA, size_km=2 * RADIUS_KM)
    dates = sorted(daily["date"].unique())[-HORIZON_DAYS:]
    piv = daily.pivot_table(index="date", columns=["lat", "lon"], values="tmin_c").sort_index()
    tmin3 = piv.rolling(3).min()
    out = {}
    ref = None
    for v, spacing in spacing_by_variant.items():
        pts = make_grid(bbox, spacing_m=spacing)
        nearest = nearest_weather_point_per_stand(stands, pts)
        pt_of = [nearest[s] for s in stands["stand_id"]]
        cols = list(dict.fromkeys(pt_of))
        idx = {c: i for i, c in enumerate(cols)}
        sel = np.array([idx[c] for c in pt_of])
        vals = tmin3.loc[dates, cols].to_numpy()          # (dni, punkty)
        per_stand = vals[:, sel].T                        # (wydzielenia, dni)
        soft, hard = per_stand < 0.0, per_stand < -2.0
        res = {"soft_days_any_stand_share": float(soft.any(axis=1).mean()),
               "hard_days_any_stand_share": float(hard.any(axis=1).mean())}
        if ref is None:
            ref = (soft, hard)
        else:
            gained = (soft & ~ref[0]).any(axis=1)
            lost = (~soft & ref[0]).any(axis=1)
            res.update({
                "stands_gaining_frost_any_day": int(gained.sum()),
                "stands_losing_frost_any_day": int(lost.sum()),
                "stands_changing_hard_frost_any_day": int((hard != ref[1]).any(axis=1).sum()),
            })
        out[label(v)] = res
    return out, [str(d)[:10] for d in dates]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    layer, stands = load_stands()
    profile = load_profile(PROFILE_PATH)
    today = date.today()
    result = {"date": str(today), "radius_km": RADIUS_KM, "stands": int(len(stands))}

    # --- koszt API (wzor Open-Meteo), swiezy przebieg: pogoda + os. czasu warunkow (fd7 w promieniu)
    bbox = tile_bbox_2180(*KIELECZKA, size_km=2 * RADIUS_KM)
    cost = {}
    for v in VARIANTS:
        sp = weather_grid_spacing_m({"weather": {"temp_grid_km": v}}, RADIUS_KM)
        pts = make_grid(bbox, spacing_m=sp)
        inr = points_within_radius(pts, *KIELECZKA, RADIUS_KM)
        cost[label(v)] = {
            "spacing_km": sp / 1000, "points": len(pts), "points_in_radius": len(inr),
            "weight_main_fd1": open_meteo_weight(len(pts), DEFAULT_PAST_DAYS, 1),
            "weight_conditions_fd7": open_meteo_weight(len(inr), 92, 7),
        }
        cost[label(v)]["weight_total"] = cost[label(v)]["weight_main_fd1"] + cost[label(v)]["weight_conditions_fd7"]
    result["api_cost"] = cost

    # --- F/R: cel = dzis (fd1) i cel = dzis+6 (fd7, opad z prognozy modelu)
    fd7_calls = []

    def fd7_api(points, past_days, forecast_days=1):
        fd7_calls.append((len(points), past_days, forecast_days))
        return _default_open_meteo_call(points, past_days, forecast_days)

    for name, target in (("cel_dzis_fd1", today), ("cel_plus6_fd7", today + timedelta(days=6))):
        scored = {}
        for v in VARIANTS:
            scored[label(v)] = score_with_grid(stands, layer, profile, temp_grid_km=v, target_date=target,
                                               weather_call_api=fd7_api)[0]
            print(name, label(v), "OK", flush=True)
        base = scored[label(None)]
        result[name] = {label(v): compare(base, scored[label(v)]) for v in VARIANTS if v is not None}
        result[name]["_base_F_quartiles"] = [float(x) for x in np.percentile(base.loc[base["mask"], "F"], [5, 25, 50, 75, 95])]
    result["fresh_api_calls_in_this_script"] = fd7_calls

    # --- horyzont przymrozku z serii dziennej fd7 (cache po pobraniu wyzej)
    from pipeline.weather import fetch_weather_raw
    daily = fetch_weather_raw(make_grid(bbox, spacing_m=5000.0), DEFAULT_PAST_DAYS, forecast_days=7,
                              call_api=fd7_api, cache_dir=ROOT / "cache")
    spacing = {v: weather_grid_spacing_m({"weather": {"temp_grid_km": v}}, RADIUS_KM) for v in VARIANTS}
    result["frost_horizon"], result["frost_horizon_dates"] = horizon_frost(stands.loc[stands["stand_id"].notna()], daily, spacing)

    # regula z planu
    ok = {}
    for v in (10, 15):
        k = label(v)
        p95 = max(result["cel_dzis_fd1"][k]["abs_dF_p95"], result["cel_plus6_fd7"][k]["abs_dF_p95"])
        fh = result["frost_horizon"][k]
        frost_lost = (fh.get("stands_gaining_frost_any_day", 0) + fh.get("stands_losing_frost_any_day", 0)
                      + result["cel_dzis_fd1"][k]["frost_status_changes_at_target"]
                      + result["cel_plus6_fd7"][k]["frost_status_changes_at_target"])
        ok[k] = {"p95_abs_dF_worst_case": p95, "frost_status_changes_total": frost_lost,
                 "meets_rule_p95_le_0_02_and_no_frost_change": bool(p95 <= 0.02 and frost_lost == 0)}
    result["rule"] = ok
    (OUT / "siatka_temperatury.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
