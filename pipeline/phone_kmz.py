"""Eksport 'na telefon': KMZ z najlepszymi 5% wydzielen (wg R), rejonami i parkingami.

Czysta logika bez sieci; wejscie to pliki eksportu aplikacji (`scores.json`, `stands.geojson`,
`regions.json`, `access_points.json`, `manifest.json` - bieza analiza albo migawka z `trips/`).
Tylko prezentacja: nic tu nie zmienia modelu (R, H, F, P). Geometrie sa WGS84 (tak jak
`stands.geojson`) i upraszczane z tolerancja ok. 3 m w EPSG:2180.

Do pliku trafia tylko klasa 1 -- najlepsze 5% wsrod wydzielen w masce (percentyl jak w aplikacji,
`classify_by_percentile`), w kolorze cyjan, wg R z presja. Pelny plik (wszystkie klasy i zestaw
"bez presji", ok. 28 tys. wielokatow dla 20 km) importowal sie na telefonie ok. 20 min i zawieszal
aplikacje; 5% to ok. 700 wielokatow."""
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.polygon import orient
from shapely.ops import transform

SIMPLIFY_TOLERANCE_M = 3.0
TOP_REGIONS = 5
COORD_DECIMALS = 6  # ok. 0,1 m

CLASS_THRESHOLDS = {1: 0.05, 2: 0.20, 3: 0.50}  # gorna granica udzialu wydzielen "lepszych od danego"
TOP_LABEL = "Najlepsze 5% wydzieleń"
TOP_COLOR = "99ffe500"  # KML: aabbggrr -- cyjan #00E5FF, polprzezroczysty
OUTLINE_ALPHA = "cc"

_TO_PL = Transformer.from_crs(4326, 2180, always_xy=True)
_TO_WGS = Transformer.from_crs(2180, 4326, always_xy=True)


def classify_by_percentile(values) -> list[int]:
    """Klasa 1..4 dla kazdej wartosci: udzial wartosci scisle wiekszych < 5% / 20% / 50%.
    Remisy (rowne wartosci) trafiaja do tej samej klasy, niezaleznie od kolejnosci wejscia."""
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    if n == 0:
        return []
    ascending = np.sort(arr)
    greater = n - np.searchsorted(ascending, arr, side="right")
    share = greater / n
    classes = np.full(n, 4, dtype=int)
    for cls in (3, 2, 1):
        classes[share < CLASS_THRESHOLDS[cls]] = cls
    return classes.tolist()


def _check_wgs84(coords) -> None:
    for x, y in coords:
        if not (-180 <= x <= 180 and -90 <= y <= 90):
            raise ValueError(
                "Geometria nie jest w WGS84 (lon/lat) - stands.geojson powinien miec stopnie, "
                f"a znaleziono ({x}, {y}).")


def simplify_geometry(geojson_geometry: dict):
    """GeoJSON (WGS84) -> geometria shapely (WGS84), uproszczona z tolerancja 3 m z zachowaniem topologii."""
    geom = shape(geojson_geometry)
    _check_wgs84(_iter_coords(geom))
    projected = transform(_TO_PL.transform, geom)
    simplified = projected.simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True)
    return transform(_TO_WGS.transform, simplified)


def _iter_coords(geom):
    parts = getattr(geom, "geoms", [geom])
    for part in parts:
        yield from part.exterior.coords
        for ring in part.interiors:
            yield from ring.coords


def _ring_kml(ring) -> str:
    pts = " ".join(f"{round(x, COORD_DECIMALS)},{round(y, COORD_DECIMALS)}" for x, y in ring.coords)
    return f"<LinearRing><coordinates>{pts}</coordinates></LinearRing>"


def _polygon_kml(poly) -> str:
    poly = orient(poly, 1.0)
    inner = "".join(f"<innerBoundaryIs>{_ring_kml(r)}</innerBoundaryIs>" for r in poly.interiors)
    return f"<Polygon><outerBoundaryIs>{_ring_kml(poly.exterior)}</outerBoundaryIs>{inner}</Polygon>"


def _geometry_kml(geom) -> str:
    if geom.geom_type == "Polygon":
        return _polygon_kml(geom)
    return "<MultiGeometry>" + "".join(_polygon_kml(p) for p in geom.geoms if not p.is_empty) + "</MultiGeometry>"


def _pl(value, digits=1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _short_id(stand_id: str) -> str:
    """'02-14-3-12-189   -a   -00@2026' -> '02-14-3-12-189-a-00' (bez spacji i sufiksu roku)."""
    return re.sub(r"\s+", "", stand_id.split("@")[0])


@dataclass
class _Stand:
    sid: str
    geometry_kml: str
    R: float
    description: str


@dataclass
class Prepared:
    stands: list  # _Stand: najlepsze 5% wydzielen w masce, R malejaco
    masked_count: int  # wydzielenia w masce z wynikiem (podstawa percentyla)
    regions: list | None
    parkings: list | None
    day: str | None
    title: str


def prepare(data: dict, title: str | None = None) -> Prepared:
    """Wybiera najlepsze 5% wydzielen w masce i upraszcza tylko ich geometrie (upraszczanie jest drogie)."""
    geometries = {f["properties"]["stand_id"]: f["geometry"] for f in data["stands"]["features"]}
    masked = [s for s in data["scores"]
              if s.get("mask") and s.get("R") is not None and s["stand_id"] in geometries]
    classes = classify_by_percentile([float(s["R"]) for s in masked])
    stands = []
    for s, cls in zip(masked, classes):
        if cls != 1:
            continue
        geom = simplify_geometry(geometries[s["stand_id"]])
        if geom.is_empty:
            continue
        parts = [_short_id(s["stand_id"]), f"R {_pl(s['R'])}"]
        if s.get("R_bez_presji") is not None:
            parts.append(f"bez presji {_pl(s['R_bez_presji'])}")
        for key in ("H", "F", "P"):
            if s.get(key) is not None:
                parts.append(f"{key} {_pl(s[key], 2)}")
        stands.append(_Stand(s["stand_id"], _geometry_kml(geom), float(s["R"]), " · ".join(parts)))
    stands.sort(key=lambda st: -st.R)
    parkings = None
    if data.get("access_points"):
        parkings = [f for f in data["access_points"]["features"] if f["properties"].get("type") == "parking"]
    day = data.get("day") or (data.get("manifest") or {}).get("day") or (data["scores"][0].get("day") if data["scores"] else None)
    return Prepared(stands, len(masked), data.get("regions"), parkings, day, title or "Borowik")


def _styles_kml() -> str:
    line = OUTLINE_ALPHA + TOP_COLOR[2:]
    return (f'<Style id="najlepsze"><LineStyle><color>{line}</color><width>1</width></LineStyle>'
            f"<PolyStyle><color>{TOP_COLOR}</color><fill>1</fill><outline>1</outline></PolyStyle></Style>")


def _top_folder(stands: list) -> str:
    marks = "".join(
        f"<Placemark><name>R {round(st.R)}</name><description>{escape(st.description)}</description>"
        f"<styleUrl>#najlepsze</styleUrl>{st.geometry_kml}</Placemark>"
        for st in stands)
    return f"<Folder><name>{escape(TOP_LABEL)}</name><open>1</open>{marks}</Folder>"


def _regions_folder(regions: list) -> str:
    best = sorted(regions, key=lambda r: -r["rank_score"])[:TOP_REGIONS]
    marks = []
    for pos, r in enumerate(best, start=1):
        place = (r.get("near_place") or {}).get("name")
        name = f"Rejon {pos} · {place}" if place else f"Rejon {pos}"
        desc = f"ranking {_pl(r['rank_score'])} · wydzieleń: {r.get('stand_count', '?')}"
        marks.append(
            f"<Placemark><name>{escape(name)}</name><description>{escape(desc)}</description><Point><coordinates>"
            f"{round(r['centroid_lon'], COORD_DECIMALS)},{round(r['centroid_lat'], COORD_DECIMALS)}"
            f"</coordinates></Point></Placemark>")
    return f"<Folder><name>Rejony (5 najlepszych)</name><open>1</open>{''.join(marks)}</Folder>"


def _parkings_folder(parkings: list) -> str:
    marks = []
    for f in parkings:
        x, y = f["geometry"]["coordinates"][:2]
        name = f["properties"].get("name") or "Parking"
        marks.append(f"<Placemark><name>{escape(name)}</name><Point><coordinates>"
                     f"{round(x, COORD_DECIMALS)},{round(y, COORD_DECIMALS)}</coordinates></Point></Placemark>")
    return f"<Folder><name>Parkingi</name><open>0</open>{''.join(marks)}</Folder>"


def render_kml(prep: Prepared) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             f"<name>{escape(prep.title)}</name>", _styles_kml(), _top_folder(prep.stands)]
    if prep.regions:
        parts.append(_regions_folder(prep.regions))
    if prep.parkings:
        parts.append(_parkings_folder(prep.parkings))
    parts.append("</Document></kml>")
    return "".join(parts)


def build_kml(data: dict, title: str | None = None) -> str:
    return render_kml(prepare(data, title))


@dataclass
class ExportResult:
    path: Path
    size_bytes: int
    stand_count: int  # wydzielenia w masce
    exported_count: int  # w pliku: najlepsze 5%
    region_count: int
    parking_count: int


def _write_kmz(path: Path, kml: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("doc.kml", kml.encode("utf-8"))
    tmp.replace(path)
    return path.stat().st_size


def export_kmz(data: dict, path: Path, title: str | None = None) -> ExportResult:
    """Zapisuje KMZ z najlepszymi 5% wydzielen, rejonami i parkingami."""
    path = Path(path)
    prep = prepare(data, title)
    size = _write_kmz(path, render_kml(prep))
    return ExportResult(
        path=path, size_bytes=size, stand_count=prep.masked_count, exported_count=len(prep.stands),
        region_count=min(len(prep.regions or []), TOP_REGIONS), parking_count=len(prep.parkings or []))


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def load_source(directory: Path) -> dict:
    """Wczytuje pliki eksportu z katalogu (frontend/public/data albo trips/<id>). Wymagane: scores.json
    i stands.geojson; reszta opcjonalna (starsze migawki nie maja R_bez_presji, parkingow itd.)."""
    directory = Path(directory)
    scores = _read_json(directory / "scores.json")
    stands = _read_json(directory / "stands.geojson")
    if not isinstance(scores, list) or not scores:
        raise ValueError(f"Brak scores.json (albo pusty) w {directory} - uruchom najpierw analizę.")
    if not isinstance(stands, dict) or not stands.get("features"):
        raise ValueError(f"Brak stands.geojson (albo pusty) w {directory}.")
    return {
        "scores": scores, "stands": stands,
        "regions": _read_json(directory / "regions.json"),
        "access_points": _read_json(directory / "access_points.json"),
        "manifest": _read_json(directory / "manifest.json"),
        "day": scores[0].get("day"),
    }
