import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline.confidence import compute_confidence
from pipeline.explain import compute_log_contributions, generate_explanation
from pipeline.gdos import mark_gdos_blocked
from pipeline.pressure import compute_d_park, compute_demand, compute_pressure
from pipeline.scoring import compute_ranking

_EXPLANATION_FACTORS = ["S_host", "S_site", "S_age", "M", "T", "K_frost"]
_FACTOR_KEY_MAP = {
    "S_host": "host", "S_site": "site", "S_age": "age",
    "M": "moisture", "T": "temperature", "K_frost": "frost",
}


def enrich_with_mvp_layers(stands: gpd.GeoDataFrame, profile: dict, gdos_gdf: gpd.GeoDataFrame,
                              osm_features: dict, zakaz_checker, alpha: float | None = None,
                              top_n_for_ban_check: int = 50) -> gpd.GeoDataFrame:
    stands = stands.copy()
    alpha = profile["pressure"]["alpha_default"] if alpha is None else alpha

    gdos_blocked = mark_gdos_blocked(stands, gdos_gdf)
    stands["gdos_blocked"] = gdos_blocked
    stands["mask_full"] = stands["mask"] & ~gdos_blocked

    parking = osm_features.get("parking")
    roads = osm_features.get("roads")
    places = osm_features.get("places")
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

    stands["R_final"] = [
        compute_ranking(mask, h, f_loc, p=p, alpha=alpha)
        for mask, h, f_loc, p in zip(stands["mask_full"], stands["H"], stands["F_loc"], stands["P"])
    ]

    stands["periodic_ban_checked"] = False
    stands["periodic_ban_active"] = False
    if top_n_for_ban_check > 0 and len(stands):
        # centroids already carries stands.crs (centroid preserves it); do not
        # call set_crs on it -- set_crs raises on a GeoSeries whose crs is
        # already set unless allow_override=True. Reproject directly instead.
        centroids_4326 = centroids.to_crs("EPSG:4326")
        top_idx = stands.sort_values("R_final", ascending=False).head(top_n_for_ban_check).index
        for idx in top_idx:
            lon, lat = centroids_4326.loc[idx].x, centroids_4326.loc[idx].y
            banned = zakaz_checker(lat, lon)
            stands.loc[idx, "periodic_ban_checked"] = True
            stands.loc[idx, "periodic_ban_active"] = bool(banned)
            if banned:
                stands.loc[idx, "R_final"] = 0.0

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
                 "age": row.get("spec_age"), "P": row.get("P", 0.0)}
        explanations.append(generate_explanation(contributions, values, meta, profile))
    stands["explanation"] = explanations

    return stands
