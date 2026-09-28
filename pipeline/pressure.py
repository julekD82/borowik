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


def demand_norm_local(demand: float, demand_max: float) -> float:
    """Pre-1.5 normalization: Demand relative to the single busiest spot IN
    THIS ANALYSIS. Makes the loneliest spot in the search radius look as
    "pressured" as the edge of a city if that radius happens to contain
    nothing busier -- and makes two separate searches' P values
    incomparable, since each has its own max (spec §4.1's own critique).
    Kept as `pressure.normalization: local` for comparison; no longer the
    default after plan 1.5."""
    return 0.0 if demand_max in (0, 0.0, None) else demand / demand_max


def demand_norm_absolute(demand: float, d_half: float) -> float:
    """Plan 1.5 default: Demand relative to a fixed profile constant
    (`pressure.d_half`) instead of this run's own maximum -- comparable
    across different searches, and a genuinely empty area now normalizes
    near 0 instead of near 1 just because nothing busier was in range."""
    total = demand + d_half
    return 0.0 if total <= 0 else demand / total


def compute_demand_norm(demand: float, demand_max: float, profile: dict) -> float:
    cfg = profile["pressure"]
    if cfg.get("normalization", "absolute") == "local":
        return demand_norm_local(demand, demand_max)
    return demand_norm_absolute(demand, cfg["d_half"])


def compute_pressure(d_park: float | None, demand: float, demand_max: float, profile: dict) -> float:
    """P = 1 - exp(-k * Demand_norm * exp(-d_park/park_decay_m)), spec §4.5.
    Demand_norm's own source is compute_demand_norm (plan 1.5: absolute by
    default, local opt-in via profile["pressure"]["normalization"]).
    d_park=None (no parking/road data at all in this tile) is treated as
    "infinitely far", which drives the park_term to 0 and P to 0 -- a
    conservative default (never overstate pressure) rather than a crash."""
    cfg = profile["pressure"]
    demand_norm = compute_demand_norm(demand, demand_max, profile)
    effective_d_park = d_park if d_park is not None else math.inf
    park_term = math.exp(-effective_d_park / cfg["park_decay_m"])
    return 1.0 - math.exp(-cfg["k"] * demand_norm * park_term)
