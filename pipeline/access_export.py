"""Plan wdrozenia Faza 3.5: eksport warstw punktow dostepu i drog lesnych.

`access_points_{day}.geojson` (punkty: typ, zrodlo, atrakcyjnosc) i
`forest_roads_{day}.geojson` (linie: nawierzchnia, zrodlo, publiczna/
zamknieta, atrakcyjnosc, numer dojazdu pozarowego BDL). WGS84, wspolrzedne
zaokraglone do 5 miejsc (~1 m); geometria drog jest upraszczana w metrach
(EPSG:2180) -- tolerancja rosnie, az plik zmiesci sie w limicie rozmiaru.
"""
import json
import math
import pathlib

import geopandas as gpd
import numpy as np
import shapely

from pipeline.access_pressure import AccessModel, attractiveness_class

DEFAULT_LIMIT_BYTES = 6 * 1024 * 1024
_ROUND = 5


def _round_coords(obj):
    if isinstance(obj, float):
        return round(obj, _ROUND)
    if isinstance(obj, (list, tuple)):
        return [_round_coords(o) for o in obj]
    return obj


def _num(value):
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) else round(value, 4)


def points_feature_collection(model: AccessModel) -> dict:
    pts = model.points
    if not len(pts):
        return {"type": "FeatureCollection", "features": []}
    wgs = pts.to_crs("EPSG:4326")
    features = []
    for (_, row), geom in zip(pts.iterrows(), wgs.geometry):
        a_norm = _num(row["A_norm"])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(geom.x, _ROUND), round(geom.y, _ROUND)]},
            "properties": {
                "id": row["point_id"], "type": row["type"], "source": row["source"],
                "subtype": row["subtype"], "name": row["name"] or "",
                "attractiveness": a_norm, "attractiveness_class": attractiveness_class(a_norm or 0.0),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _geometry_json(geom) -> dict:
    if geom.geom_type == "MultiLineString":
        return {"type": "MultiLineString", "coordinates": [_round_coords(list(g.coords)) for g in geom.geoms]}
    return {"type": geom.geom_type, "coordinates": _round_coords(list(geom.coords))}


def _road_props(row, att) -> dict:
    # Zwarte wlasciwosci (rozmiar pliku zalezy od liczby odcinkow, nie od
    # wierzcholkow): klase atrakcyjnosci liczy przegladarka z liczby, puste
    # pola sa pomijane, zrodlo dojazdu pozarowego wynika z kind == "fire".
    props = {"kind": row["kind"], "surface": row["surface_class"]}
    if row["kind"] != "fire":
        props["source"] = row["source"]
    if row["fire_no"]:
        props["fire_no"] = row["fire_no"]
    if att is not None:
        props["attractiveness"] = att
    return props


ATTRACTIVENESS_STEP = 0.05   # dzieli progi klas (0,1 / 0,3), wiec kwantyzacja w dol nie zmienia klasy


def roads_feature_collection(model: AccessModel, tolerance_m: float, dissolve: bool = False) -> dict:
    """`dissolve=True`: odcinki o tych samych atrybutach (rodzaj, nawierzchnia,
    zrodlo, numer dojazdu, atrakcyjnosc skwantowana w dol do 0,05) sa laczone w
    jeden obiekt (line_merge) -- tak zmniejsza sie liczba obiektow, ktora
    decyduje o rozmiarze pliku."""
    roads = model.roads
    if not len(roads):
        return {"type": "FeatureCollection", "features": []}
    simple = roads.geometry.simplify(tolerance_m, preserve_topology=False) if tolerance_m > 0 else roads.geometry
    if not dissolve:
        wgs = gpd.GeoSeries(simple, crs="EPSG:2180").to_crs("EPSG:4326")
        features = []
        for (_, row), geom in zip(roads.iterrows(), wgs):
            if geom is None or geom.is_empty:
                continue
            att = _num(row["attractiveness"])
            features.append({"type": "Feature", "geometry": _geometry_json(geom),
                             "properties": _road_props(row, None if att is None else round(att, 3))})
        return {"type": "FeatureCollection", "features": features}

    groups: dict = {}
    for (_, row), geom in zip(roads.iterrows(), simple):
        if geom is None or geom.is_empty:
            continue
        att = _num(row["attractiveness"])
        if att is not None:
            att = round(math.floor(att / ATTRACTIVENESS_STEP + 1e-9) * ATTRACTIVENESS_STEP, 2)
        key = (row["kind"], row["surface_class"], row["source"] if row["kind"] != "fire" else "",
               row["fire_no"] or "", att)
        groups.setdefault(key, {"row": row, "geoms": []})["geoms"].append(geom)
    keys = list(groups)
    merged = []
    for key in keys:
        union = shapely.union_all(groups[key]["geoms"])
        merged.append(shapely.line_merge(union) if union.geom_type != "LineString" else union)
    wgs = gpd.GeoSeries(merged, crs="EPSG:2180").to_crs("EPSG:4326")
    features = []
    for key, geom in zip(keys, wgs):
        if geom is None or geom.is_empty:
            continue
        features.append({"type": "Feature", "geometry": _geometry_json(geom),
                         "properties": _road_props(groups[key]["row"], key[4])})
    return {"type": "FeatureCollection", "features": features}


def _write(collection: dict, out_path: pathlib.Path) -> int:
    text = json.dumps(collection, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def write_access_points_geojson(model: AccessModel, out_path, limit_bytes: int = DEFAULT_LIMIT_BYTES) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    size = _write(points_feature_collection(model), out_path)
    if size > limit_bytes:
        raise ValueError(f"{out_path.name}: {size} B przekracza limit {limit_bytes} B")
    return out_path


def write_forest_roads_geojson(model: AccessModel, out_path, limit_bytes: int = DEFAULT_LIMIT_BYTES,
                                start_tolerance_m: float = 2.0) -> tuple[pathlib.Path, float]:
    """Zapisuje drogi tak, by plik mieszcil sie w limicie: najpierw coraz mocniejsze
    uproszczenie geometrii (x2, do 4 razy), a gdy to nie wystarcza (rozmiar zalezy od
    LICZBY odcinkow, np. przy promieniu 25 km) -- laczenie sasiednich odcinkow o
    tych samych atrybutach (`dissolve`) przy rosnacej tolerancji. Zwraca
    (sciezka, uzyta_tolerancja_m); to, czy odcinki zostaly polaczone, trafia do
    `model.counts["forest_roads_dissolved"]` (i dalej do manifestu)."""
    out_path = pathlib.Path(out_path)
    attempts = []
    tol = start_tolerance_m
    for _ in range(3):
        attempts.append((tol, False))
        tol *= 2.0
    tol = start_tolerance_m * 2.0
    for _ in range(5):
        attempts.append((tol, True))
        tol *= 2.0
    last = None
    for tolerance, dissolve in attempts:
        last = _write(roads_feature_collection(model, tolerance, dissolve), out_path)
        if last <= limit_bytes:
            model.counts["forest_roads_dissolved"] = dissolve
            return out_path, tolerance
    raise ValueError(f"{out_path.name}: {last} B nie miesci sie w limicie {limit_bytes} B "
                     f"nawet po polaczeniu odcinkow (tolerancja {attempts[-1][0]} m)")
