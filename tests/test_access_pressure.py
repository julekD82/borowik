import copy
import math

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point

from pipeline.access_points import AccessSet
from pipeline.access_pressure import (
    attractiveness_class, build_access_model, compute_access_pressure,
    compute_attractiveness, kernel, propagate_corridor,
)
from pipeline.habitat import load_profile

CFG = load_profile("profiles/boletus_edulis.yaml")["pressure"]["access_points"]
CRS = "EPSG:2180"


def _pts(rows):
    """rows: (x, y, type)"""
    return gpd.GeoDataFrame(
        {"point_id": [f"p{i}" for i in range(len(rows))], "type": [r[2] for r in rows],
         "source": "test", "subtype": "", "name": "", "weight_pop": np.nan},
        geometry=[Point(r[0], r[1]) for r in rows], crs=CRS)


def _roads(rows):
    """rows: (LineString, kind, surface_class)"""
    return gpd.GeoDataFrame(
        {"kind": [r[1] for r in rows], "surface_class": [r[2] for r in rows], "source": "test",
         "fire_no": "", "highway": ""}, geometry=[r[0] for r in rows], crs=CRS)


def _empty_roads():
    return _roads([])


def _cfg(**over):
    cfg = copy.deepcopy(CFG)
    cfg.update(over)
    return cfg


def test_kernel_is_smooth_and_zero_beyond_range():
    d = np.array([0.0, 1500.0, 2999.0, 3000.0, 4000.0])
    k = kernel(d, 3000.0)
    assert k[0] == pytest.approx(1.0)
    assert k[1] == pytest.approx((1 - 0.25) ** 2)
    # brak skoku na granicy: 2,99 km vs 3,01 km -- praktycznie ta sama presja (plan 3.3)
    assert kernel(2990.0, 3000.0) < 1e-4 and kernel(3010.0, 3000.0) == 0.0
    assert k[3] == 0.0 and k[4] == 0.0


def test_attractiveness_uses_population_within_range_and_saturates():
    points = _pts([(0, 0, "parking"), (100000, 0, "parking")])
    pop_xy = np.array([[0.0, 0.0], [10000.0, 0.0]])
    pop = np.array([5000.0, 5000.0])
    a, a_norm = compute_attractiveness(points, pop_xy, pop, CFG)
    # parking 0: komorka na miejscu (g=1) + druga w 10 km (jadro 20 km)
    expected = 5000.0 + 5000.0 * kernel(10000.0, 20000.0)
    assert a[0] == pytest.approx(expected)
    assert a[1] == 0.0                                  # daleko od ludzi: zero
    assert a_norm[0] == pytest.approx(expected / (expected + CFG["types"]["parking"]["a_half"]))
    assert 0.0 < a_norm[0] < 1.0


def test_attractiveness_absolute_normalization_not_relative_to_max():
    # jeden punkt w calej analizie: A_norm nie jest 1.0 (jak przy normalizacji lokalnej)
    points = _pts([(0, 0, "parking")])
    _, a_norm = compute_attractiveness(points, np.array([[0.0, 0.0]]), np.array([100.0]), CFG)
    assert a_norm[0] < 0.01


def test_settlement_attractiveness_walks_only_1_5km():
    points = _pts([(0, 0, "settlement")])
    pop_xy = np.array([[0.0, 0.0], [5000.0, 0.0]])
    a, _ = compute_attractiveness(points, pop_xy, np.array([400.0, 9999.0]), CFG)
    assert a[0] == pytest.approx(400.0)   # oczko w 5 km poza zasiegiem pieszym


def _model(points, roads, pop_xy=np.array([[0.0, 0.0]]), pop=np.array([50000.0]), cfg=None):
    cfg = cfg or CFG
    return build_access_model(AccessSet(points=points, roads=roads), pop_xy, pop, cfg)


def _stand(x, y):
    return np.array([[float(x), float(y)]])


def test_stand_beyond_every_range_has_zero_pressure():
    model = _model(_pts([(0, 0, "parking")]), _empty_roads())
    out = compute_access_pressure(_stand(3100, 0), model)   # > 3 km od parkingu
    assert out["P"].iloc[0] == 0.0 and out["access_raw"].iloc[0] == 0.0
    near = compute_access_pressure(_stand(500, 0), model)
    assert near["P"].iloc[0] > 0.0


def test_pressure_is_sum_over_points_not_max():
    one = _model(_pts([(0, 0, "parking")]), _empty_roads())
    three = _model(_pts([(0, 0, "parking"), (100, 0, "parking"), (0, 100, "parking")]), _empty_roads())
    p1 = compute_access_pressure(_stand(500, 0), one)["access_raw"].iloc[0]
    p3 = compute_access_pressure(_stand(500, 0), three)["access_raw"].iloc[0]
    assert p3 > 2.5 * p1


def test_pressure_saturates_below_one_and_top_point_reported():
    cfg = _cfg(saturation_s=0.05)
    model = _model(_pts([(0, 0, "parking"), (2000, 0, "parking")]), _empty_roads(), cfg=cfg)
    out = compute_access_pressure(_stand(100, 0), model)
    assert 0.0 < out["P"].iloc[0] < 1.0
    assert out["P"].iloc[0] == pytest.approx(1 - math.exp(-out["access_raw"].iloc[0] / 0.05))
    assert out["top_point_id"].iloc[0] == "p0" and out["top_point_type"].iloc[0] == "parking"


def test_weights_by_type():
    # ten sam punkt i ludnosc (ten sam A_norm); parking (w=1,0, R=3 km) vs wjazd (w=0,6, R=2,5 km)
    pop = dict(pop_xy=np.array([[0.0, 0.0]]), pop=np.array([20000.0]))
    park = _model(_pts([(0, 0, "parking")]), _empty_roads(), **pop)
    ent = _model(_pts([(0, 0, "entrance")]), _empty_roads(), **pop)
    p = compute_access_pressure(_stand(1000, 0), park)["pcontrib_parking"].iloc[0]
    e = compute_access_pressure(_stand(1000, 0), ent)["pcontrib_entrance"].iloc[0]
    expected = 0.6 * (1 - (1000 / 2500) ** 2) ** 2 / ((1 - (1000 / 3000) ** 2) ** 2)
    assert e / p == pytest.approx(expected)


# --- droga lesna jako korytarz -------------------------------------------------

def _road_model(surface="hard", length=12000.0, pop_at=(0.0, 0.0)):
    parking = _pts([(0, 0, "parking")])
    road = _roads([(LineString([(0, 0), (length, 0)]), "closed", surface)])
    # gesty wierzcholek co 100 m: sciezki sieciowe po wierzcholkach
    coords = [(x, 0) for x in np.arange(0, length + 1, 100.0)]
    road = _roads([(LineString(coords), "closed", surface)])
    return _model(parking, road, pop_xy=np.array([pop_at]), pop=np.array([60000.0]))


def test_corridor_attractiveness_halves_every_3km_along_network():
    model = _road_model()
    a0 = model.points["A_norm"].iloc[0]
    # potencjal w wezle: 0,5^(d/3 km) * A_norm; probki to srodki krawedzi 100 m
    near = model.corridor_a[np.argmin(np.abs(model.corridor_xy[:, 0] - 50))]
    at3 = model.corridor_a[np.argmin(np.abs(model.corridor_xy[:, 0] - 3050))]
    at6 = model.corridor_a[np.argmin(np.abs(model.corridor_xy[:, 0] - 6050))]
    assert near == pytest.approx(a0 * 0.5 ** (50 / 3000), rel=1e-3)
    assert at3 / near == pytest.approx(0.5, rel=0.02)
    assert at6 / near == pytest.approx(0.25, rel=0.02)


def test_corridor_surface_multiplier():
    hard = _road_model("hard").corridor_a.max()
    dirt = _road_model("dirt").corridor_a.max()
    unknown = _road_model("unknown").corridor_a.max()
    assert dirt / hard == pytest.approx(0.3, rel=1e-6)
    assert unknown / hard == pytest.approx(0.5, rel=1e-6)


def test_corridor_lateral_range_is_300m():
    model = _road_model()
    inside = compute_access_pressure(_stand(1000, 200), model)
    outside = compute_access_pressure(_stand(1000, 350), model)
    assert inside["pcontrib_forest_road"].iloc[0] > 0.0
    assert outside["pcontrib_forest_road"].iloc[0] == 0.0
    assert outside["P"].iloc[0] == 0.0 or outside["pcontrib_parking"].iloc[0] > 0  # parking daje inne wklady


def test_corridor_not_reached_road_gets_zero_and_public_road_is_nan():
    parking = _pts([(0, 0, "parking")])
    roads = _roads([
        (LineString([(0, 0), (500, 0)]), "closed", "hard"),
        (LineString([(90000, 0), (90500, 0)]), "closed", "hard"),      # odcieta sieciowo
        (LineString([(0, 100), (500, 100)]), "public", "hard"),
    ])
    model = _model(parking, roads)
    att = model.roads["attractiveness"].values
    assert att[0] > 0 and att[1] == 0.0 and np.isnan(att[2])


def test_corridor_only_reaches_roads_connected_by_shared_vertices():
    parking = _pts([(0, 0, "parking")])
    roads = _roads([
        (LineString([(0, 0), (500, 0)]), "closed", "hard"),
        (LineString([(500, 0), (1000, 0)]), "closed", "hard"),       # wspolny wezel (500,0)
    ])
    att = _model(parking, roads).roads["attractiveness"].values
    assert att[1] > 0 and att[1] < att[0]


def test_stronger_access_point_wins_the_max_rule():
    # dwa parkingi na koncach drogi; potencjal to max, nie suma
    points = _pts([(0, 0, "parking"), (2000, 0, "parking")])
    coords = [(x, 0) for x in np.arange(0, 2001, 100.0)]
    roads = _roads([(LineString(coords), "closed", "hard")])
    model = _model(points, roads, pop_xy=np.array([[0.0, 0.0]]), pop=np.array([60000.0]))
    a_strong, a_weak = model.points["A_norm"].values
    assert a_strong > a_weak
    mid = model.corridor_a[np.argmin(np.abs(model.corridor_xy[:, 0] - 1050))]
    assert mid <= a_strong  # nigdy nie ponad najsilniejszym punktem


def test_attractiveness_class_edges():
    assert attractiveness_class(0.05) == "niska"
    assert attractiveness_class(0.2) == "srednia"
    assert attractiveness_class(0.5) == "wysoka"


def test_card_distances_reported():
    model = _model(_pts([(0, 0, "parking"), (0, 800, "entrance")]),
                   _roads([(LineString([(0, 1500), (3000, 1500)]), "closed", "hard")]))
    out = compute_access_pressure(_stand(0, 1000), model)
    assert out["d_parking_m"].iloc[0] == pytest.approx(1000.0)
    assert out["d_entrance_m"].iloc[0] == pytest.approx(200.0)
    assert out["d_hard_forest_road_m"].iloc[0] == pytest.approx(500.0)


def test_no_access_data_gives_zero_pressure_without_crashing():
    empty_pts = _pts([])
    model = _model(empty_pts, _empty_roads())
    out = compute_access_pressure(np.array([[0.0, 0.0], [10.0, 10.0]]), model)
    assert out["P"].tolist() == [0.0, 0.0]
