import geopandas as gpd
from shapely.geometry import box

from pipeline.regions import select_candidates, _assign_clusters


def _stand(stand_id, r_final, mask_full=True, x=380000):
    return {
        "stand_id": stand_id, "R_final": r_final, "mask_full": mask_full,
        "geometry": box(x, 486000, x + 100, 486100),
    }


def test_select_candidates_keeps_only_top_fraction_of_mask_passing_stands():
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 1000) for i in range(1, 11)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = select_candidates(stands, top_pct=0.2)
    # top 20% of 10 stands by R_final (1..10) -> R_final >= 9.0 -> stands 9 and 10
    assert sorted(result["stand_id"].tolist()) == ["S10", "S9"]


def test_select_candidates_ignores_mask_failing_stands_even_with_high_r():
    rows = [
        _stand("low_pass", r_final=5.0, mask_full=True, x=380000),
        _stand("high_fail", r_final=99.0, mask_full=False, x=381000),
    ]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = select_candidates(stands, top_pct=1.0)
    assert result["stand_id"].tolist() == ["low_pass"]


def test_select_candidates_returns_empty_frame_when_nothing_passes_mask():
    rows = [_stand("only", r_final=50.0, mask_full=False)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = select_candidates(stands, top_pct=0.25)
    assert len(result) == 0


def test_assign_clusters_merges_stands_separated_by_a_gap_within_buffer():
    rows = [
        _stand("A", r_final=50.0, x=380000),  # box 380000-380100
        _stand("B", r_final=60.0, x=380300),  # box 380300-380400, 200 m gap from A
    ]
    candidates = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    clusters = _assign_clusters(candidates, buffer_m=250.0)
    assert len(clusters) == 1
    assert sorted(clusters[0]["stand_id"].tolist()) == ["A", "B"]


def test_assign_clusters_keeps_gap_larger_than_buffer_separate():
    rows = [
        _stand("A", r_final=50.0, x=380000),  # box 380000-380100
        _stand("B", r_final=60.0, x=381000),  # box 381000-381100, 900 m gap from A
    ]
    candidates = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    clusters = _assign_clusters(candidates, buffer_m=250.0)
    assert len(clusters) == 2
    ids = sorted(c["stand_id"].iloc[0] for c in clusters)
    assert ids == ["A", "B"]


def test_assign_clusters_returns_empty_list_for_empty_input():
    empty = gpd.GeoDataFrame({"stand_id": [], "R_final": []}, geometry=[], crs="EPSG:2180")
    assert _assign_clusters(empty, buffer_m=250.0) == []
