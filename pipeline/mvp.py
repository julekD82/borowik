import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline.confidence import compute_confidence
from pipeline.explain import compute_log_contributions, generate_explanation, g_season_note
from pipeline.gdos import mark_gdos_blocked, gdos_status as _gdos_status
from pipeline.habitat import host_affinity
from pipeline.pressure import compute_d_park, compute_demand, compute_pressure
from pipeline.population_grid import impute_osm_population
from pipeline.routing import build_road_graph, nearest_entrance_distance
from pipeline.scoring import compute_ranking

_EXPLANATION_FACTORS = ["S_host", "S_site", "S_age", "M", "T", "K_frost"]
_FACTOR_KEY_MAP = {
    "S_host": "host", "S_site": "site", "S_age": "age",
    "M": "moisture", "T": "temperature", "K_frost": "frost",
}


def enrich_with_mvp_layers(stands: gpd.GeoDataFrame, profile: dict, gdos_gdf: gpd.GeoDataFrame,
                              osm_features: dict, zakaz_checker, alpha: float | None = None,
                              top_n_for_ban_check: int = 50,
                              roads_routing_gdf: gpd.GeoDataFrame | None = None,
                              entrances_gdf: gpd.GeoDataFrame | None = None,
                              top_n_for_routing: int = 0,
                              population_points_gdf: gpd.GeoDataFrame | None = None,
                              gdos_failed_tiles: list | None = None) -> gpd.GeoDataFrame:
    stands = stands.copy()
    alpha = profile["pressure"]["alpha_default"] if alpha is None else alpha

    gdos_blocked = mark_gdos_blocked(stands, gdos_gdf)
    stands["gdos_blocked"] = gdos_blocked
    stands["mask_full"] = stands["mask"] & ~gdos_blocked
    # Plan 1.6: gdos_status in {brak, blokada, kafel_pominiety} -- a stand
    # whose own tile's GDOS fetch failed is distinguishable from one that
    # was actually checked and found clear (gdos_blocked's own "optimistic
    # fallback", see that function's docstring, still governs mask_full --
    # this only makes the tradeoff visible per stand).
    centroids_for_status = stands.geometry.centroid
    stands["gdos_status"] = [
        _gdos_status(b, c, gdos_failed_tiles) for b, c in zip(gdos_blocked, centroids_for_status)
    ]

    parking = osm_features.get("parking")
    roads = osm_features.get("roads")
    if roads is not None and "highway" in roads.columns:
        # osm_features["roads"] now carries the full routing network
        # (paved + track, profile["osm"]["routing_highway_types"] -- "path"/
        # "footway"/"bridleway" were dropped, see that key's own comment,
        # accessibility plan Task 1) -- the euclidean d_park estimate below
        # keeps its original, deliberately paved-only scope (see
        # profiles/boletus_edulis.yaml's own comment on why "track" was
        # excluded: it made d_park nearly constant across a tile).
        roads = roads[roads["highway"].isin(profile["osm"]["road_highway_types"])]
    # Plan 1.4: population_points_gdf (GUS grid, when the caller has one) is
    # the Demand point source; otherwise OSM place nodes with missing
    # population imputed by settlement class -- never OSM's raw NaN, which
    # compute_demand's own .fillna(0.0) would otherwise silently zero out.
    places = (
        population_points_gdf if population_points_gdf is not None
        else impute_osm_population(osm_features.get("places"), profile)
    )
    centroids = stands.geometry.centroid

    d_parks = [compute_d_park(c, parking, roads, profile["pressure"]["euclid_factor"]) for c in centroids]
    demands = [compute_demand(c, places, profile["pressure"]["demand_decay_km"]) for c in centroids]
    demand_max = max([d for d in demands if d is not None], default=0.0)

    pressures = [
        compute_pressure(dp, dm, demand_max, profile) for dp, dm in zip(d_parks, demands)
    ]

    stands["d_park_m"] = d_parks
    stands["demand"] = demands
    stands["demand_norm"] = [0.0 if demand_max == 0 else d / demand_max for d in demands]
    stands["P"] = pressures
    stands["pressure_factor"] = [1.0 - alpha * p for p in pressures]
    stands["distance_method"] = "euclidean"
    stands["entrance_status"] = "not_evaluated"

    stands["R_final"] = [
        compute_ranking(mask, h, f_loc, p=p, alpha=alpha)
        for mask, h, f_loc, p in zip(stands["mask_full"], stands["H"], stands["F_loc"], stands["P"])
    ]

    if top_n_for_routing > 0 and roads_routing_gdf is not None and entrances_gdf is not None and len(entrances_gdf):
        graph = build_road_graph(roads_routing_gdf)
        top_idx = stands.sort_values("R_final", ascending=False).head(top_n_for_routing).index
        for idx in top_idx:
            centroid = stands.loc[idx, "geometry"].centroid
            distance, status = nearest_entrance_distance(graph, centroid, entrances_gdf)
            if distance is None:
                continue
            new_p = compute_pressure(distance, stands.loc[idx, "demand"], demand_max, profile)
            stands.loc[idx, "d_park_m"] = distance
            stands.loc[idx, "P"] = new_p
            stands.loc[idx, "pressure_factor"] = 1.0 - alpha * new_p
            stands.loc[idx, "distance_method"] = "network"
            stands.loc[idx, "entrance_status"] = status
            stands.loc[idx, "R_final"] = compute_ranking(
                stands.loc[idx, "mask_full"], stands.loc[idx, "H"], stands.loc[idx, "F_loc"],
                p=new_p, alpha=alpha,
            )

    stands["periodic_ban_checked"] = False
    stands["periodic_ban_active"] = False
    # Plan 1.6: "zrodlo zawiodlo" is now a real, survivable outcome instead
    # of an uncaught exception aborting the whole run (spec S13.1) -- a
    # stand whose check errors keeps its earlier (approximate) distance-only
    # R_final/mask_full, same as a stand that was never in the top-N at all.
    stands["periodic_ban_error"] = False
    if top_n_for_ban_check > 0 and len(stands):
        # centroids already carries stands.crs (centroid preserves it); do not
        # call set_crs on it -- set_crs raises on a GeoSeries whose crs is
        # already set unless allow_override=True. Reproject directly instead.
        centroids_4326 = centroids.to_crs("EPSG:4326")
        top_idx = stands.sort_values("R_final", ascending=False).head(top_n_for_ban_check).index
        for idx in top_idx:
            lon, lat = centroids_4326.loc[idx].x, centroids_4326.loc[idx].y
            try:
                banned = zakaz_checker(lat, lon)
            except Exception as exc:
                print(f"UWAGA: sprawdzenie zakazu okresowego nie powiodlo sie ({exc}) -- status: blad.", flush=True)
                stands.loc[idx, "periodic_ban_error"] = True
                continue
            stands.loc[idx, "periodic_ban_checked"] = True
            stands.loc[idx, "periodic_ban_active"] = bool(banned)
            if banned:
                stands.loc[idx, "R_final"] = 0.0
                # Not just a ranking discount: a banned stand is legally
                # off-limits, so mask_full must go False too, or a consumer
                # that reads `mask` directly (e.g. the exported scores.json)
                # would still show it as legal.
                stands.loc[idx, "mask_full"] = False

    # Plan 1.6: zakaz_status in {brak, zakaz, nie_sprawdzono, blad} -- a
    # single field a card/list can show discretely, instead of a caller
    # having to reconstruct it from three separate booleans.
    def _zakaz_status_row(row):
        if row["periodic_ban_error"]:
            return "blad"
        if not row["periodic_ban_checked"]:
            return "nie_sprawdzono"
        return "zakaz" if row["periodic_ban_active"] else "brak"

    stands["zakaz_status"] = stands.apply(_zakaz_status_row, axis=1)

    confidences, reasons_list = [], []
    for _, row in stands.iterrows():
        cls, reasons = compute_confidence(row, profile)
        confidences.append(cls)
        reasons_list.append(reasons)
    stands["confidence"] = confidences
    stands["confidence_reasons"] = reasons_list

    passing = stands[stands["mask_full"]]
    area_medians = {}
    for col in _EXPLANATION_FACTORS:
        key = _FACTOR_KEY_MAP[col]
        values = passing[col].dropna()
        values = values[values > 0]
        if len(values):
            area_medians[key] = float(values.median())
    pf_values = passing["pressure_factor"].dropna()
    pf_values = pf_values[pf_values > 0]
    if len(pf_values):
        area_medians["pressure_factor"] = float(pf_values.median())

    explanations = []
    for _, row in stands.iterrows():
        values = {_FACTOR_KEY_MAP[col]: row[col] for col in _EXPLANATION_FACTORS}
        values["pressure_factor"] = row["pressure_factor"]
        contributions = compute_log_contributions(values, area_medians)
        meta = {"species_cd": row.get("species_cd"), "site_type": row.get("site_type"),
                 "age": row.get("spec_age"), "P": row.get("P", 0.0),
                 # plan 2.1 step A4: lets generate_explanation distinguish a
                 # genuinely poor species match from a good species diluted
                 # by a low part_cd share (pipeline.explain._host_down_is_low_share).
                 "part_cd": row.get("part_cd"),
                 "host_affinity": host_affinity(row.get("species_cd"), profile)}
        explanation = generate_explanation(contributions, values, meta, profile)
        # Plan 2.1 "Zmiana 1": G_season absent (older/synthetic caller,
        # e.g. most of tests/test_mvp.py) defaults to 1.0 -- no note, exact
        # pre-this-step behaviour.
        note = g_season_note(row.get("G_season", 1.0), profile)
        if note is not None:
            explanation.append(note)
        explanations.append(explanation)
    stands["explanation"] = explanations

    return stands
