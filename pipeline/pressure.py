import math


def nearest_distance_m(point, points_gdf) -> float | None:
    if points_gdf is None or len(points_gdf) == 0:
        return None
    return float(points_gdf.distance(point).min())


def compute_d_park(centroid, parking_gdf, roads_gdf, euclid_factor: float) -> float | None:
    d_parking = nearest_distance_m(centroid, parking_gdf)
    d_road = nearest_distance_m(centroid, roads_gdf)
    candidates = [d for d in (d_parking, d_road) if d is not None]
    if not candidates:
        return None
    return min(candidates) * euclid_factor


def compute_demand(centroid, places_gdf, decay_km: float) -> float:
    if places_gdf is None or len(places_gdf) == 0:
        return 0.0
    dists_km = places_gdf.distance(centroid) / 1000.0
    pops = places_gdf["population"].fillna(0.0).astype(float)
    return float((pops / (1 + (dists_km / decay_km) ** 2)).sum())


def compute_pressure(d_park: float | None, demand: float, demand_max: float, profile: dict) -> float:
    """P = 1 - exp(-k * Demand_norm * exp(-d_park/park_decay_m)), spec §4.5.
    d_park=None (no parking/road data at all in this tile) is treated as
    "infinitely far", which drives the park_term to 0 and P to 0 -- a
    conservative default (never overstate pressure) rather than a crash."""
    cfg = profile["pressure"]
    demand_norm = 0.0 if demand_max in (0, 0.0, None) else demand / demand_max
    effective_d_park = d_park if d_park is not None else math.inf
    park_term = math.exp(-effective_d_park / cfg["park_decay_m"])
    return 1.0 - math.exp(-cfg["k"] * demand_norm * park_term)
