import json
import math
import pathlib

import geopandas as gpd

SCORE_FIELDS = [
    "stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation",
    "distance_method", "entrance_status", "d_park_m",
    # spec §3.3: how many days of the weather window are forecast (not yet
    # observed) rather than history -- plan 2.1 step A3. Same value for
    # every stand in a run (pipeline.orchestrate.run_poc's forecast_days).
    "forecast_days",
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
