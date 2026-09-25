import copy
import math
from itertools import combinations

import geopandas as gpd
from shapely.geometry import Point, box

import pytest

from pipeline.habitat import load_profile
from pipeline.regions import (
    select_candidates, _region_members, _summarize_cluster, group_into_regions,
)

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def _regions_profile(**overrides):
    """A copy of PROFILE with `regions` fully replaced by explicit test
    values, so each test is self-contained and does not silently change
    behaviour if the real, tuned defaults in profiles/boletus_edulis.yaml
    are retuned later."""
    profile = copy.deepcopy(PROFILE)
    profile["regions"] = {
        "top_pct": 1.0, "radius_m": 500.0, "min_area_ha": 0.5,
        "min_separation_m": 3000.0, "top_n_per_region": 5, "max_regions": 5,
        **overrides,
    }
    return profile


def _true_diameter(geom) -> float:
    """Max pairwise distance between any two points of geom, via its convex
    hull -- NOT the bounding-box diagonal, which can overestimate the real
    diameter of an L-shaped point spread (verified during plan research on
    real cache data: bbox diagonal gave false positives up to ~2690m for
    regions whose true diameter was really ~1500m)."""
    hull = geom.convex_hull
    coords = list(hull.exterior.coords) if hull.geom_type == "Polygon" else list(hull.coords)
    if len(coords) < 2:
        return 0.0
    return max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in combinations(coords, 2))


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


def test_region_members_includes_seed_itself():
    # box(380000,486000,380100,486100) has centroid (380050, 486050) and its
    # own corners ~70.7m from that centroid (100x100 box, half-diagonal) --
    # radius_m must be at least that for the box to contain itself.
    candidates = gpd.GeoDataFrame([_stand("A", r_final=50.0, x=380000)], crs="EPSG:2180")
    members = _region_members(candidates, Point(380050, 486050), radius_m=100.0)
    assert members["stand_id"].tolist() == ["A"]


def test_region_members_excludes_stand_whose_geometry_pokes_outside_radius_even_though_centroid_is_close():
    # spec §5.6 plan-2.1 research finding: a large/elongated stand can have
    # its centroid close to the seed while its own polygon extends well
    # past the intended radius. Membership must test the WHOLE geometry,
    # not just the centroid distance, or the region's true diameter breaks
    # the <=2km completion criterion (found on real BDL data during
    # planning -- stands up to ~27ha/~900m own diagonal).
    seed = box(380000, 486000, 380100, 486100)  # centroid (380050, 486050)
    # 700m wide, 50m tall strip, centroid EXACTLY equal to the seed's
    # centroid, but its corners are ~350.9m from that centroid -- outside a
    # 300m-radius buffer even though centroid distance is 0.
    elongated = box(379700, 486025, 380400, 486075)
    candidates = gpd.GeoDataFrame(
        [{"stand_id": "seed", "R_final": 50.0, "geometry": seed},
         {"stand_id": "elongated", "R_final": 50.0, "geometry": elongated}],
        crs="EPSG:2180",
    )
    members = _region_members(candidates, Point(380050, 486050), radius_m=300.0)
    assert members["stand_id"].tolist() == ["seed"]

    # The same elongated stand IS a member once the radius is generous
    # enough to actually contain it whole (distance to its farthest corner
    # is ~350.9m) -- confirms the exclusion above is about geometry, not a
    # bug that rejects everything.
    members_wide = _region_members(candidates, Point(380050, 486050), radius_m=400.0)
    assert sorted(members_wide["stand_id"].tolist()) == ["elongated", "seed"]


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


def test_summarize_cluster_stand_ids_ordered_by_r_final_then_tie_break():
    members = gpd.GeoDataFrame({
        "stand_id": ["low_tb", "high_tb", "third"],
        "R_final": [50.001, 50.004, 40.0],  # first two round to 50.00 at 2 decimals -- tied
        "tie_break": [0.2, 0.9, 0.5],
        "geometry": [box(0, 0, 10, 10), box(10, 10, 20, 20), box(20, 20, 30, 30)],
    }, crs="EPSG:2180")
    summary = _summarize_cluster(members, top_n=3)
    assert summary["stand_ids"] == ["high_tb", "low_tb", "third"]


def test_summarize_cluster_stand_ids_breaks_a_full_tie_by_stand_id():
    # Final-review finding: two members tied on BOTH rounded R_final and
    # tie_break (a common case on real data -- most stands without a BDL
    # package share the same neutral 0.5 tie_break) must still get a
    # deterministic order, not whatever the spatial index happened to
    # return them in. Arrives in descending id order to prove the sort
    # key actually does the work, not incidental input order.
    members = gpd.GeoDataFrame({
        "stand_id": ["Z", "Y", "X"],
        "R_final": [50.0, 50.0, 50.0],
        "tie_break": [0.5, 0.5, 0.5],
        "geometry": [box(0, 0, 10, 10), box(10, 10, 20, 20), box(20, 20, 30, 30)],
    }, crs="EPSG:2180")
    summary = _summarize_cluster(members, top_n=3)
    assert summary["stand_ids"] == ["X", "Y", "Z"]


def test_summarize_cluster_falls_back_to_neutral_tie_break_when_column_absent():
    # Existing callers/fixtures that don't set a "tie_break" column (most
    # of this file) must keep their current ordering, not crash.
    members = gpd.GeoDataFrame({
        "stand_id": ["A", "B"],
        "R_final": [50.0, 40.0],
        "geometry": [box(0, 0, 10, 10), box(10, 10, 20, 20)],
    }, crs="EPSG:2180")
    summary = _summarize_cluster(members, top_n=2)
    assert summary["stand_ids"] == ["A", "B"]


def test_group_into_regions_on_a_uniform_r_cluster_orders_members_by_tie_break():
    # Same dense, uniformly-excellent grid as
    # test_group_into_regions_on_a_synthetic_continuous_forest_does_not_produce_one_giant_region
    # below (all R_final tied at 90.0, so no member ordering signal comes
    # from R at all) -- with a distinct tie_break per stand added, member
    # order within the accepted region must follow it, not spatial-index
    # iteration order.
    grid_n = 31
    spacing = 200.0
    rows = []
    counter = 0
    for i in range(grid_n):
        for j in range(grid_n):
            x = 380000 + i * spacing
            y = 486000 + j * spacing
            rows.append({
                "stand_id": f"G{i}_{j}", "R_final": 90.0, "mask_full": True,
                "tie_break": (counter % 100) / 100.0,
                "geometry": box(x, y, x + 100.0, y + 100.0),
            })
            counter += 1
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")

    profile = _regions_profile(top_pct=1.0, radius_m=800.0, min_area_ha=5.0, min_separation_m=3000.0, max_regions=5)
    result = group_into_regions(stands, profile)

    assert len(result) >= 1
    tie_break_by_id = dict(zip(stands["stand_id"], stands["tie_break"]))
    for _, region in result.iterrows():
        member_tie_breaks = [tie_break_by_id[sid] for sid in region["stand_ids"]]
        assert member_tie_breaks == sorted(member_tie_breaks, reverse=True)


def test_group_into_regions_empty_when_nothing_passes_mask():
    stands = gpd.GeoDataFrame(
        [{"stand_id": "A", "R_final": 99.0, "mask_full": False,
          "geometry": box(380000, 486000, 380100, 486100)}],
        crs="EPSG:2180",
    )
    result = group_into_regions(stands, PROFILE)
    assert len(result) == 0
    assert list(result.columns) == ["region_id", "rank_score", "stand_count", "stand_ids", "geometry"]


def test_group_into_regions_rejects_seeds_below_min_area_ha():
    # Two tiny (0.25 ha) but very-high-R, well-separated candidates -- high
    # enough R to be picked first by the density-score ranking, but too
    # small to ever form a valid region on their own.
    rows = [
        {"stand_id": "tiny1", "R_final": 99.0, "mask_full": True,
         "geometry": box(380000, 486000, 380050, 486050)},
        {"stand_id": "tiny2", "R_final": 95.0, "mask_full": True,
         "geometry": box(390000, 486000, 390050, 486050)},
    ]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    profile = _regions_profile(top_pct=1.0, radius_m=200.0, min_area_ha=1.0, min_separation_m=3000.0)
    result = group_into_regions(stands, profile)
    assert len(result) == 0


def test_group_into_regions_rejects_seed_too_close_to_already_accepted_region():
    # Two single-stand candidates only 1km apart (< min_separation_m), each
    # easily large/high-R enough to qualify on its own. Only the
    # higher-scoring one should survive.
    rows = [
        _stand("better", r_final=95.0, x=380000),
        _stand("worse", r_final=90.0, x=381000),  # 1000m away, centroid-to-centroid
    ]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    profile = _regions_profile(top_pct=1.0, radius_m=100.0, min_area_ha=0.5, min_separation_m=3000.0)
    result = group_into_regions(stands, profile)
    assert len(result) == 1
    assert result.iloc[0]["stand_ids"] == ["better"]


def test_group_into_regions_caps_at_max_regions_and_sorts_by_score():
    # 30 single-stand "regions" 5km apart, R_final 1..30. top_pct=0.3 keeps
    # the top 9 (threshold ~21.3 -> R 22..30 survive) -- enough to exceed
    # max_regions=5 and exercise the cap.
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 5000) for i in range(1, 31)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    profile = _regions_profile(top_pct=0.3, radius_m=100.0, min_area_ha=0.5, min_separation_m=3000.0, max_regions=5)
    result = group_into_regions(stands, profile)
    assert len(result) == profile["regions"]["max_regions"]
    assert result["rank_score"].tolist() == sorted(result["rank_score"].tolist(), reverse=True)
    assert result["rank_score"].max() == 30.0


def test_group_into_regions_region_ids_are_sequential():
    # 10 single-stand "regions" 5km apart, R_final 1..10. top_pct=0.25's
    # threshold 7.75 leaves exactly 3 candidates (R 8, 9, 10), well under
    # max_regions=5, isolating id-sequencing from the capping behaviour
    # already covered above.
    rows = [_stand(f"S{i}", r_final=float(i), x=380000 + i * 5000) for i in range(1, 11)]
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    profile = _regions_profile(top_pct=0.25, radius_m=100.0, min_area_ha=0.5, min_separation_m=3000.0, max_regions=5)
    result = group_into_regions(stands, profile)
    assert result["region_id"].tolist() == ["region_1", "region_2", "region_3"]
    assert result["rank_score"].tolist() == [10.0, 9.0, 8.0]


def test_group_into_regions_does_not_let_a_sprawling_mediocre_cluster_beat_a_tight_excellent_one():
    # End-to-end version of the density-score-ranking behaviour: a loose
    # chain of 10 just-above-threshold stands (300m apart -- close enough
    # that old buffer-based clustering would have chain-merged them into
    # one giant cluster) must not outrank a tight pair of excellent stands,
    # because with a bounded radius each mediocre seed only ever sees its
    # immediate 1-2 neighbours (see plan research), not the whole chain.
    mediocre_rows = [_stand(f"M{i}", r_final=20.0, x=380000 + i * 300) for i in range(10)]
    excellent_rows = [_stand("E1", r_final=90.0, x=390000), _stand("E2", r_final=88.0, x=390300)]
    stands = gpd.GeoDataFrame(mediocre_rows + excellent_rows, crs="EPSG:2180")
    profile = _regions_profile(top_pct=1.0, radius_m=500.0, min_area_ha=0.5, min_separation_m=3000.0)
    result = group_into_regions(stands, profile)
    assert set(result.iloc[0]["stand_ids"]) == {"E1", "E2"}
    assert result.iloc[0]["rank_score"] == 89.0


def test_group_into_regions_on_a_synthetic_continuous_forest_does_not_produce_one_giant_region():
    # The actual bug this step fixes (spec §5.6 "Stan 2.1"): on a real 25km
    # run, one region swallowed 4747 stands over ~187 km2 because the old
    # buffer+unary_union clustering chain-merges any run of near-touching
    # candidates with no upper bound on the result's size. Simulate that
    # here with a dense, uniformly-excellent grid spanning 6km -- far
    # larger than any single region's allowed ~1.6km-diameter footprint.
    grid_n = 31
    spacing = 200.0
    rows = []
    for i in range(grid_n):
        for j in range(grid_n):
            x = 380000 + i * spacing
            y = 486000 + j * spacing
            rows.append({
                "stand_id": f"G{i}_{j}", "R_final": 90.0, "mask_full": True,
                "geometry": box(x, y, x + 100.0, y + 100.0),
            })
    stands = gpd.GeoDataFrame(rows, crs="EPSG:2180")
    total_candidates = len(rows)

    profile = _regions_profile(top_pct=1.0, radius_m=800.0, min_area_ha=5.0, min_separation_m=3000.0, max_regions=5)
    result = group_into_regions(stands, profile)

    assert 1 < len(result) <= profile["regions"]["max_regions"]
    for _, region in result.iterrows():
        assert region["stand_count"] < total_candidates
        assert _true_diameter(region["geometry"]) <= 2000.0

    # centres pairwise >= min_separation_m apart, matching the completion
    # criterion (checked on the real cached 25km dataset during planning)
    centers = [region["geometry"].centroid for _, region in result.iterrows()]
    for a, b in combinations(centers, 2):
        assert a.distance(b) >= profile["regions"]["min_separation_m"]
