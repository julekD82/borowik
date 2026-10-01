"""Faza 3.6: raport porownawczy gravity vs access_points dla Kieleczki.

Dziala WYLACZNIE na cache (zadnych zapytan sieciowych) i na wynikach
przebiegu 1.6 z docs/archiwum/porownania/faza1_6 (geometrie + H/F/P/R per
wydzielenie). Zapisuje do docs/archiwum/porownania/faza3/:
  raport_dane.json          -- wszystkie liczby raportu
  roznice_P.csv             -- P_gravity, P_access, R przed/po per wydzielenie
  mapa_roznic_P_*.html      -- mapy roznic P (folium)
  mapa_pokrycia_nawierzchni.html
  kontrola_reczna.csv       -- 10 losowych wjazdow i 10 parkingow do przegladu

    python scripts/faza3_raport.py [--set-s]   # --set-s wypisuje S do profilu
"""
import argparse
import copy
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import folium  # noqa: E402
import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pyproj import Transformer  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from pipeline.access_data import load_access_sources  # noqa: E402
from pipeline.access_export import write_access_points_geojson, write_forest_roads_geojson  # noqa: E402
from pipeline.access_points import build_access_set  # noqa: E402
from pipeline.access_pressure import build_access_model, compute_access_pressure  # noqa: E402
from pipeline.entrances import compute_forest_boundary  # noqa: E402
from pipeline.habitat import load_profile  # noqa: E402
from pipeline.population_grid import load_population_points  # noqa: E402
from pipeline.rdlp import fetch_rdlp_boundaries_cached  # noqa: E402
from pipeline.regions import group_into_regions  # noqa: E402
from pipeline.scoring import compute_ranking  # noqa: E402
from pipeline.search_area import fetch_cached_osm, fetch_search_stands, search_tiles  # noqa: E402
from pipeline.tiles import tile_bbox_2180  # noqa: E402

LAT, LON, RADIUS_KM = 50.527, 18.605, 20.0
LUBLINIEC = (50.6688, 18.6832)
RUN_DIR = pathlib.Path("docs/archiwum/porownania/faza1_6")
OUT_DIR = pathlib.Path("docs/archiwum/porownania/faza3")
TO_4326 = Transformer.from_crs(2180, 4326, always_xy=True)
TO_2180 = Transformer.from_crs(4326, 2180, always_xy=True)


def _no_network(*_a, **_k):
    raise RuntimeError("raport dziala tylko na cache -- brak danych w cache")


def load_all(cache_dir: pathlib.Path, profile: dict):
    center, tiles = search_tiles(LAT, LON, RADIUS_KM)
    rdlp = fetch_rdlp_boundaries_cached(cache_dir)
    context, _ = fetch_search_stands(tiles, rdlp, cache_dir, _no_network)
    forest = compute_forest_boundary(context)
    scores = pd.DataFrame(json.load(open(RUN_DIR / "scores_2026-09-28.json", encoding="utf-8")))
    geo = gpd.read_parquet(RUN_DIR / "stands_mvp.parquet")
    stands = geo.merge(scores, on="stand_id").set_crs(geo.crs, allow_override=True)
    grid = next(cache_dir.glob("NSP2021*.geojson"))
    pop = load_population_points(grid, tile_bbox_2180(LAT, LON, size_km=2 * (RADIUS_KM + profile["population"]["buffer_km"])))
    osm, _ = fetch_cached_osm(tiles, cache_dir, profile, _no_network)
    sources = load_access_sources(tiles, cache_dir, profile["pressure"]["access_points"], _no_network, bdl_get=_no_network)
    return dict(tiles=tiles, forest=forest, stands=stands, pop=pop, osm=osm, sources=sources)


def pressure_for(centroid_xy, data, cfg):
    aset = build_access_set(forest_boundary=data["forest"], sources=data["sources"],
                            osm_parking=data["osm"].get("parking"), pop_points=data["pop"],
                            tiles=data["tiles"], cfg=cfg)
    pop_xy = np.array([(g.x, g.y) for g in data["pop"].geometry])
    model = build_access_model(aset, pop_xy, data["pop"]["population"].astype(float).values, cfg)
    return model, compute_access_pressure(centroid_xy, model)


def solve_s(raw: np.ndarray, target_median: float) -> float:
    """S tak, by mediana P = target (mediana raw > 0), inaczej dopasowanie sredniej."""
    med = float(np.median(raw))
    if med > 0 and 0 < target_median < 1:
        return -med / np.log(1 - target_median)
    return float("nan")


def area_share(stands, mask) -> float:
    a = stands.geometry.area.values
    return float(a[mask].sum() / a.sum()) if a.sum() else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="cache")
    ap.add_argument("--profile", default="profiles/boletus_edulis.yaml")
    args = ap.parse_args()
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = load_profile(args.profile)
    cfg = profile["pressure"]["access_points"]
    data = load_all(pathlib.Path(args.cache_dir), profile)
    stands = data["stands"]
    cent = stands.geometry.centroid
    xy = np.array([(c.x, c.y) for c in cent])
    mask = stands["mask"].values.astype(bool)
    alpha = profile["pressure"]["alpha_default"]
    report = {"stand_count": int(len(stands)), "mask_passing": int(mask.sum())}

    model, out = pressure_for(xy, data, cfg)
    p_grav = stands["P"].values.astype(float)
    raw = out["access_raw"].values
    target = float(np.median(p_grav[mask]))
    s_fit = solve_s(raw[mask], target)
    report["saturation"] = {"S_in_profile": cfg["saturation_s"], "S_fit_median_match": s_fit,
                            "gravity_median_P_mask": target, "median_raw_mask": float(np.median(raw[mask])),
                            "share_raw_zero_mask": float((raw[mask] == 0).mean())}
    s_used = cfg["saturation_s"] if not np.isnan(s_fit) else cfg["saturation_s"]
    p_acc = 1.0 - np.exp(-raw / s_used)
    report["counts"] = model.counts
    report["P"] = {
        "gravity_median_mask": target, "access_median_mask": float(np.median(p_acc[mask])),
        "gravity_mean_mask": float(p_grav[mask].mean()), "access_mean_mask": float(p_acc[mask].mean()),
        "spearman_P_mask": float(spearmanr(p_grav[mask], p_acc[mask])[0]),
    }

    # --- kontrole sensownosci -------------------------------------------------
    pts_xy = np.array([(g.x, g.y) for g in model.points.geometry]) if len(model.points) else np.empty((0, 2))
    d_pt = cKDTree(pts_xy).query(xy)[0] if len(pts_xy) else np.full(len(xy), np.inf)
    corr = cKDTree(model.corridor_xy).query(xy)[0] if len(model.corridor_xy) else np.full(len(xy), np.inf)
    max_range = max(c["range_m"] for k, c in cfg["types"].items() if k != "forest_road")
    beyond = (d_pt > max_range) & (corr > cfg["types"]["forest_road"]["range_m"])
    report["checks"] = {
        "stands_beyond_all_ranges": int(beyond.sum()),
        "of_which_P_nonzero": int((p_acc[beyond] > 0).sum()),
        "share_forest_area_P_gt_0_5_all": area_share(stands, p_acc > 0.5),
        "share_forest_area_P_gt_0_5_mask": area_share(stands[mask], p_acc[mask] > 0.5),
        "share_forest_area_P_gt_0_5_gravity_all": area_share(stands, p_grav > 0.5),
        "share_forest_area_P_gt_0": area_share(stands, p_acc > 0),
        "threshold_warning_70pct": bool(area_share(stands, p_acc > 0.5) > 0.7),
    }
    # brak skokow: roznice P miedzy sasiadami (centroidy <= 200 m)
    tree = cKDTree(xy)
    pairs = np.array(list(tree.query_pairs(200.0)))
    if len(pairs):
        d_acc = np.abs(p_acc[pairs[:, 0]] - p_acc[pairs[:, 1]])
        d_gr = np.abs(p_grav[pairs[:, 0]] - p_grav[pairs[:, 1]])
        report["checks"]["neighbour_jump_p99_access"] = float(np.percentile(d_acc, 99))
        report["checks"]["neighbour_jump_p99_gravity"] = float(np.percentile(d_gr, 99))
        report["checks"]["neighbour_jump_max_access"] = float(d_acc.max())
        report["checks"]["neighbour_jump_max_gravity"] = float(d_gr.max())

    # --- pas lasu przy Lublincu -------------------------------------------------
    st_pts = model.points[model.points["type"] == "settlement"]
    big = st_pts[st_pts["weight_pop"] >= 500]
    if len(big):
        bxy = np.array([(g.x, g.y) for g in big.geometry])
        d_town = cKDTree(bxy).query(xy)[0]
        e, n = TO_2180.transform(LUBLINIEC[1], LUBLINIEC[0])
        near_lub = np.hypot(xy[:, 0] - e, xy[:, 1] - n) <= 8000
        bins = [0, 500, 1000, 2000, 3000, 5000, 1e9]
        rows = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            sel = near_lub & (d_town >= lo) & (d_town < hi)
            if sel.sum():
                rows.append({"od_osiedla_m": f"{lo}-{hi if hi < 1e9 else 'inf'}", "wydzielen": int(sel.sum()),
                             "P_access_srednia": float(p_acc[sel].mean()), "P_gravity_srednia": float(p_grav[sel].mean())})
        report["lubliniec_belt"] = rows

    # --- R, top-20, rejony przed/po ----------------------------------------------
    r_old = np.array([compute_ranking(m, h, f, p=p, alpha=alpha) for m, h, f, p in
                      zip(stands["mask"], stands["H"], stands["F_loc"], p_grav)])
    r_new = np.array([compute_ranking(m, h, f, p=p, alpha=alpha) for m, h, f, p in
                      zip(stands["mask"], stands["H"], stands["F_loc"], p_acc)])
    report["R_recompute_check_max_abs_diff_vs_1_6"] = float(np.max(np.abs(r_old - stands["R"].values)))
    top_old = set(stands.loc[np.argsort(-r_old)[:20], "stand_id"])
    top_new = set(stands.loc[np.argsort(-r_new)[:20], "stand_id"])
    report["ranking"] = {"top20_overlap": len(top_old & top_new),
                         "spearman_R_mask": float(spearmanr(r_old[mask], r_new[mask])[0])}
    frame = stands[["stand_id", "geometry", "mask"]].copy()
    frame["mask_full"] = frame["mask"]
    regions = {}
    for label, r in (("przed", r_old), ("po", r_new)):
        f = frame.copy()
        f["R_final"] = r
        g = group_into_regions(f, profile)
        regions[label] = g
    def _reg_list(g):
        return [{"region_id": row["region_id"], "rank_score": float(row["rank_score"]),
                 "stand_count": int(row["stand_count"]),
                 "centroid_lon_lat": [round(v, 5) for v in TO_4326.transform(row.geometry.centroid.x, row.geometry.centroid.y)]}
                for _, row in g.iterrows()]
    old_c = np.array([(row.geometry.centroid.x, row.geometry.centroid.y) for _, row in regions["przed"].iterrows()]).reshape(-1, 2)
    new_c = np.array([(row.geometry.centroid.x, row.geometry.centroid.y) for _, row in regions["po"].iterrows()]).reshape(-1, 2)
    same = 0
    for c in old_c:
        if len(new_c) and np.min(np.hypot(new_c[:, 0] - c[0], new_c[:, 1] - c[1])) <= 1600:
            same += 1
    report["regions"] = {"przed": _reg_list(regions["przed"]), "po": _reg_list(regions["po"]),
                         "old_regions_kept_within_1600m": same}

    # --- 10 najwiekszych zmian P ---------------------------------------------------
    delta = p_acc - p_grav
    lookup = {r["point_id"]: r for _, r in model.points.iterrows()}
    lookup.update({r["road_id"]: r for _, r in model.roads.iterrows()})

    def _explain(i):
        tid = out["top_point_id"].iloc[i]
        ttype = out["top_point_type"].iloc[i]
        if not tid:
            return "brak punktu dostepu w zasiegu (P=0); w gravity presja od ludnosci z odleglosci"
        row = lookup.get(tid)
        src = row["source"] if row is not None else "?"
        name = (row["name"] if row is not None and "name" in row and isinstance(row["name"], str) else "")
        return f"{ttype} {tid} ({src}{', ' + name if name else ''}); wklady: " + ", ".join(
            f"{k[9:]}={out[k].iloc[i]:.3f}" for k in out.columns if k.startswith("pcontrib_") and out[k].iloc[i] > 0)

    idx_mask = np.where(mask)[0]
    order = idx_mask[np.argsort(delta[idx_mask])]
    def _rows(ids):
        res = []
        for i in ids:
            lon, lat = TO_4326.transform(xy[i, 0], xy[i, 1])
            res.append({"stand_id": stands["stand_id"].iloc[i], "lat": round(lat, 5), "lon": round(lon, 5),
                        "P_gravity": round(float(p_grav[i]), 3), "P_access": round(float(p_acc[i]), 3),
                        "d_parking_m": None if np.isnan(out["d_parking_m"].iloc[i]) else round(float(out["d_parking_m"].iloc[i])),
                        "wyjasnienie": _explain(i)})
        return res
    report["top10_wzrost_P"] = _rows(order[::-1][:10])
    report["top10_spadek_P"] = _rows(order[:10])

    # --- wrazliwosc: nieznana nawierzchnia, zasieg poprzeczny --------------------------
    variants = {}
    for label, unknown in (("nieznana_jak_utwardzona", 1.0), ("nieznana_jak_gruntowa", 0.3), ("baza_0_5", 0.5)):
        c2 = copy.deepcopy(cfg)
        c2["surface_multiplier"]["unknown"] = unknown
        _, o2 = pressure_for(xy, data, c2)
        p2 = 1.0 - np.exp(-o2["access_raw"].values / s_used)
        variants[label] = {"median_P_mask": float(np.median(p2[mask])), "share_area_P_gt_0_5": area_share(stands, p2 > 0.5),
                           "spearman_vs_baza": float(spearmanr(p_acc[mask], p2[mask])[0])}
    report["sensitivity_unknown_surface"] = variants
    lateral = {}
    for r_m in (300.0, 500.0, 1000.0):
        c2 = copy.deepcopy(cfg)
        c2["types"]["forest_road"]["range_m"] = r_m
        _, o2 = pressure_for(xy, data, c2)
        p2 = 1.0 - np.exp(-o2["access_raw"].values / s_used)
        lateral[f"{int(r_m)}m"] = {
            "share_forest_area_reached_by_roads": area_share(stands, o2["pcontrib_forest_road"].values > 0),
            "share_area_P_gt_0_5": area_share(stands, p2 > 0.5), "median_P_mask": float(np.median(p2[mask]))}
    report["lateral_range_comparison"] = lateral

    # --- pokrycie nawierzchni (BDL/OSM) w komorkach 2 x 2 km -----------------------------
    corr_roads = model.roads[model.roads["kind"].isin(["closed", "fire"])].copy()
    if len(corr_roads):
        corr_roads["len"] = corr_roads.geometry.length
        corr_roads["known"] = corr_roads["surface_class"] != "unknown"
        mids = corr_roads.geometry.interpolate(0.5, normalized=True)
        corr_roads["cx"] = (mids.x // 2000).astype(int)
        corr_roads["cy"] = (mids.y // 2000).astype(int)
        grp = corr_roads.groupby(["cx", "cy"]).apply(
            lambda g: pd.Series({"km": g["len"].sum() / 1000, "known_share": g.loc[g["known"], "len"].sum() / g["len"].sum()}),
            include_groups=False).reset_index()
        grp = grp[grp["km"] >= 1.0]
        report["surface_coverage"] = {
            "network_km": float(corr_roads["len"].sum() / 1000),
            "known_share_overall": float(corr_roads.loc[corr_roads["known"], "len"].sum() / corr_roads["len"].sum()),
            "fire_road_km": float(corr_roads.loc[corr_roads["kind"] == "fire", "len"].sum() / 1000),
            "fire_known_share": float(corr_roads.loc[(corr_roads["kind"] == "fire") & corr_roads["known"], "len"].sum()
                                       / max(1e-9, corr_roads.loc[corr_roads["kind"] == "fire", "len"].sum())),
            "cells_2x2km": int(len(grp)),
            "cell_known_share_quantiles": {q: float(grp["known_share"].quantile(q)) for q in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)},
            "cells_below_20pct_known": int((grp["known_share"] < 0.2).sum()),
        }
        grp.to_csv(OUT_DIR / "pokrycie_nawierzchni_kafle_2x2.csv", index=False)
        m = folium.Map(location=[LAT, LON], zoom_start=10, tiles="OpenStreetMap")
        for _, r in grp.iterrows():
            e0, n0 = r["cx"] * 2000, r["cy"] * 2000
            (lo1, la1), (lo2, la2) = TO_4326.transform(e0, n0), TO_4326.transform(e0 + 2000, n0 + 2000)
            share = r["known_share"]
            color = "#2e7d32" if share >= 0.6 else "#f9a825" if share >= 0.3 else "#c62828"
            folium.Rectangle([[la1, lo1], [la2, lo2]], color=color, weight=1, fill=True, fill_opacity=0.45,
                             tooltip=f"{share:.0%} znanej nawierzchni, {r['km']:.1f} km sieci").add_to(m)
        m.save(OUT_DIR / "mapa_pokrycia_nawierzchni.html")

    # --- kontrola reczna ---------------------------------------------------------------------
    rng = np.random.default_rng(42)
    manual = []
    for label, sel in (("wjazd", model.points[model.points["type"].isin(["entrance", "gate"])]),
                       ("parking", model.points[model.points["type"] == "parking"])):
        if not len(sel):
            continue
        take = sel.iloc[rng.choice(len(sel), size=min(10, len(sel)), replace=False)]
        for _, r in take.iterrows():
            lon, lat = TO_4326.transform(r.geometry.x, r.geometry.y)
            manual.append({"rodzaj": label, "typ": r["type"], "podtyp": r["subtype"], "zrodlo": r["source"], "id": r["point_id"],
                           "nazwa": r["name"], "lat": round(lat, 6), "lon": round(lon, 6),
                           "widok_satelitarny": f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},250m/data=!3m1!1e3"})
    pd.DataFrame(manual).to_csv(OUT_DIR / "kontrola_reczna.csv", index=False, encoding="utf-8")

    # --- mapy roznic P -------------------------------------------------------------------------
    def _diff_map(name, center, zoom, radius_m=None):
        m = folium.Map(location=list(center), zoom_start=zoom, tiles="OpenStreetMap")
        e, n = TO_2180.transform(center[1], center[0])
        sel = np.arange(len(xy)) if radius_m is None else np.where(np.hypot(xy[:, 0] - e, xy[:, 1] - n) <= radius_m)[0]
        sel = sel[np.argsort(-np.abs(delta[sel]))[:5000]]
        for i in sel:
            d = float(delta[i])
            if abs(d) < 0.05:
                continue
            lon, lat = TO_4326.transform(xy[i, 0], xy[i, 1])
            color = "#b71c1c" if d > 0 else "#0d47a1"
            folium.CircleMarker([lat, lon], radius=3, color=color, weight=0, fill=True, fill_opacity=min(0.9, 0.3 + abs(d)),
                                tooltip=f"{stands['stand_id'].iloc[i]}: P {p_grav[i]:.2f} -> {p_acc[i]:.2f}").add_to(m)
        for _, r in model.points[model.points["type"].isin(["parking", "gate"])].iterrows():
            lon, lat = TO_4326.transform(r.geometry.x, r.geometry.y)
            if radius_m is None or np.hypot(r.geometry.x - e, r.geometry.y - n) <= radius_m:
                folium.CircleMarker([lat, lon], radius=4, color="#000", weight=1, fill=True,
                                    fill_color="#1f4e9c" if r["type"] == "parking" else "#c0392b",
                                    tooltip=f"{r['type']} {r['source']} {r['name']}").add_to(m)
        m.save(OUT_DIR / name)
    _diff_map("mapa_roznic_P_kieleczka.html", (LAT, LON), 10)
    _diff_map("mapa_roznic_P_lubliniec.html", LUBLINIEC, 12, radius_m=9000)

    # --- CSV per wydzielenie -------------------------------------------------------------------------
    pd.DataFrame({"stand_id": stands["stand_id"], "mask": mask, "P_gravity": p_grav, "P_access": p_acc,
                  "R_przed": r_old, "R_po": r_new, "top_point_id": out["top_point_id"],
                  "top_point_type": out["top_point_type"]}).to_csv(OUT_DIR / "roznice_P.csv", index=False)

    # --- eksport warstw mapy z realnych danych (rozmiar, tolerancja uproszczenia) -------------
    ap_path = write_access_points_geojson(model, OUT_DIR / "access_points_2026-09-28.geojson")
    fr_path, tol = write_forest_roads_geojson(model, OUT_DIR / "forest_roads_2026-09-28.geojson")
    report["export"] = {"access_points_bytes": ap_path.stat().st_size, "forest_roads_bytes": fr_path.stat().st_size,
                        "forest_roads_tolerance_m": tol, "features_points": int(len(model.points)),
                        "features_roads": int(len(model.roads))}

    report["czas_s"] = round(time.time() - t0, 1)
    (OUT_DIR / "raport_dane.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("saturation", "P", "checks", "counts")}, ensure_ascii=False, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
