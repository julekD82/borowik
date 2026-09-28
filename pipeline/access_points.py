"""Plan wdrozenia Faza 3.1: budowa punktow dostepu i sieci drog lesnych.

Wejscie: surowe zrodla z `pipeline.access_data` (BDL parkingi/dojazdy
pozarowe, OSM drogi/szlabany, OSM parkingi z glownego cache), granica lasu
(`pipeline.entrances.compute_forest_boundary`) i punkty ludnosci GUS.
Wyjscie: `AccessSet` -- punkty (parking / entrance / gate / road_fallback /
settlement) oraz odcinki drog (publiczne, zamkniete drogi lesne, dojazdy
pozarowe BDL) z klasa nawierzchni. Atrakcyjnosc i presje liczy dopiero
`pipeline.access_pressure`.

Wszystko w EPSG:2180. Wszystkie progi w profilu (`pressure.access_points`).

Korekty wlasciciela (plan 3.1 "nadpisywanie przez korekty"): DataFrame
`overrides` z kolumnami `action` ("drop"/"add"), `type`, `x`, `y`, `radius_m`
-- "drop" usuwa punkty danego typu w promieniu, "add" dodaje punkt recznie
(source="wlasciciel"). Plik korekt nie istnieje w repo (dane wlasciciela sa
poza repozytorium); funkcja jest gotowa i przetestowana.
"""
from dataclasses import dataclass, field

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point, box
from shapely.ops import unary_union

from pipeline.entrances import _extract_points

POINT_TYPES = ("parking", "entrance", "gate", "road_fallback", "settlement")
SURFACE_CLASSES = ("hard", "gravel", "compacted", "unknown", "dirt")


@dataclass
class AccessSet:
    points: gpd.GeoDataFrame
    roads: gpd.GeoDataFrame
    counts: dict = field(default_factory=dict)


def _empty_points() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"point_id": [], "type": [], "source": [], "subtype": [], "name": [], "weight_pop": []},
        geometry=[], crs="EPSG:2180",
    )


def _empty_roads() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"kind": [], "surface_class": [], "source": [], "fire_no": [], "highway": []},
        geometry=[], crs="EPSG:2180",
    )


# --- klasyfikacja drog OSM --------------------------------------------------

def classify_surface(surface, tracktype, osm_cfg: dict) -> str:
    """hard / gravel / compacted / dirt / unknown. Tag `surface` ma pierwszenstwo;
    bez niego `tracktype` (grade1 utwardzona, grade2 kruszywo, grade3 ubita,
    grade4-5 gruntowa) -- plan 3.1. Brak obu = "unknown" (a nie "brak drogi")."""
    s = (surface or "").strip().lower() if isinstance(surface, str) else ""
    if s in osm_cfg["hard_surfaces"]:
        return "hard"
    if s in osm_cfg["gravel_surfaces"]:
        return "gravel"
    if s in osm_cfg["compacted_surfaces"]:
        return "compacted"
    if s in osm_cfg["dirt_surfaces"]:
        return "dirt"
    t = (tracktype or "").strip().lower() if isinstance(tracktype, str) else ""
    return {"grade1": "hard", "grade2": "gravel", "grade3": "compacted",
            "grade4": "dirt", "grade5": "dirt"}.get(t, "unknown")


def _norm(value) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def classify_road_access(highway, access, motor_vehicle, osm_cfg: dict) -> str:
    """"public" (dojazd autem dla kazdego) albo "closed" (wewnetrzna droga lesna,
    korytarz rowerowy). Droga publiczna = highway w `public_highway_types` i
    brak ograniczen w `access`/`motor_vehicle`; `track`/`service` sa zawsze
    "closed" (plan 3.1: asfalt w lesie nie znaczy dojazdu autem)."""
    if _norm(highway) not in osm_cfg["public_highway_types"]:
        return "closed"
    closed = set(osm_cfg["closed_access_values"])
    if _norm(access) in closed or _norm(motor_vehicle) in closed:
        return "closed"
    return "public"


def prepare_osm_roads(osm_roads: gpd.GeoDataFrame, cfg: dict) -> gpd.GeoDataFrame:
    """Dodaje kind (public/closed), surface_class, paved (do fallbacku)."""
    if osm_roads is None or not len(osm_roads):
        return _empty_roads().assign(paved=pd.Series(dtype=bool))
    osm_cfg = cfg["osm"]
    roads = osm_roads.copy()
    col = lambda name: roads[name] if name in roads else pd.Series([None] * len(roads), index=roads.index)
    roads["kind"] = [
        classify_road_access(h, a, m, osm_cfg)
        for h, a, m in zip(roads["highway"], col("access"), col("motor_vehicle"))
    ]
    roads["surface_class"] = [
        classify_surface(s, t, osm_cfg) for s, t in zip(col("surface"), col("tracktype"))
    ]
    default_paved = set(osm_cfg["paved_by_default_highway_types"])
    roads["paved"] = [
        (sc == "hard") or (sc == "unknown" and _norm(h) in default_paved)
        for sc, h in zip(roads["surface_class"], roads["highway"])
    ]
    roads["source"] = "osm"
    roads["fire_no"] = ""
    return roads[[c for c in ("kind", "surface_class", "paved", "source", "fire_no", "highway", "geometry")]]


# --- pomocnicze geometrie -----------------------------------------------------

def _prepared(geom):
    if geom is not None:
        shapely.prepare(geom)
    return geom


def forest_zone(forest_boundary, buffer_m: float):
    if forest_boundary is None or forest_boundary.is_empty:
        return None
    return _prepared(forest_boundary.buffer(buffer_m))


def _within(zone, geoms) -> np.ndarray:
    if zone is None or not len(geoms):
        return np.zeros(len(geoms), dtype=bool)
    return shapely.intersects(np.asarray(geoms, dtype=object), zone)


def dedupe_points(xy: np.ndarray, priority: np.ndarray, radius_m: float) -> np.ndarray:
    """Zachlanna deduplikacja: przegladamy punkty od najwyzszego priorytetu
    (mniejsza liczba = wyzszy), zostawiamy punkt, jesli w promieniu nie ma juz
    zostawionego. Zwraca indeksy zachowanych (w kolejnosci wejscia). Siatka
    o boku radius_m, wiec O(n)."""
    order = np.lexsort((np.arange(len(xy)), priority))
    kept, grid = [], {}
    r2 = radius_m * radius_m
    for i in order:
        x, y = xy[i]
        cx, cy = int(x // radius_m), int(y // radius_m)
        clash = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if (xy[j][0] - x) ** 2 + (xy[j][1] - y) ** 2 < r2:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                break
        if not clash:
            kept.append(i)
            grid.setdefault((cx, cy), []).append(i)
    return np.array(sorted(kept), dtype=int)


def _points_frame(geoms, ptype, source, subtype, name=None, prefix="", ids=None, pop=None):
    n = len(geoms)
    ids = ids if ids is not None else list(range(n))
    return gpd.GeoDataFrame({
        "point_id": [f"{prefix}{i}" for i in ids],
        "type": ptype, "source": source, "subtype": subtype,
        "name": name if name is not None else [""] * n,
        "weight_pop": pop if pop is not None else [np.nan] * n,
    }, geometry=list(geoms), crs="EPSG:2180")


# --- parkingi -------------------------------------------------------------------

def build_parkings(bdl_parkings, osm_parking, zone_200, cfg: dict) -> gpd.GeoDataFrame:
    """BDL (wszystkie) + OSM `amenity=parking` w <= 200 m od lasu; dedupe 100 m
    z pierwszenstwem BDL."""
    parts = []
    if bdl_parkings is not None and len(bdl_parkings):
        parts.append(_points_frame(
            list(bdl_parkings.geometry), "parking", "bdl", list(bdl_parkings["subtype"]),
            name=list(bdl_parkings["name"]), prefix="pk-bdl-", ids=list(bdl_parkings["source_id"]),
        ))
    if osm_parking is not None and len(osm_parking):
        keep = _within(zone_200, list(osm_parking.geometry))
        sel = osm_parking[keep]
        if len(sel):
            parts.append(_points_frame(
                list(sel.geometry), "parking", "osm", "amenity_parking",
                prefix="pk-osm-", ids=list(sel["osm_id"]),
            ))
    if not parts:
        return _empty_points()
    allp = pd.concat(parts, ignore_index=True)
    xy = np.array([(g.x, g.y) for g in allp.geometry])
    prio = np.where(allp["source"] == "bdl", 0, 1)
    kept = dedupe_points(xy, prio, cfg["parking_dedupe_m"])
    return gpd.GeoDataFrame(allp.iloc[kept].reset_index(drop=True), geometry="geometry", crs="EPSG:2180")


# --- wjazdy i szlabany ------------------------------------------------------------

def _crossings(boundary_line, roads: gpd.GeoDataFrame) -> list:
    """Punkty, w ktorych drogi przecinaja granice lasu (jak
    pipeline.entrances.find_entrance_points, ale z filtrem prepared -- tylko
    drogi realnie przecinajace granice licza przeciecie)."""
    if boundary_line is None or not len(roads):
        return []
    _prepared(boundary_line)
    geoms = np.asarray(list(roads.geometry), dtype=object)
    hit = shapely.intersects(geoms, boundary_line)
    out = []
    for geom in geoms[hit]:
        out.extend(_extract_points(geom.intersection(boundary_line)))
    return out


def _near(points, tree_geoms, distance: float) -> np.ndarray:
    """Dla kazdego punktu: czy istnieje geometria z tree_geoms w odleglosci <= distance."""
    if not len(points) or not len(tree_geoms):
        return np.zeros(len(points), dtype=bool)
    tree = shapely.STRtree(np.asarray(tree_geoms, dtype=object))
    buffers = shapely.buffer(np.asarray(points, dtype=object), distance)
    idx = tree.query(buffers, predicate="intersects")
    hit = np.zeros(len(points), dtype=bool)
    hit[np.unique(idx[0])] = True
    return hit


def _line_endpoints(geoms) -> list:
    pts = []
    for g in geoms:
        if g.geom_type == "LineString" and len(g.coords) >= 2:
            pts.append(Point(g.coords[0]))
            pts.append(Point(g.coords[-1]))
    return pts


def build_entrances(forest_boundary, zone, public_roads, forest_roads, gates, cfg: dict) -> gpd.GeoDataFrame:
    """Wjazdy do lasu (typ entrance) i szlabany (typ gate), plan 3.1.

    * `crossing_public` -- droga publiczna przecina granice lasu I <= 60 m od
      przeciecia zaczyna sie dukt/track/droga lesna (kontynuacja w lesie);
    * `crossing_track` -- dukt/droga lesna przecina granice, a droga publiczna
      jest <= 300 m od przeciecia (auto dojezdza do jego poczatku);
    * `junction` -- koniec duktu lezacy <= 20 m od drogi publicznej w strefie lasu;
    * szlaban (`gate`) -- OSM barrier na drodze lesnej (<= 15 m od niej),
      <= 300 m od drogi publicznej.
    Deduplikacja 150 m, szlaban ma pierwszenstwo przed wjazdem."""
    rows = []  # (Point, type, subtype, source, name, priority)
    forest_geoms = list(forest_roads.geometry) if forest_roads is not None and len(forest_roads) else []
    public_geoms = list(public_roads.geometry) if public_roads is not None and len(public_roads) else []

    if forest_boundary is not None and not forest_boundary.is_empty:
        boundary_line = forest_boundary.boundary
        if public_geoms:
            pts = _crossings(boundary_line, public_roads)
            ok = _near(pts, forest_geoms, cfg["entrance_continuation_m"])
            rows += [(p, "entrance", "crossing_public", "osm", "", 2) for p, k in zip(pts, ok) if k]
        if forest_geoms and public_geoms:
            pts = _crossings(boundary_line, forest_roads)
            ok = _near(pts, public_geoms, cfg["entrance_track_to_public_m"])
            rows += [(p, "entrance", "crossing_track", "osm", "", 3) for p, k in zip(pts, ok) if k]
    if forest_geoms and public_geoms:
        ends = _line_endpoints(forest_geoms)
        in_zone = _within(zone, ends) if zone is not None else np.zeros(len(ends), dtype=bool)
        ends_in = [p for p, z in zip(ends, in_zone) if z]
        ok = _near(ends_in, public_geoms, 20.0)
        rows += [(p, "entrance", "junction", "osm", "", 4) for p, k in zip(ends_in, ok) if k]
    if gates is not None and len(gates) and forest_geoms:
        gpts = list(gates.geometry)
        on_forest_road = _near(gpts, forest_geoms, 15.0)
        near_public = _near(gpts, public_geoms, cfg["gate_max_dist_to_public_road_m"])
        rows += [
            (p, "gate", "barrier", "osm", "", 1)
            for p, a, b in zip(gpts, on_forest_road, near_public) if a and b
        ]
    if not rows:
        return _empty_points()
    xy = np.array([(r[0].x, r[0].y) for r in rows])
    kept = dedupe_points(xy, np.array([r[5] for r in rows]), cfg["entrance_dedupe_m"])
    sel = [rows[i] for i in kept]
    frame = gpd.GeoDataFrame({
        "point_id": [f"{'gt' if r[1] == 'gate' else 'en'}-osm-{i}" for i, r in enumerate(sel)],
        "type": [r[1] for r in sel], "source": [r[3] for r in sel], "subtype": [r[2] for r in sel],
        "name": [r[4] for r in sel], "weight_pop": [np.nan] * len(sel),
    }, geometry=[r[0] for r in sel], crs="EPSG:2180")
    return frame


def build_fallback_points(forest_boundary, paved_public_roads, entrances, tiles, cfg: dict):
    """Kafle z lasem (>= `fallback_min_forest_km2`), w ktorych NIE wyznaczono
    zadnego wjazdu/szlabanu: zrodlem sa punkty co `fallback_road_sample_m` na
    drogach asfaltowych <= 200 m od lasu (typ road_fallback). Zwraca
    (punkty, liczba_kafli_fallback)."""
    if forest_boundary is None or forest_boundary.is_empty or paved_public_roads is None or not len(paved_public_roads):
        return _empty_points(), 0
    forest_near = _prepared(forest_boundary.buffer(cfg["fallback_road_max_dist_to_forest_m"]))
    ent_xy = (np.array([(g.x, g.y) for g in entrances.geometry]) if len(entrances) else np.empty((0, 2)))
    rows, fallback_tiles = [], 0
    step = cfg["fallback_road_sample_m"]
    for n_min, e_min, n_max, e_max in tiles:
        cell = box(e_min, n_min, e_max, n_max)
        if forest_boundary.intersection(cell).area < cfg.get("fallback_min_forest_km2", 1.0) * 1e6:
            continue
        has_entrance = bool(len(ent_xy)) and bool(np.any(
            (ent_xy[:, 0] >= e_min) & (ent_xy[:, 0] < e_max) & (ent_xy[:, 1] >= n_min) & (ent_xy[:, 1] < n_max)
        ))
        if has_entrance:
            continue
        fallback_tiles += 1
        for geom in paved_public_roads.geometry:
            if geom.is_empty or not geom.intersects(cell) or not forest_near.intersects(geom):
                continue
            seg = geom.intersection(cell)
            parts = [seg] if seg.geom_type == "LineString" else list(getattr(seg, "geoms", []))
            for part in parts:
                if part.geom_type != "LineString" or part.length == 0:
                    continue
                for d in np.arange(0.0, part.length, step):
                    p = part.interpolate(d)
                    if forest_near.contains(p):
                        rows.append(p)
    if not rows:
        return _empty_points(), fallback_tiles
    xy = np.array([(p.x, p.y) for p in rows])
    kept = dedupe_points(xy, np.zeros(len(xy)), step * 0.5)
    sel = [rows[i] for i in kept]
    return _points_frame(sel, "road_fallback", "osm", "asfalt_przy_lesie", prefix="rf-osm-"), fallback_tiles


# --- osiedla ---------------------------------------------------------------------

def build_settlements(pop_points, zone_200, cfg: dict) -> gpd.GeoDataFrame:
    """Oczka GUS z ludnoscia > 0, ktorych kwadrat 1 x 1 km siega <= 200 m do lasu.
    Punkt = srodek oczka (dane GUS sa w siatce 1 km), weight_pop = ludnosc."""
    if pop_points is None or not len(pop_points) or zone_200 is None:
        return _empty_points()
    pts = pop_points[pop_points["population"] > 0]
    cells = shapely.box(pts.geometry.x.values - 500, pts.geometry.y.values - 500,
                        pts.geometry.x.values + 500, pts.geometry.y.values + 500)
    hit = shapely.intersects(cells, zone_200)
    sel = pts[hit]
    if not len(sel):
        return _empty_points()
    return _points_frame(
        list(sel.geometry), "settlement", "gus", "oczko_1km", prefix="st-gus-",
        ids=list(range(len(sel))), pop=list(sel["population"].astype(float)),
    )


# --- korekty wlasciciela ------------------------------------------------------------

def apply_overrides(points: gpd.GeoDataFrame, overrides: pd.DataFrame | None) -> gpd.GeoDataFrame:
    if overrides is None or not len(overrides):
        return points
    points = points.copy()
    for _, row in overrides[overrides["action"] == "drop"].iterrows():
        near = points.geometry.distance(Point(row["x"], row["y"])) <= float(row["radius_m"])
        points = points[~(near & (points["type"] == row["type"]))]
    adds = []
    for i, row in overrides[overrides["action"] == "add"].reset_index(drop=True).iterrows():
        adds.append(_points_frame([Point(row["x"], row["y"])], row["type"], "wlasciciel", "korekta",
                                  prefix="ov-", ids=[i]))
    if adds:
        points = pd.concat([points] + adds, ignore_index=True)
    return gpd.GeoDataFrame(points.reset_index(drop=True), geometry="geometry", crs="EPSG:2180")


# --- calosc -------------------------------------------------------------------------

def build_access_set(*, forest_boundary, sources: dict, osm_parking, pop_points, tiles, cfg: dict,
                      overrides: pd.DataFrame | None = None) -> AccessSet:
    """Sklada punkty i drogi ze wszystkich zrodel i liczy liczniki do manifestu."""
    zone_200 = forest_zone(forest_boundary, cfg["parking_osm_max_dist_to_forest_m"])
    zone_roads = forest_zone(forest_boundary, cfg["forest_buffer_m"])

    osm_roads = prepare_osm_roads(sources.get("osm_roads"), cfg)
    if len(osm_roads) and zone_roads is not None:
        osm_roads = osm_roads[_within(zone_roads, list(osm_roads.geometry))].reset_index(drop=True)
    elif zone_roads is None:
        osm_roads = osm_roads.iloc[0:0]
    public = osm_roads[osm_roads["kind"] == "public"] if len(osm_roads) else osm_roads
    closed = osm_roads[osm_roads["kind"] == "closed"] if len(osm_roads) else osm_roads

    fire = sources.get("fire_roads")
    if fire is not None and len(fire):
        fire = fire.assign(kind="fire", surface_class="unknown", source="bdl_ppoz", highway="", paved=False)
        fire = fire[["kind", "surface_class", "paved", "source", "fire_no", "highway", "geometry"]]
    else:
        fire = _empty_roads().assign(paved=pd.Series(dtype=bool))

    forest_roads = pd.concat([closed, fire], ignore_index=True) if (len(closed) or len(fire)) else fire

    parkings = build_parkings(sources.get("bdl_parkings"), osm_parking, zone_200, cfg)
    entrances = build_entrances(forest_boundary, zone_roads, public, forest_roads, sources.get("osm_gates"), cfg)
    paved_public = public[public["paved"]] if len(public) else public
    fallback, fallback_tiles = build_fallback_points(forest_boundary, paved_public, entrances, tiles, cfg)
    settlements = build_settlements(pop_points, zone_200, cfg)

    parts = [p for p in (parkings, entrances, fallback, settlements) if len(p)]
    points = (gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:2180")
              if parts else _empty_points())
    points = apply_overrides(points, overrides)

    road_parts = [r for r in (osm_roads, fire) if len(r)]
    roads = (gpd.GeoDataFrame(pd.concat(road_parts, ignore_index=True), geometry="geometry", crs="EPSG:2180")
             if road_parts else _empty_roads())

    counts = {
        "points_by_type_source": {
            f"{t}/{s}": int(n) for (t, s), n in points.groupby(["type", "source"]).size().items()
        } if len(points) else {},
        "parking_bdl": int(((points["type"] == "parking") & (points["source"] == "bdl")).sum()) if len(points) else 0,
        "parking_osm": int(((points["type"] == "parking") & (points["source"] == "osm")).sum()) if len(points) else 0,
        "entrance": int((points["type"] == "entrance").sum()) if len(points) else 0,
        "gate": int((points["type"] == "gate").sum()) if len(points) else 0,
        "road_fallback": int((points["type"] == "road_fallback").sum()) if len(points) else 0,
        "settlement": int((points["type"] == "settlement").sum()) if len(points) else 0,
        "fallback_tile_count": int(fallback_tiles),
        "roads_by_kind": {k: int(n) for k, n in roads.groupby("kind").size().items()} if len(roads) else {},
        "osm_public_roads_paved": int(len(paved_public)),
    }
    return AccessSet(points=points, roads=roads, counts=counts)
