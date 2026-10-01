"""Eksport 'na telefon' (KMZ): tylko najlepsze 5% wydzielen, kolor, foldery, liczba obiektow, WGS84."""
import io
import json
import xml.etree.ElementTree as ET
import zipfile

import pytest

from pipeline import phone_kmz
from pipeline.phone_kmz import (
    TOP_COLOR,
    TOP_LABEL,
    build_kml,
    classify_by_percentile,
    export_kmz,
    simplify_geometry,
)

NS = {"k": "http://www.opengis.net/kml/2.2"}
CENTER_LAT, CENTER_LON, RADIUS_KM = 50.60, 18.40, 20.0


def _square(i, size=0.001):
    """Kwadrat ok. 70 x 110 m w siatce 10 x N na WGS84, w obszarze analizy."""
    x0 = CENTER_LON - 0.05 + (i % 10) * 0.004
    y0 = CENTER_LAT - 0.05 + (i // 10) * 0.004
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]]],
    }


def _dataset(n=100, with_no_pressure=True, masked_out=(), with_regions=True, with_parkings=True):
    """n wydzielen: R = 100 - i (i=0 najlepsze); id 's{i}'. Wydzielenia z `masked_out` maja mask=False."""
    scores, features = [], []
    for i in range(n):
        s = {"stand_id": f"s{i}", "R": 100.0 - i, "H": 0.5, "F": 0.6, "P": 0.3, "mask": i not in masked_out,
             "day": "2026-09-30"}
        if with_no_pressure:
            s["R_bez_presji"] = 100.0 - (n - 1 - i)  # odwrotna kolejnosc: i=n-1 najlepsze
        scores.append(s)
        features.append({"type": "Feature", "properties": {"stand_id": f"s{i}"}, "geometry": _square(i)})
    regions = [
        {"region_id": f"region_{k}", "rank_score": 60.0 + (k * 7) % 11, "centroid_lat": CENTER_LAT + k * 0.01,
         "centroid_lon": CENTER_LON + k * 0.01, "stand_count": 3, "stand_ids": [],
         "near_place": {"name": f"Wies{k}", "distance_m": 1500}}
        for k in range(1, 8)
    ] if with_regions else None
    access = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [CENTER_LON + 0.01 * k, CENTER_LAT]},
         "properties": {"id": f"pk{k}", "type": t, "name": f"Obiekt {k}"}}
        for k, t in enumerate(["parking", "parking", "gate", "entrance", "parking"])
    ]} if with_parkings else None
    return {
        "scores": scores, "stands": {"type": "FeatureCollection", "features": features},
        "regions": regions, "access_points": access,
        "manifest": {"lat": CENTER_LAT, "lon": CENTER_LON, "radius_km": RADIUS_KM, "day": "2026-09-30"},
    }


def _parse(kml_text):
    return ET.fromstring(kml_text.encode("utf-8"))


def _folder(root, name):
    for f in root.iter("{%s}Folder" % NS["k"]):
        if f.find("k:name", NS).text == name:
            return f
    raise AssertionError(f"brak folderu {name!r}")


def _folder_names(root):
    return [f.find("k:name", NS).text for f in root.iter("{%s}Folder" % NS["k"])]


# --- klasy percentylowe ------------------------------------------------------

def test_classify_splits_5_20_50_percent_of_masked_stands():
    values = [100.0 - i for i in range(100)]
    classes = classify_by_percentile(values)
    assert classes.count(1) == 5 and classes.count(2) == 15 and classes.count(3) == 30 and classes.count(4) == 50
    assert classes[0] == 1 and classes[4] == 1 and classes[5] == 2 and classes[19] == 2
    assert classes[20] == 3 and classes[49] == 3 and classes[50] == 4 and classes[99] == 4


def test_classify_ties_share_one_class():
    classes = classify_by_percentile([10.0] * 50)
    assert set(classes) == {1}


def test_classify_is_independent_of_input_order():
    values = [3.0, 9.0, 1.0, 7.0, 5.0, 8.0, 2.0, 6.0, 4.0, 10.0]
    classes = classify_by_percentile(values)
    assert classes[values.index(10.0)] == 1
    assert classes[values.index(1.0)] == 4


# --- kolor ------------------------------------------------------------------

def test_top_color_is_semi_transparent_cyan():
    assert TOP_COLOR.startswith("99") and TOP_COLOR[2:] == "ffe500"  # cyjan #00E5FF (KML: aabbggrr)


def test_single_style_with_cyan_fill_and_thin_outline():
    root = _parse(build_kml(_dataset()))
    styles = {s.get("id"): s for s in root.iter("{%s}Style" % NS["k"])}
    assert set(styles) == {"najlepsze"}
    assert styles["najlepsze"].find("k:PolyStyle/k:color", NS).text == TOP_COLOR
    assert styles["najlepsze"].find("k:PolyStyle/k:fill", NS).text == "1"
    assert float(styles["najlepsze"].find("k:LineStyle/k:width", NS).text) <= 1.0


# --- tylko najlepsze 5% (telefon nie udzwignal 28 tys. wielokatow) ------------

def _polygon_marks(root):
    return [p for p in root.iter("{%s}Placemark" % NS["k"]) if p.find(".//k:Polygon", NS) is not None]


def _descriptions(marks):
    return " ".join(p.find("k:description", NS).text for p in marks)


def test_only_the_best_5_percent_of_masked_stands_are_exported():
    root = _parse(build_kml(_dataset(n=100)))
    marks = list(_folder(root, TOP_LABEL).iter("{%s}Placemark" % NS["k"]))
    assert len(marks) == 5 and len(_polygon_marks(root)) == 5
    assert {p.find("k:styleUrl", NS).text for p in marks} == {"#najlepsze"}
    text = _descriptions(marks)
    assert all(f"s{i} " in text for i in range(5)) and "s5 " not in text


def test_stands_outside_mask_are_omitted_and_do_not_shift_percentiles():
    masked_out = set(range(0, 100, 2))  # polowa poza maska (w tym najlepsze wg R)
    root = _parse(build_kml(_dataset(n=100, masked_out=masked_out)))
    marks = _polygon_marks(root)
    assert len(marks) == 3  # najlepsze 5% liczone tylko z 50 wydzielen w masce
    text = _descriptions(marks)
    assert "s0 " not in text and "s2 " not in text  # parzyste poza maska
    assert all(f"s{i} " in text for i in (1, 3, 5))


def test_no_pressure_set_is_not_exported():
    for data in (_dataset(n=100), _dataset(n=100, with_no_pressure=False)):
        root = _parse(build_kml(data))
        assert not any("Bez presji" in n for n in _folder_names(root))
        assert len(_polygon_marks(root)) == 5


def test_only_exported_stands_are_simplified(monkeypatch):
    # Upraszczanie geometrii jest drogie: robimy je tylko dla wydzielen, ktore trafia do pliku.
    calls = []
    original = phone_kmz.simplify_geometry
    monkeypatch.setattr(phone_kmz, "simplify_geometry", lambda g: calls.append(1) or original(g))
    build_kml(_dataset(n=100))
    assert len(calls) == 5


def test_regions_folder_has_five_best_ranked_points_visible():
    data = _dataset()
    root = _parse(build_kml(data))
    folder = _folder(root, "Rejony (5 najlepszych)")
    pts = list(folder.iter("{%s}Placemark" % NS["k"]))
    assert len(pts) == 5
    assert folder.find("k:visibility", NS) is None or folder.find("k:visibility", NS).text == "1"
    best5 = sorted(data["regions"], key=lambda r: -r["rank_score"])[:5]
    coords = [p.find("k:Point/k:coordinates", NS).text for p in pts]
    for r, c in zip(best5, coords):
        lon, lat = map(float, c.split(",")[:2])
        assert lon == pytest.approx(r["centroid_lon"], abs=1e-5) and lat == pytest.approx(r["centroid_lat"], abs=1e-5)
    assert pts[0].find("k:name", NS).text.startswith("Rejon 1")
    assert "Wies" in pts[0].find("k:name", NS).text


def test_parking_folder_contains_only_parkings():
    root = _parse(build_kml(_dataset()))
    folder = _folder(root, "Parkingi")
    assert len(list(folder.iter("{%s}Placemark" % NS["k"]))) == 3


def test_optional_folders_omitted_when_data_missing():
    root = _parse(build_kml(_dataset(with_regions=False, with_parkings=False)))
    names = _folder_names(root)
    assert "Parkingi" not in names and "Rejony (5 najlepszych)" not in names


# --- geometria: WGS84 i uproszczenie ------------------------------------------

def test_all_coordinates_are_wgs84_inside_analysis_area():
    root = _parse(build_kml(_dataset()))
    checked = 0
    for c in root.iter("{%s}coordinates" % NS["k"]):
        for triple in c.text.split():
            lon, lat = map(float, triple.split(",")[:2])
            assert abs(lat - CENTER_LAT) < RADIUS_KM / 111.0 * 1.05
            assert abs(lon - CENTER_LON) < RADIUS_KM / (111.0 * 0.635) * 1.05
            checked += 1
    assert checked > 20


def test_build_rejects_projected_coordinates():
    data = _dataset(n=3)
    data["stands"]["features"][0]["geometry"] = {
        "type": "Polygon", "coordinates": [[[500000, 300000], [500100, 300000], [500100, 300100], [500000, 300000]]]}
    with pytest.raises(ValueError, match="WGS84"):
        build_kml(data)


def test_simplify_removes_one_meter_wiggle_but_keeps_ten_meter_bump():
    dlat = 1 / 111_000
    dlon = 1 / (111_000 * 0.635)
    x0, y0 = 18.4, 50.6
    wiggle = {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + 100 * dlon, y0], [x0 + 200 * dlon, y0 + 1 * dlat], [x0 + 300 * dlon, y0],
        [x0 + 300 * dlon, y0 + 200 * dlat], [x0, y0 + 200 * dlat], [x0, y0]]]}
    bump = {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + 100 * dlon, y0], [x0 + 200 * dlon, y0 + 10 * dlat], [x0 + 300 * dlon, y0],
        [x0 + 300 * dlon, y0 + 200 * dlat], [x0, y0 + 200 * dlat], [x0, y0]]]}
    assert len(simplify_geometry(wiggle).exterior.coords) == 5
    kept = list(simplify_geometry(bump).exterior.coords)
    assert any(abs(x - (x0 + 200 * dlon)) < 1e-6 and abs(y - (y0 + 10 * dlat)) < 1e-6 for x, y in kept)


def test_simplified_geometry_stays_in_wgs84_close_to_original():
    g = simplify_geometry(_dataset(n=1)["stands"]["features"][0]["geometry"])
    x, y = g.centroid.x, g.centroid.y
    assert abs(x - (CENTER_LON - 0.05 + 0.0005)) < 1e-4 and abs(y - (CENTER_LAT - 0.05 + 0.0005)) < 1e-4


def test_multipolygon_with_hole_is_written_as_multigeometry_with_inner_boundary():
    data = _dataset(n=1)
    outer = [[18.35, 50.55], [18.36, 50.55], [18.36, 50.56], [18.35, 50.56], [18.35, 50.55]]
    hole = [[18.353, 50.553], [18.357, 50.553], [18.357, 50.557], [18.353, 50.557], [18.353, 50.553]]
    other = [[18.37, 50.55], [18.38, 50.55], [18.38, 50.56], [18.37, 50.56], [18.37, 50.55]]
    data["stands"]["features"][0]["geometry"] = {"type": "MultiPolygon", "coordinates": [[outer, hole], [other]]}
    root = _parse(build_kml(data))
    pm = next(root.iter("{%s}Placemark" % NS["k"]))
    assert len(pm.findall(".//k:Polygon", NS)) == 2
    assert len(pm.findall(".//k:innerBoundaryIs", NS)) == 1


# --- KMZ i rozmiar -----------------------------------------------------------

def test_export_writes_valid_kmz_with_doc_kml(tmp_path):
    result = export_kmz(_dataset(), tmp_path / "out" / "borowik_test_2026-09-30.kmz")
    assert result.path.exists() and result.size_bytes == result.path.stat().st_size
    with zipfile.ZipFile(result.path) as z:
        assert z.namelist() == ["doc.kml"]
        root = ET.fromstring(z.read("doc.kml"))
    assert root.tag == "{%s}kml" % NS["k"]
    assert result.stand_count == 100 and result.exported_count == 5
    assert result.region_count == 5 and result.parking_count == 3


# --- wczytywanie zrodla ------------------------------------------------------

def test_load_source_reads_snapshot_dir_and_tolerates_missing_optional_files(tmp_path):
    data = _dataset()
    (tmp_path / "scores.json").write_text(json.dumps(data["scores"]), encoding="utf-8")
    (tmp_path / "stands.geojson").write_text(json.dumps(data["stands"]), encoding="utf-8")
    src = phone_kmz.load_source(tmp_path)
    assert src["regions"] is None and src["access_points"] is None and src["manifest"] is None
    assert src["day"] == "2026-09-30"


def test_load_source_without_scores_raises_clear_error(tmp_path):
    with pytest.raises(ValueError, match="scores.json"):
        phone_kmz.load_source(tmp_path)


def test_no_manifest_skips_area_check_but_still_builds():
    data = _dataset(n=5)
    data["manifest"] = None
    assert "<kml" in build_kml(data)
