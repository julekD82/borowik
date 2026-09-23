import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.validate import rank_known_points, load_known_points


def _synthetic_stands():
    # five 1x1 degree squares side by side, R increasing left to right
    polys = [box(i, 50.0, i + 1, 51.0) for i in range(5)]
    return gpd.GeoDataFrame({
        "stand_id": ["s1", "s2", "s3", "s4", "s5"],
        "R": [10.0, 20.0, 30.0, 40.0, 50.0],
        "geometry": polys,
    }, crs="EPSG:4326")


def test_rank_known_points_matches_containing_stand_and_percentile():
    stands = _synthetic_stands()
    known = [
        {"name": "Znane dobre miejsce", "label": "good", "lat": 50.5, "lon": 3.5},  # inside s4, R=40
        {"name": "Znane puste miejsce", "label": "bad", "lat": 50.5, "lon": 0.5},   # inside s1, R=10
    ]

    result = rank_known_points(stands, known)

    good = result[result["name"] == "Znane dobre miejsce"].iloc[0]
    assert good["stand_id"] == "s4"
    assert good["R"] == pytest.approx(40.0)
    assert good["rank_pct"] == pytest.approx(60.0)  # 3 of 5 stands have R<40

    bad = result[result["name"] == "Znane puste miejsce"].iloc[0]
    assert bad["stand_id"] == "s1"
    assert bad["rank_pct"] == pytest.approx(0.0)


def test_load_known_points_reads_yaml(tmp_path):
    p = tmp_path / "known_points.yaml"
    p.write_text(
        "- name: Test spot\n  label: good\n  lat: 50.5\n  lon: 18.6\n",
        encoding="utf-8",
    )
    points = load_known_points(str(p))
    assert points == [{"name": "Test spot", "label": "good", "lat": 50.5, "lon": 18.6}]
