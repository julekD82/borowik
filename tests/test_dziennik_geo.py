import geopandas as gpd
import numpy as np
from shapely.geometry import box

from pipeline import dziennik_geo as G
from pipeline.field_data import read_gpx


def _index():
    """Dwa sasiednie wydzielenia 100x100 m: A = x 0..100, B = x 100..200 (EPSG:2180)."""
    stands = gpd.GeoDataFrame(
        {
            "stand_id": ["02-19-1-09-933   -a   -00@2026", "02-19-1-09-933   -b   -00@2026"],
            "adr_for": ["02-19-1-09-933   -a   -00", "02-19-1-09-933   -b   -00"],
            "label": ["A", "B"],
        },
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=2180,
    )
    return G.StandIndex(stands)


def test_stand_label_and_district_names():
    assert G.stand_label("02-14-3-11-96   -a   -00", "Zawadzkie") == "Oddz. 96a · Nadl. Zawadzkie"
    assert G.stand_label("03-04-2-10-221   -m   -00", None) == "Oddz. 221m · nadl. 03-04"
    assert G.stand_label("xx", None) == "Wydzielenie xx"
    assert G.district_name("02-16", "BDL_02_16_KOSZECIN_2026") == "Koszęcin"
    assert G.district_name("04-22", "BDL_04_22_STRZELCE_OPOLSKIE_2026") == "Strzelce Opolskie"
    assert G.district_name("04-22", None) is None


def test_near_boundary_uses_accuracy_or_25m_default(monkeypatch):
    idx = _index()
    monkeypatch.setattr(G, "to_2180", lambda lon, lat: np.array([[lon, lat]]))  # wspolrzedne juz metryczne
    near = G.assign_find(idx, 90.0, 50.0, accuracy_m=15.0)   # 10 m od granicy A/B, dokladnosc 15 m
    far = G.assign_find(idx, 90.0, 50.0, accuracy_m=5.0)
    default = G.assign_find(idx, 80.0, 50.0, accuracy_m=None)  # 20 m < 25 m
    assert near["label"] == "A" and near["near_boundary"] is True
    assert far["near_boundary"] is False and round(far["boundary_m"]) == 10
    assert default["near_boundary"] is True
    outside = G.assign_find(idx, 500.0, 500.0, accuracy_m=5.0)
    assert outside["stand_id"] is None and outside["near_boundary"] is None


def test_time_in_stands_splits_by_length_and_skips_gaps():
    idx = _index()
    xy = np.array([[50.0, 50.0], [150.0, 50.0], [150.0, 50.0], [190.0, 50.0], [190.0, 50.0]])
    t = [0, 100_000, 130_000, 130_000 + 20 * 60_000, 130_000 + 20 * 60_000 + 40_000]
    # odcinek 1: 100 s, po polowie w A i B; odcinek 2: 30 s w miejscu w B; odcinek 3: przerwa 20 min (nie liczy sie);
    # odcinek 4: 40 s w miejscu w B
    out = G.time_in_stands(idx, xy, t)
    a, b = idx.ids
    assert round(out["seconds"][a]) == 50
    assert round(out["seconds"][b]) == 50 + 30 + 40
    assert round(out["gap_s"]) == 1200
    assert out["touched"] == {a, b}
    assert out["unmatched_s"] == 0


def test_time_outside_any_stand_is_unmatched():
    idx = _index()
    xy = np.array([[300.0, 50.0], [400.0, 50.0]])
    out = G.time_in_stands(idx, xy, [0, 60_000])
    assert out["seconds"] == {} and round(out["unmatched_s"]) == 60


def test_gpx_marks_low_accuracy_points_and_is_readable(tmp_path):
    route = G.parse_route({
        "track_geojson": '{"type":"LineString","coordinates":[[18.67,50.54],[18.68,50.55]]}',
        "point_times_ms": '["1789908376406","1789908381434"]',
        "point_accuracies": "[718.9, 12]",
        "distance_m": "100", "duration_s": "5",
    })
    assert route["times_ms"] == [1789908376406, 1789908381434]
    path = tmp_path / "trasy" / "a.gpx"
    assert G.write_gpx(path, "Test & <wyjście>", route) == 1
    text = path.read_text(encoding="utf-8")
    assert text.count("<cmt>") == 1 and "&amp;" in text
    points = read_gpx(path)
    assert len(points) == 2 and points[0][1:] == (50.54, 18.67)


def test_parse_route_rejects_mismatched_lengths():
    assert G.parse_route({"track_geojson": '{"coordinates":[[1,2],[3,4]]}', "point_times_ms": "[1]",
                          "point_accuracies": "[]"}) is None


def test_bad_accuracy_points_take_position_of_nearest_good_point():
    idx = _index()
    # start w B z bardzo zlym punktem (w A), potem dobre punkty w B; zly punkt nie moze dac czasu w A
    xy = np.array([[50.0, 50.0], [150.0, 50.0], [160.0, 50.0]])
    t = [0, 30_000, 60_000]
    plain = G.time_in_stands(idx, xy, t)
    snapped = G.time_in_stands(idx, xy, t, accuracies=[719.0, 5.0, 5.0])
    a, b = idx.ids
    assert plain["seconds"].get(a, 0) > 0
    assert round(snapped["seconds"][b]) == 60 and a not in snapped["seconds"] and snapped["touched"] == {b}


def test_snap_bad_points_edge_cases():
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]])
    t = [0, 10_000, 20_000]
    assert (G.snap_bad_points(xy, t, [5, 60, 5])[1] == xy[0]).all()  # rowny czas: pierwszy z najblizszych
    assert (G.snap_bad_points(xy, t, [60, 60, 60]) == xy).all()      # brak dobrych punktow: bez zmian
    assert (G.snap_bad_points(xy, t, None) == xy).all()
    assert (G.snap_bad_points(xy, t, [None, 60, None])[1] == xy[0]).all()
