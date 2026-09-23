import json
import math
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline.export import build_score_record, write_scores_json, export_stand_geometries


def _enriched_stands():
    return gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "H": [0.9, 0.5], "F": [0.6, 0.4], "F_loc": [0.6, 0.4],
        "P": [0.1, 0.2], "R_final": [48.6, 16.0],
        "mask_full": [True, False],
        "confidence": ["SREDNIA", "NISKA"],
        "confidence_reasons": [["a", "b"], ["c"]],
        "explanation": [[{"factor": "host", "contribution": 0.1, "text": "..."}], []],
    }, geometry=[box(0, 0, 1, 1), box(1, 1, 2, 2)], crs="EPSG:2180")


def _enriched_stands_with_nan_h():
    # H is None on mask-failing stands (compute_habitat's age mask returns
    # None), and a float column mixing None with floats coerces to NaN --
    # confirmed in the real Faza 2 export (322 bare "NaN" tokens, all in H,
    # for the 325 non-mask-passing stands in one tile).
    stands = _enriched_stands()
    stands.loc[1, "H"] = float("nan")
    return stands


def test_build_score_record_shape_matches_architecture_schema():
    row = _enriched_stands().iloc[0]
    record = build_score_record(row, day="2026-09-23")
    assert record["stand_id"] == "A"
    assert record["day"] == "2026-09-23"
    for key in ["H", "F", "F_loc", "P", "R", "mask", "confidence", "confidence_reasons", "explanation"]:
        assert key in record
    assert record["R"] == 48.6
    assert record["mask"] is True


def test_write_scores_json_writes_one_record_per_stand(tmp_path):
    out_path = write_scores_json(_enriched_stands(), day="2026-09-23", out_path=tmp_path / "scores_2026-09-23.json")
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert {r["stand_id"] for r in data} == {"A", "B"}


def test_build_score_record_converts_nan_to_none():
    row = _enriched_stands_with_nan_h().iloc[1]
    record = build_score_record(row, day="2026-09-23")
    assert record["H"] is None


def test_write_scores_json_produces_strict_json_with_no_bare_nan_tokens(tmp_path):
    out_path = write_scores_json(
        _enriched_stands_with_nan_h(), day="2026-09-23", out_path=tmp_path / "scores_2026-09-23.json"
    )
    raw = out_path.read_text(encoding="utf-8")
    assert "NaN" not in raw  # browsers' JSON.parse throws on a bare NaN token
    data = json.loads(raw)
    assert data[1]["H"] is None


def test_export_stand_geometries_round_trips(tmp_path):
    out_path = export_stand_geometries(_enriched_stands(), tmp_path / "stands.parquet")
    assert out_path.exists()
    reloaded = gpd.read_parquet(out_path)
    assert len(reloaded) == 2
    assert "stand_id" in reloaded.columns
    assert "geometry" in reloaded.columns
