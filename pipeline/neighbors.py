import pandas as pd

from pipeline.bdl import normalize_code

# spec §5.3 pkt 3 / §0.1: adjacency is a real shared boundary length, not a
# percentage of either polygon's own perimeter -- a large wydzielenie
# touching many small neighbours along a short combined edge must not be
# treated as "mostly bordered by X" just because that edge is a big slice
# of ITS OWN perimeter. ~20m, per the task.
MIN_SHARED_BOUNDARY_M = 20.0
# spec §5.3 pkt 3: "wiekiem < 20 lat" for a neighbouring D-STAN, regardless
# of species -- distinct from the S_age/mask cultivation threshold (12
# years, pipeline.habitat) which answers a different question (legal
# access), not "young enough to look and smell different next door".
MIN_NEIGHBOR_STAND_AGE_YEARS = 20


def _shared_boundary_length(a, b) -> float:
    """Length of the boundary `a` and `b` actually share. Only counts
    LineString/MultiLineString parts of the intersection -- a Polygon or
    GeometryCollection component would mean overlapping geometry (a data
    quality issue, not a shared edge) and is deliberately not measured as
    boundary length."""
    shared = a.boundary.intersection(b.boundary)
    if shared.is_empty:
        return 0.0
    if shared.geom_type in ("LineString", "MultiLineString"):
        return shared.length
    if shared.geom_type == "GeometryCollection":
        return sum(g.length for g in shared.geoms if g.geom_type in ("LineString", "MultiLineString"))
    return 0.0


def find_neighbor_labels(target_row, context_stands, dictionaries: dict) -> list[str]:
    """Readable "graniczy z" labels for one wydzielenie (plan 2.1 step B3,
    spec §5.3 pkt 3) -- informational only, never fed into H/R (see
    pipeline.bdl_package_details' module docstring for the same structural
    guarantee).

    `context_stands` must be the full per-tile BDL fetch (not a
    within_radius-trimmed subset), the same frame pipeline.entrances.
    compute_forest_boundary already uses, so the search radius's own edge
    doesn't manufacture fake neighbours. `dictionaries` is
    pipeline.bdl_dictionaries.load_dictionaries' output (or {} -- falls
    back to raw codes, never raises).

    A neighbour qualifies if the shared boundary (see
    _shared_boundary_length, NOT a percentage of either polygon's
    perimeter) is >= MIN_SHARED_BOUNDARY_M, and either its `area_type` is
    not D-STAN, or it's a D-STAN with a different dominant species_cd or
    age < MIN_NEIGHBOR_STAND_AGE_YEARS. Deduplicated and sorted for a
    stable, testable order."""
    target_geom = target_row.geometry
    target_adr_for = target_row.get("adr_for")
    target_species = normalize_code(target_row.get("species_cd"))

    area_type_names = dictionaries.get("area_type", {})
    species_names = dictionaries.get("tree_species", {})

    # Buffered only to widen the spatial-index prefilter's bounding-box net
    # (catches candidates whose bbox just misses touching); the exact
    # shared-boundary length check below always uses the real geometry.
    candidate_idx = context_stands.sindex.query(target_geom.buffer(1.0), predicate="intersects")

    labels = set()
    for i in candidate_idx:
        other = context_stands.iloc[i]
        if other.get("adr_for") == target_adr_for:
            continue
        other_geom = other.geometry
        if other_geom.equals(target_geom):
            continue
        if _shared_boundary_length(target_geom, other_geom) < MIN_SHARED_BOUNDARY_M:
            continue

        other_area_type = normalize_code(other.get("area_type"))
        if other_area_type != "D-STAN":
            labels.add(area_type_names.get(other_area_type, other_area_type))
            continue

        other_species = normalize_code(other.get("species_cd"))
        species_name = species_names.get(other_species, other_species)
        other_age = other.get("spec_age")
        is_young = other_age is not None and not pd.isna(other_age) and other_age < MIN_NEIGHBOR_STAND_AGE_YEARS
        if is_young:
            labels.add(f"młodnik {species_name} ({int(other_age)} lat)")
        elif other_species != target_species:
            labels.add(f"drzewostan {species_name}")
        # same species, not young: not a distinguishing neighbour -- omitted.

    return sorted(labels)
