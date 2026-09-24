import geopandas as gpd
from shapely.geometry import box

import pytest

from pipeline.habitat import load_profile
from pipeline.regions import (
    select_candidates, _assign_clusters, _summarize_cluster, group_into_regions,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


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


def test_summarize_cluster_uses_median_of_top_n_not_sum():
    # A large cluster of many just-above-threshold stands must not outrank
    # a small cluster of a few excellent ones purely by being numerous --
    # spec §5.6 step 3, the whole reason this function exists.
    many_mediocre = gpd.GeoDataFrame(
        [_stand(f"M{i}", r_final=20.0, x=380000 + i * 300) for i in range(10)],
        crs="EPSG:2180",
    )
    few_excellent = gpd.GeoDataFrame(
        [_stand("E1", r_final=90.0, x=390000), _stand("E2", r_final=88.0, x=390300)],
        crs="EPSG:2180",
    )
    mediocre_summary = _summarize_cluster(many_mediocre, top_n=5)
    excellent_summary = _summarize_cluster(few_excellent, top_n=5)
    assert excellent_summary["rank_score"] > mediocre_summary["rank_score"]
    assert mediocre_summary["rank_score"] == 20.0
    assert excellent_summary["rank_score"] == 89.0  # median of [90, 88], top_n=5 > available 2


def test_summarize_cluster_geometry_is_union_of_member_geometries_not_buffered():
    members = gpd.GeoDataFrame(
        [_stand("A", r_final=50.0, x=380000), _stand("B", r_final=60.0, x=380100)],
        crs="EPSG:2180",
    )
    summary = _summarize_cluster(members, top_n=5)
    # two touching 100x100 boxes -> exact union area, not inflated by any buffer
    assert summary["geometry"].area == pytest.approx(2 * 100 * 100)


def test_summarize_cluster_stand_ids_and_count():
    members = gpd.GeoDataFrame(
        [_stand("A", r_final=50.0, x=380000), _stand("B", r_final=60.0, x=380100)],
        crs="EPSG:2180",
    )
    summary = _summarize_cluster(members, top_n=5)
    assert summary["stand_count"] == 2
    assert sorted(summary["stand_ids"]) == ["A", "B"]


def test_group_into_regions_empty_when_nothing_passes_mask():
    stands = gpd.GeoDataFrame(
        [{"stand_id": "A", "R_final": 99.0, "mask_full": False,
          "geometry": box(380000, 486000, 380100, 486100)}],
        crs="EPSG:2180",
    )
    result = group_into_regions(stands, PROFILE)
    assert len(result) == 0
    assert list(result.columns) == ["region_id", "rank_score", "stand_count", "stand_ids", "geometry"]


def test_group_into_regions_caps_at_max_regions_and_sorts_by_score():
    # 30 single-stand clusters (each 5 km apart, far beyond buffer_m) with
    # R_final 1..30. select_candidates' default top_pct=0.25 keeps only the
    # top 8 of these (verified: threshold 22.75 -> R 23..30 survive), so
    # max_regions=5 (profile default) still has 3 to drop -- this actually
    # exercises the cap, unlike a smaller spread where top_pct alone would
    # already leave <=5 candidates.
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 5000) for i in range(1, 31)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = group_into_regions(stands, PROFILE)
    assert len(result) == PROFILE["regions"]["max_regions"]
    assert result["rank_score"].tolist() == sorted(result["rank_score"].tolist(), reverse=True)
    assert result["rank_score"].max() == 30.0


def test_group_into_regions_region_ids_are_sequential():
    # 10 single-stand clusters, R_final 1..10. top_pct=0.25's threshold 7.75
    # leaves exactly 3 candidates (R 8, 9, 10), each far enough apart (5 km)
    # to stay separate clusters -- under max_regions=5 so nothing is capped,
    # isolating the id-sequencing behaviour from the capping behaviour
    # already covered above.
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 5000) for i in range(1, 11)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    result = group_into_regions(stands, PROFILE)
    assert result["region_id"].tolist() == ["region_1", "region_2", "region_3"]


def test_group_into_regions_does_not_let_a_sprawling_mediocre_cluster_beat_a_tight_excellent_one():
    # End-to-end version of the Task 3 unit test, through the public API.
    mediocre_rows = [_stand(f"M{i}", r_final=20.0, x=380000 + i * 300) for i in range(10)]
    excellent_rows = [_stand("E1", r_final=90.0, x=390000), _stand("E2", r_final=88.0, x=390300)]
    stands = gpd.GeoDataFrame(mediocre_rows + excellent_rows, crs="EPSG:2180")
    result = group_into_regions(stands, PROFILE)
    assert set(result.iloc[0]["stand_ids"]) == {"E1", "E2"}
    assert result.iloc[0]["rank_score"] == 89.0
