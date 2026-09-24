import json

import geopandas as gpd
import pytest
from shapely.geometry import box

from pipeline.export import export_stand_geometries_geojson, build_score_record
from test_export import _enriched_stands


def test_geojson_reprojects_real_polish_coordinates_and_preserves_id(tmp_path):
    stands = gpd.GeoDataFrame({"stand_id": ["polish stand@2026"], "secret": [1]},
                              geometry=[box(380000, 486000, 380300, 486100)], crs=2180)
    path = export_stand_geometries_geojson(stands, tmp_path / "nested" / "stands.geojson")
    data = json.loads(path.read_text(encoding="utf-8"))
    feature = data["features"][0]
    assert feature["properties"] == {"stand_id": "polish stand@2026"}
    lon, lat = feature["geometry"]["coordinates"][0][0]
    assert 14 < lon < 24 and 49 < lat < 55
    assert stands.crs.to_epsg() == 2180


def test_geojson_empty_collection_and_unknown_crs(tmp_path):
    empty = gpd.GeoDataFrame({"stand_id": []}, geometry=[], crs=2180)
    path = export_stand_geometries_geojson(empty, tmp_path / "empty.geojson")
    assert json.loads(path.read_text())["features"] == []
    with pytest.raises(ValueError, match="CRS"):
        export_stand_geometries_geojson(empty.set_crs(None, allow_override=True), path)


def test_distance_export_preserves_value_and_missing_is_null():
    stands = _enriched_stands()
    assert build_score_record(stands.iloc[0], "2026-09-24")["d_park_m"] == 1234.5
    assert build_score_record(stands.iloc[1], "2026-09-24")["d_park_m"] is None
