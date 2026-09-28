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


def roads_feature_collection(model: AccessModel, tolerance_m: float) -> dict:
    roads = model.roads
    if not len(roads):
        return {"type": "FeatureCollection", "features": []}
    simple = roads.geometry.simplify(tolerance_m, preserve_topology=False) if tolerance_m > 0 else roads.geometry
    wgs = gpd.GeoSeries(simple, crs="EPSG:2180").to_crs("EPSG:4326")
    features = []
    for (_, row), geom in zip(roads.iterrows(), wgs):
        if geom is None or geom.is_empty:
            continue
        att = _num(row["attractiveness"])
        # Zwarte wlasciwosci (rozmiar pliku zalezy od liczby odcinkow, nie od
        # wierzcholkow): klase atrakcyjnosci liczy przegladarka z liczby, puste
        # pola sa pomijane, zrodlo dojazdu pozarowego wynika z kind == "fire".
        props = {"kind": row["kind"], "surface": row["surface_class"]}
        if row["kind"] != "fire":
            props["source"] = row["source"]
        if row["fire_no"]:
            props["fire_no"] = row["fire_no"]
        if att is not None:
            props["attractiveness"] = round(att, 3)
        features.append({"type": "Feature", "geometry": {
            "type": geom.geom_type, "coordinates": _round_coords(list(geom.coords)),
        }, "properties": props})
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
    """Zapisuje drogi, zwiekszajac tolerancje uproszczenia x2 az plik <= limit.
    Zwraca (sciezka, uzyta_tolerancja_m)."""
    out_path = pathlib.Path(out_path)
    tolerance = start_tolerance_m
    for _ in range(6):
        size = _write(roads_feature_collection(model, tolerance), out_path)
        if size <= limit_bytes:
            return out_path, tolerance
        tolerance *= 2.0
    raise ValueError(f"{out_path.name}: nie miesci sie w limicie {limit_bytes} B nawet przy tolerancji {tolerance / 2} m")
