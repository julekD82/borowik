import json
import math
import pathlib

import geopandas as gpd

from pipeline.tie_break import veg_cover_label

SCORE_FIELDS = [
    "stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation",
    "distance_method", "entrance_status", "d_park_m",
    # spec §3.3: how many days of the weather window are forecast (not yet
    # observed) rather than history -- plan 2.1 step A3. Same value for
    # every stand in a run (pipeline.orchestrate.run_poc's forecast_days).
    "forecast_days",
    # Plan 2.1 "Zmiana 1": seasonal fruiting-frequency multiplier for this
    # run's target_date (pipeline.phenology.compute_g_season) -- same value
    # for every stand in one export.
    "G_season",
    # plan 2.1 step B2: whether this stand's S_host came from a real BDL
    # package's full species composition ("paczka") or the WFS
    # panujący+part_cd fallback ("wfs"), plus that package's own
    # generation date (metadane.txt) when applicable -- null for "wfs".
    "s_host_source", "s_host_package_date",
    # Plan 2.1 "Zmiana 4": ground-cover/density ordinal secondary sort key
    # (pipeline.tie_break) -- presentation-only, see that module's docstring.
    "tie_break",
    # Plan 2026-09-26 A1: exp-weighted share of the P26w window whose rain
    # came from the IMGW radar (pipeline.radar), 0 = Open-Meteo only.
    "rain_radar_coverage",
]


def _json_safe(value):
    """NaN (e.g. H=None on a mask-failing stand, coerced to NaN once the
    column holds floats) has no JSON representation; json.dumps emits it as
    a bare `NaN` token by default, which is invalid JSON and throws in a
    browser's JSON.parse -- the stated consumer (spec §6.1). Convert to
    None/null instead."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def build_score_record(row, day: str) -> dict:
    """Matches the architecture diagram's scores_YYYY-MM-DD.json shape (spec
    §6.1: "id -> H, F, P, R, conf, wyjaśnienie") and the score_daily table
    columns (spec §6.2)."""
    record = {field: _json_safe(row[field]) for field in SCORE_FIELDS}
    record["day"] = day
    record["R"] = _json_safe(float(row["R_final"]))
    record["mask"] = bool(row["mask_full"])
    # Plan 2.1 step A4 (spec §5.2): from the EPSG:2180 geometry itself (same
    # source pipeline.regions.py already uses for its own area_ha), not
    # BDL's own sub_area attribute -- unused elsewhere, possibly stale.
    # Frontend-only presentation filter (hide sub-0.5ha stands as standalone
    # targets); not a mask, so every stand still gets a real value here.
    record["area_ha"] = _json_safe(float(row["geometry"].area / 10000.0))
    return record


def write_scores_json(stands: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [build_score_record(row, day) for _, row in stands.iterrows()]
    # allow_nan=False: fail loudly if some other field ever smuggles a NaN
    # past _json_safe, instead of silently writing invalid JSON again.
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


def export_stand_geometries(stands: gpd.GeoDataFrame, out_path) -> pathlib.Path:
    """Minimal id+geometry export -- the input the eventual tippecanoe/PMTiles
    packaging step (spec §9 step 11/12, out of scope for this plan, see
    Global Constraints) will consume once the frontend exists to read it."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stands[["stand_id", "geometry"]].to_parquet(out_path)
    return out_path


def export_stand_geometries_geojson(stands: gpd.GeoDataFrame, out_path) -> pathlib.Path:
    """Export minimal stand polygons in WGS84 for the static MapLibre UI."""
    if stands.crs is None:
        raise ValueError("Stand geometries require a source CRS")
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    geographic = stands[["stand_id", "geometry"]].to_crs("EPSG:4326")
    out_path.write_text(geographic.to_json(drop_id=True, na="null"), encoding="utf-8")
    return out_path


REGION_FIELDS = ["region_id", "rank_score", "stand_count", "stand_ids"]


def build_region_record(row, day: str) -> dict:
    """Matches spec §7.2's regions_{date}.json: the rejony list that becomes
    the application's main output, alongside the existing scores_{date}.json
    detail view."""
    record = {field: _json_safe(row[field]) for field in REGION_FIELDS}
    record["region_id"] = str(record["region_id"])
    record["rank_score"] = _json_safe(float(row["rank_score"]))
    record["stand_count"] = int(row["stand_count"])
    record["stand_ids"] = list(row["stand_ids"])
    record["day"] = day
    return record


def _share_label(part_cd: str, dictionaries: dict) -> str:
    return dictionaries.get("part", {}).get(part_cd, part_cd)


def _species_entries(species: list[tuple[str, str]], dictionaries: dict) -> list[dict]:
    tree_names = dictionaries.get("tree_species", {})
    return [
        {
            "species_cd": species_cd,
            "name": tree_names.get(species_cd, species_cd),
            "share": _share_label(part_cd, dictionaries),
        }
        for species_cd, part_cd in species
    ]


def build_details_record(stand_id: str, adr_for: str, stand_stru, prot_categ, day: str,
                           package_details_index: dict, neighbors_by_stand: dict, dictionaries: dict,
                           tie_break_index: dict) -> dict:
    """One card's worth of plan 2.1 step B3 detail (spec §5.3 pkt 3):
    species composition, density, understory, soil type -- from a BDL
    package when `adr_for` is covered by one (fields null/empty
    otherwise) -- plus neighbours and stand_stru/prot_categ, which come
    from WFS and are present regardless of package coverage. Purely
    additive: never touches H/F/R (see pipeline.bdl_package_details'
    module docstring for why that's structurally guaranteed, not just
    tested).

    Since plan 2.1 "Zmiana 4": also ground cover (word form) and the
    stand density index -- from pipeline.tie_break, empty/null when
    `adr_for` isn't covered by any package. Purely additive presentation
    fields: never touches H/F/R (see pipeline.tie_break's own module
    docstring)."""
    details = package_details_index.get(adr_for)
    prot_categ_name = None
    if prot_categ is not None and not (isinstance(prot_categ, float) and math.isnan(prot_categ)):
        prot_categ_name = dictionaries.get("prot_categ", {}).get(prot_categ, prot_categ)
    tie_break_raw = tie_break_index.get(adr_for)
    return {
        "stand_id": stand_id,
        "day": day,
        "drzew_species": _species_entries(details.drzew_species, dictionaries) if details else [],
        "density": (
            dictionaries.get("density", {}).get(details.density_cd, details.density_cd)
            if details and details.density_cd else None
        ),
        "podszyt_species": _species_entries(details.podszyt_species, dictionaries) if details else [],
        "soil_type": (
            dictionaries.get("soil_subtype", {}).get(details.soil_subtype_cd, details.soil_subtype_cd)
            if details and details.soil_subtype_cd else None
        ),
        "package_date": details.package_date if details else None,
        "neighbors": neighbors_by_stand.get(adr_for, []),
        "stand_stru": _json_safe(stand_stru),  # no BDL dictionary exists for this field (verified B3 research)
        "prot_categ": prot_categ_name,
        "veg_cover": veg_cover_label(tie_break_raw.veg_cover_cd) if tie_break_raw else None,
        "standdensity_index": _json_safe(tie_break_raw.standdensity_index) if tie_break_raw else None,
    }


def write_details_json(stands: gpd.GeoDataFrame, package_details_index: dict, neighbors_by_stand: dict,
                         dictionaries: dict, day: str, out_path, tie_break_index: dict) -> pathlib.Path:
    """Plan 2.1 step B3: card-detail data (species composition, density,
    understory, soil type, neighbours, stand_stru/prot_categ) for every
    wydzielenie in `stands`, kept in its own file rather than
    scores_{day}.json -- adding this per stand there would have grown a
    real Będziemyśl export (6.6MB/4703 records) by an estimated 35-55%,
    even though a card's detail is opened for a handful of wydzielenia,
    while the "Wydzielenia" list (scores.json) is read on every load.
    Optional on the frontend, same pattern as regions_{day}.json: a
    missing details file just means no B3 section on the card, not an
    error.

    `tie_break_index` (plan 2.1 "Zmiana 4"):
    pipeline.tie_break.load_tie_break_raw's adr_for -> raw output, used
    only to render veg_cover/standdensity_index on the card
    (build_details_record) -- the numeric tie_break sort value itself
    lives in scores_{day}.json, not here."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        build_details_record(
            row["stand_id"], row["adr_for"], row.get("stand_stru"), row.get("prot_categ"),
            day, package_details_index, neighbors_by_stand, dictionaries, tie_break_index,
        )
        for _, row in stands.iterrows()
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


def write_regions_json(regions: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Centroid computed in the regions' own (projected, metric) CRS and only
    # then reprojected to WGS84 -- computing a centroid directly in a
    # geographic CRS is inaccurate and triggers a geopandas UserWarning.
    # Without a location, a consumer of this file (map, navigation link)
    # cannot place a region at all (final review finding).
    centroids_4326 = regions.geometry.centroid.to_crs("EPSG:4326")
    records = []
    for (_, row), point in zip(regions.iterrows(), centroids_4326):
        record = build_region_record(row, day)
        record["centroid_lat"] = point.y
        record["centroid_lon"] = point.x
        records.append(record)
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


def write_conditions_json(timeline: dict, day: str, out_path) -> pathlib.Path:
    """Plan A2 Plan-B: area conditions timeline
    (pipeline.conditions_timeline.build_conditions_timeline), optional on
    the frontend like regions/details."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"day": day, **timeline}, ensure_ascii=False, indent=2, allow_nan=False),
                        encoding="utf-8")
    return out_path


# Plan wdrozenia 1.1: one run_manifest_YYYY-MM-DD.json per run_trip_preparation
# call, alongside the other exports. pipeline.prepare_trip.build_manifest
# assembles the dict from values already computed during the run (git state,
# profile hash, orchestrate.py's scored.attrs["diagnostics"], tile/entrance/
# zakaz counters) -- this function only serializes it, same pattern as the
# other write_*_json helpers above.
def write_manifest_json(manifest: dict, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False),
                        encoding="utf-8")
    return out_path
