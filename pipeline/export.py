import json
import math
import pathlib

import geopandas as gpd

SCORE_FIELDS = ["stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation"]


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
