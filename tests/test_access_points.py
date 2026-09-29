import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, box

from pipeline.access_points import (
    apply_overrides, build_access_set, build_entrances, build_fallback_points,
    build_parkings, build_settlements, classify_road_access, classify_surface,
    dedupe_points, forest_zone, prepare_osm_roads,
)
from pipeline.habitat import load_profile

CFG = load_profile("profiles/boletus_edulis.yaml")["pressure"]["access_points"]
CRS = "EPSG:2180"

# Las 2 x 2 km: E 1000..3000, N 1000..3000 (EPSG:2180, metry). Droga publiczna
# biegnie z zachodu na wschod przez srodek (y = 2000).
FOREST = box(1000, 1000, 3000, 3000)


def _roads(rows):
    """rows: (geom, highway, extra-tags dict)"""
    return gpd.GeoDataFrame(
        [{"osm_id": i, "highway": h, "geometry": g, **tags} for i, (g, h, tags) in enumerate(rows)],
        geometry="geometry", crs=CRS,
    )


def _points(geoms, **cols):
    return gpd.GeoDataFrame({"osm_id": list(range(len(geoms))), **cols}, geometry=geoms, crs=CRS)


# --- klasyfikacja -------------------------------------------------------------

def test_surface_from_tag_then_tracktype_then_unknown():
    osm = CFG["osm"]
    assert classify_surface("asphalt", None, osm) == "hard"
    assert classify_surface("gravel", "grade5", osm) == "gravel"  # tag wygrywa z tracktype
    assert classify_surface("compacted", None, osm) == "compacted"
    assert classify_surface("sand", None, osm) == "dirt"
    assert classify_surface(None, "grade1", osm) == "hard"
    assert classify_surface(None, "grade2", osm) == "gravel"
    assert classify_surface(None, "grade4", osm) == "dirt"
    assert classify_surface(None, None, osm) == "unknown"
    assert classify_surface("unpaved", None, osm) == "unknown"


def test_public_vs_closed_forest_road():
    osm = CFG["osm"]
    assert classify_road_access("tertiary", None, None, osm) == "public"
    assert classify_road_access("unclassified", "yes", None, osm) == "public"
    # asfalt/unclassified z ograniczeniem to zamknieta droga lesna, nie dojazd autem
    assert classify_road_access("unclassified", "forestry", None, osm) == "closed"
    assert classify_road_access("tertiary", None, "no", osm) == "closed"
    assert classify_road_access("track", None, None, osm) == "closed"
    assert classify_road_access("service", None, None, osm) == "closed"


def test_prepare_osm_roads_marks_paved_and_kind():
    roads = _roads([
        (LineString([(0, 0), (10, 0)]), "tertiary", {"surface": None, "tracktype": None, "access": None, "motor_vehicle": None}),
        (LineString([(0, 5), (10, 5)]), "track", {"surface": "asphalt", "tracktype": None, "access": None, "motor_vehicle": None}),
        (LineString([(0, 9), (10, 9)]), "unclassified", {"surface": "gravel", "tracktype": None, "access": None, "motor_vehicle": None}),
    ])
    out = prepare_osm_roads(roads, CFG)
    assert out["kind"].tolist() == ["public", "closed", "public"]
    assert out["surface_class"].tolist() == ["unknown", "hard", "gravel"]
    # tertiary bez tagu nawierzchni liczy sie jako asfalt (domyslnie), gravel-unclassified nie
    assert out["paved"].tolist() == [True, True, False]


# --- deduplikacja --------------------------------------------------------------

def test_dedupe_points_keeps_highest_priority_within_radius():
    xy = np.array([[0.0, 0.0], [50.0, 0.0], [500.0, 0.0]])
    kept = dedupe_points(xy, np.array([1, 0, 0]), 100.0)
    assert kept.tolist() == [1, 2]  # punkt 1 (priorytet 0) wygrywa z 0; punkt 2 daleko


def test_dedupe_points_is_strict_radius():
    xy = np.array([[0.0, 0.0], [100.0, 0.0]])
    assert len(dedupe_points(xy, np.zeros(2), 100.0)) == 2  # dokladnie promien: rozne punkty


# --- parkingi --------------------------------------------------------------------

def test_parkings_bdl_wins_dedupe_and_osm_only_near_forest():
    zone = forest_zone(FOREST, 200.0)
    bdl = gpd.GeoDataFrame({"source_id": ["7"], "subtype": ["parking_lesny"], "name": ["Lesny"]},
                            geometry=[Point(2000, 2000)], crs=CRS)
    osm = _points([Point(2050, 2000),      # 50 m od BDL -> zduplikowany
                   Point(2000, 3150),      # 150 m od lasu -> zostaje
                   Point(2000, 3400),      # 400 m od lasu -> odpada
                   ], amenity=["parking"] * 3)
    out = build_parkings(bdl, osm, zone, CFG)
    assert sorted(out["source"]) == ["bdl", "osm"]
    assert out.loc[out["source"] == "osm"].geometry.iloc[0].equals(Point(2000, 3150))
    assert out["type"].eq("parking").all()


def test_parkings_empty_inputs():
    assert len(build_parkings(None, None, forest_zone(FOREST, 200), CFG)) == 0


# --- wjazdy ------------------------------------------------------------------------

def _prep(rows):
    roads = _roads([(g, h, {"surface": None, "tracktype": None, "access": a, "motor_vehicle": None})
                    for g, h, a in rows])
    return prepare_osm_roads(roads, CFG)


def _entrances(public_rows, forest_rows, gates=None, fire=None):
    prepared = _prep(public_rows + forest_rows)
    public = prepared[prepared["kind"] == "public"]
    forest = prepared[prepared["kind"] == "closed"]
    if fire is not None:
        forest = pd.concat([forest, fire], ignore_index=True)
    zone = forest_zone(FOREST, CFG["forest_buffer_m"])
    return build_entrances(FOREST, zone, public, forest, gates, CFG)


def test_entrance_public_road_crossing_kept_only_with_track_continuation():
    # droga publiczna N-S przecina granice lasu w (2000, 1000); dukt zaczyna sie
    # 30 m od przeciecia -> kontynuacja w lesie
    road = LineString([(2000, 500), (2000, 1500)])
    duct = LineString([(2030, 1005), (2500, 1300)])
    with_duct = _entrances([(road, "tertiary", None)], [(duct, "track", None)])
    assert (with_duct["type"] == "entrance").any()
    # bez duktu -- asfalt tylko mija las, brak wjazdu
    without = _entrances([(road, "tertiary", None)], [])
    assert len(without) == 0


def test_entrance_track_crossing_needs_public_road_nearby():
    track = LineString([(1000 - 200, 2500), (1500, 2500)])   # przecina granice w (1000, 2500)
    near_road = LineString([(700, 2200), (700, 2800)])        # ~300 m od przeciecia
    far_road = LineString([(200, 2200), (200, 2800)])         # 800 m
    near = _entrances([(near_road, "tertiary", None)], [(track, "track", None)])
    far = _entrances([(far_road, "tertiary", None)], [(track, "track", None)])
    assert len(near) >= 1 and (near["subtype"] == "crossing_track").any()
    assert len(far) == 0


def test_entrance_forest_asphalt_with_access_forestry_is_not_public_source():
    # zamknieta (forestry) droga asfaltowa nie jest zrodlem wjazdow dla aut
    closed_asphalt = LineString([(2000, 500), (2000, 1500)])
    duct = LineString([(2030, 1005), (2500, 1300)])
    out = _entrances([(closed_asphalt, "unclassified", "forestry")], [(duct, "track", None)])
    assert not (out["subtype"] == "crossing_public").any()


def test_gate_on_forest_road_near_public_road_and_priority_over_entrance():
    road = LineString([(2000, 500), (2000, 1500)])
    duct = LineString([(2010, 1010), (2500, 1010)])
    gate_near = gpd.GeoDataFrame({"osm_id": [1], "barrier": ["gate"], "access": [None]},
                                 geometry=[Point(2050, 1010)], crs=CRS)  # na dukcie, ~50 m od drogi
    out = _entrances([(road, "tertiary", None)], [(duct, "track", None)], gates=gate_near)
    assert (out["type"] == "gate").sum() == 1
    # wjazd w odleglosci < 150 m od szlabanu zostaje zdeduplikowany (szlaban wygrywa)
    assert (out["type"] == "entrance").sum() == 0


def test_gate_far_from_public_road_or_off_road_is_dropped():
    road = LineString([(2000, 500), (2000, 1500)])
    duct = LineString([(2010, 1010), (2900, 1010)])
    far_gate = gpd.GeoDataFrame({"osm_id": [1], "barrier": ["gate"], "access": [None]},
                                geometry=[Point(2800, 1010)], crs=CRS)    # 800 m od drogi publicznej
    off_road = gpd.GeoDataFrame({"osm_id": [2], "barrier": ["gate"], "access": [None]},
                                geometry=[Point(2050, 1200)], crs=CRS)     # 190 m od duktu
    assert not (_entrances([(road, "tertiary", None)], [(duct, "track", None)], gates=far_gate)["type"] == "gate").any()
    assert not (_entrances([(road, "tertiary", None)], [(duct, "track", None)], gates=off_road)["type"] == "gate").any()


def test_fire_road_counts_as_forest_continuation():
    road = LineString([(2000, 500), (2000, 1500)])
    fire = gpd.GeoDataFrame({"kind": ["fire"], "surface_class": ["unknown"], "source": ["bdl_ppoz"],
                             "fire_no": ["12"], "highway": [""], "paved": [False]},
                            geometry=[LineString([(2020, 1010), (2400, 1300)])], crs=CRS)
    out = _entrances([(road, "tertiary", None)], [], fire=fire)
    assert (out["subtype"] == "crossing_public").any()


# --- fallback ----------------------------------------------------------------------

def test_fallback_used_only_for_tiles_without_entrances():
    road = LineString([(500, 2000), (3500, 2000)])
    paved = _prep([(road, "tertiary", None)])
    empty = gpd.GeoDataFrame({"type": []}, geometry=[], crs=CRS)
    tile = (0, 0, 10000, 10000)   # N,E,N,E -- caly las w kaflu, ~4 km2
    points, n_tiles = build_fallback_points(FOREST, paved, empty, [tile], CFG)
    assert n_tiles == 1 and len(points) > 0 and (points["type"] == "road_fallback").all()
    # kafel z wjazdem: bez fallbacku
    with_entrance = gpd.GeoDataFrame({"type": ["entrance"]}, geometry=[Point(2000, 1000)], crs=CRS)
    points2, n2 = build_fallback_points(FOREST, paved, with_entrance, [tile], CFG)
    assert n2 == 0 and len(points2) == 0


def test_fallback_skips_tile_with_almost_no_forest():
    road = LineString([(500, 2000), (3500, 2000)])
    paved = _prep([(road, "tertiary", None)])
    empty = gpd.GeoDataFrame({"type": []}, geometry=[], crs=CRS)
    tiny_tile = (1000, 1000, 1500, 1500)  # 0.25 km2 lasu
    _, n = build_fallback_points(FOREST, paved, empty, [tiny_tile], CFG)
    assert n == 0


# --- osiedla -----------------------------------------------------------------------

def test_settlements_only_cells_touching_forest_zone_with_population():
    pop = gpd.GeoDataFrame({"population": [300.0, 0.0, 120.0]},
                           geometry=[Point(500, 2000),     # kwadrat 0..1000 sasiaduje z lasem
                                     Point(500, 2100),     # ludnosc 0
                                     Point(9000, 9000)],   # daleko
                           crs=CRS)
    out = build_settlements(pop, forest_zone(FOREST, 200.0), CFG)
    assert len(out) == 1 and out["weight_pop"].iloc[0] == 300.0 and out["type"].iloc[0] == "settlement"


# --- korekty wlasciciela -------------------------------------------------------------

def test_overrides_drop_and_add():
    pts = gpd.GeoDataFrame({"point_id": ["a", "b"], "type": ["parking", "entrance"], "source": ["bdl", "osm"],
                            "subtype": ["", ""], "name": ["", ""], "weight_pop": [np.nan, np.nan]},
                           geometry=[Point(0, 0), Point(10, 0)], crs=CRS)
    ov = pd.DataFrame([
        {"action": "drop", "type": "parking", "x": 5.0, "y": 0.0, "radius_m": 20.0},
        {"action": "add", "type": "gate", "x": 500.0, "y": 500.0, "radius_m": 0.0},
    ])
    out = apply_overrides(pts, ov)
    assert sorted(out["type"]) == ["entrance", "gate"]        # parking usuniety, wjazd (inny typ) zostaje
    assert out.loc[out["type"] == "gate", "source"].iloc[0] == "wlasciciel"


# --- calosc ------------------------------------------------------------------------------

def test_build_access_set_counts_and_roads_kinds():
    road = LineString([(2000, 500), (2000, 1500)])
    duct = LineString([(2030, 1005), (2500, 1300)])
    osm_roads = _roads([
        (road, "tertiary", {"surface": "asphalt", "tracktype": None, "access": None, "motor_vehicle": None}),
        (duct, "track", {"surface": None, "tracktype": "grade2", "access": None, "motor_vehicle": None}),
    ])
    fire = gpd.GeoDataFrame({"source_id": ["1"], "fire_no": ["72"]},
                            geometry=[LineString([(2500, 1300), (2600, 2000)])], crs=CRS)
    bdl_parkings = gpd.GeoDataFrame({"source_id": ["9"], "subtype": ["parking_lesny"], "name": [""]},
                                    geometry=[Point(2100, 1900)], crs=CRS)
    empty_gates = gpd.GeoDataFrame({"osm_id": [], "barrier": [], "access": []}, geometry=[], crs=CRS)
    s = build_access_set(
        forest_boundary=FOREST,
        sources={"osm_roads": osm_roads, "osm_gates": empty_gates, "fire_roads": fire, "bdl_parkings": bdl_parkings},
        osm_parking=None, pop_points=None, tiles=[(0, 0, 10000, 10000)], cfg=CFG,
    )
    assert s.counts["parking_bdl"] == 1
    assert s.counts["entrance"] >= 1
    assert s.counts["roads_by_kind"] == {"closed": 1, "fire": 1, "public": 1}
    assert s.counts["fallback_tile_count"] == 0
    assert set(s.roads["surface_class"]) >= {"gravel", "hard", "unknown"}


# --- nawierzchnia dojazdow pozarowych z OSM -----------------------------------

def test_fire_road_takes_surface_from_nearest_described_osm_road():
    from pipeline.access_points import attach_osm_surface_to_fire_roads
    osm = prepare_osm_roads(_roads([
        (LineString([(0, 5), (100, 5)]), "track", {"surface": "asphalt", "tracktype": None, "access": None, "motor_vehicle": None}),
        (LineString([(0, 500), (100, 500)]), "track", {"surface": None, "tracktype": None, "access": None, "motor_vehicle": None}),
    ]), CFG)
    fire = gpd.GeoDataFrame({"kind": ["fire"] * 3, "surface_class": ["unknown"] * 3, "fire_no": ["1", "2", "3"]},
                            geometry=[LineString([(0, 0), (100, 0)]),         # 5 m od drogi z asfaltem
                                      LineString([(0, 495), (100, 495)]),     # przy drodze BEZ opisu
                                      LineString([(0, 2000), (100, 2000)])],  # daleko od wszystkiego
                            crs=CRS)
    out = attach_osm_surface_to_fire_roads(fire, osm, 20.0)
    assert out["surface_class"].tolist() == ["hard", "unknown", "unknown"]
    assert out["surface_source"].tolist() == ["osm", "brak", "brak"]
