"""Kontrola pasa > 5 km od osiedla przy Lublincu (two_stage): dla kazdego
wydzielenia typ i odleglosc punktu o najwiekszym wkladzie w P oraz odsetek
wydzielen, dla ktorych ten punkt lezy <= 2,5 km. Tylko z cache.

    python scripts/faza3_pas5km_kontrola.py
"""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

import faza3_huff_raport as h  # noqa: E402
import faza3_raport as base  # noqa: E402
from pipeline.habitat import load_profile  # noqa: E402

THRESHOLD_M = 2500.0


def main() -> int:
    profile = load_profile("profiles/boletus_edulis.yaml")
    ctx = h.Ctx("cache", profile)
    cfg = copy.deepcopy(ctx.cfg)
    cfg["population_split"] = "two_stage"
    model = ctx.model(cfg)
    out = ctx.raw(model)
    p = 1.0 - np.exp(-out["access_raw"].values / ctx.fit_s(out["access_raw"].values))

    st = model.points[model.points["type"] == "settlement"]
    big = st[st["weight_pop"] >= 500]
    d_town = cKDTree(np.array([(g.x, g.y) for g in big.geometry])).query(ctx.xy)[0]
    e, n = base.TO_2180.transform(base.LUBLINIEC[1], base.LUBLINIEC[0])
    near = np.hypot(ctx.xy[:, 0] - e, ctx.xy[:, 1] - n) <= 8000
    sel = np.where(near & (d_town >= 5000))[0]

    pts = model.points.set_index("point_id")
    roads = model.roads.set_index("road_id")
    rows = []
    for i in sel:
        tid, ttype = out["top_point_id"].iloc[i], out["top_point_type"].iloc[i]
        if not tid:
            rows.append({"stand_id": ctx.stands["stand_id"].iloc[i], "typ": "brak", "odleglosc_m": np.nan, "P": p[i]})
            continue
        geom = pts.loc[tid, "geometry"] if tid in pts.index else roads.loc[tid, "geometry"]
        from shapely.geometry import Point
        d = geom.distance(Point(ctx.xy[i]))
        rows.append({"stand_id": ctx.stands["stand_id"].iloc[i], "typ": ttype, "odleglosc_m": float(d), "P": float(p[i]),
                     "zrodlo": pts.loc[tid, "source"] if tid in pts.index else roads.loc[tid, "source"]})
    df = pd.DataFrame(rows)
    within = df["odleglosc_m"] <= THRESHOLD_M
    result = {
        "wydzielen_w_pasie": int(len(df)), "zakres": "<= 8 km od centrum Lublinca i >= 5 km od najblizszego duzego osiedla",
        "prog_m": THRESHOLD_M,
        "odsetek_glowny_punkt_do_2_5_km": float(within.mean()),
        "liczba_do_2_5_km": int(within.sum()),
        "wg_typu": {t: {"liczba": int(len(g)), "mediana_odleglosci_m": float(g["odleglosc_m"].median()),
                        "do_2_5_km": int((g["odleglosc_m"] <= THRESHOLD_M).sum()), "srednie_P": float(g["P"].mean())}
                    for t, g in df.groupby("typ")},
        "odleglosc_kwantyle_m": {q: float(df["odleglosc_m"].quantile(q)) for q in (0.1, 0.5, 0.9, 1.0)},
        "srednie_P_pasa": float(df["P"].mean()),
    }
    # kontrola pomocnicza: gdyby nie liczyc osiedli, w tym pasie
    (base.OUT_DIR / "kontrola_pas_5km.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    df.to_csv(base.OUT_DIR / "kontrola_pas_5km.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
