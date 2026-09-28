"""Plan wdrozenia Faza 3.2-3.4: atrakcyjnosc punktow dostepu i presja wydzielen.

    A_k       = sum_j Pop_j * g(d_jk)               (ludnosc GUS w zasiegu punktu)
    A_norm_k  = A_k / (A_k + a_half)                 (normalizacja BEZWZGLEDNA)
    raw       = sum_t w_t * sum_k A_norm_k * kern(d_k / R_t)
    P         = 1 - exp(-raw / S)

`g` i `kern` to to samo gladkie jadro k(x) = max(0, 1-x^2)^2 (bez twardej
granicy). Droga lesna dziedziczy atrakcyjnosc po SIECI drog:
A_odcinek = max_k A_norm_k * 0.5^(d_siec_k / network_half) -- liczone jako
najkrotsza sciezka z przesunieciami startowymi (max_k A h(d) == min_k
(offset_k + d), offset_k = lambda ln(1/A_k), lambda = network_half/ln 2),
potem mnoznik nawierzchni. Do presji wydzielenia korytarz wchodzi jako JEDEN
skladnik (maksimum po probkach drogi w zasiegu poprzecznym), bo dwie
rownolegle drogi obok siebie nie oznaczaja dwa razy wiecej rowerzystow.

Wszystkie parametry w profilu (`pressure.access_points`), NIESKALIBROWANE.
"""
from dataclasses import dataclass, field
import math

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from pipeline.access_points import AccessSet

CORRIDOR_SOURCE_TYPES = ("parking", "entrance", "gate", "road_fallback")
POINT_TYPES_FOR_PRESSURE = ("parking", "entrance", "gate", "road_fallback", "settlement")
# Klasy atrakcyjnosci do UI (niska / srednia / wysoka) -- progi A_norm.
ATTRACTIVENESS_CLASS_EDGES = (0.1, 0.3)


def kernel(d, radius):
    """k(d) = max(0, 1 - (d/R)^2)^2, wektorowo; 0 poza zasiegiem."""
    x = np.asarray(d, dtype=float) / radius
    return np.where(x < 1.0, (1.0 - x * x) ** 2, 0.0)


def attractiveness_class(value: float) -> str:
    low, high = ATTRACTIVENESS_CLASS_EDGES
    return "niska" if value < low else "srednia" if value < high else "wysoka"


@dataclass
class AccessModel:
    points: gpd.GeoDataFrame            # + A, A_norm
    roads: gpd.GeoDataFrame             # + attractiveness, road_id
    corridor_xy: np.ndarray
    corridor_a: np.ndarray
    corridor_road: np.ndarray           # indeks w roads
    cfg: dict
    counts: dict = field(default_factory=dict)


def _xy(geoms) -> np.ndarray:
    return np.array([(g.x, g.y) for g in geoms], dtype=float).reshape(-1, 2)


def compute_attractiveness(points: gpd.GeoDataFrame, pop_xy: np.ndarray, pop_values: np.ndarray,
                            cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """(A, A_norm) dla kazdego punktu. Ludnosc w zasiegu
    `attractiveness_range_km` typu punktu, jadro k; A_norm z `a_half` typu."""
    a = np.zeros(len(points))
    a_norm = np.zeros(len(points))
    if not len(points) or not len(pop_xy):
        return a, a_norm
    pop_tree = cKDTree(pop_xy)
    for ptype, tcfg in cfg["types"].items():
        idx = np.where(points["type"].values == ptype)[0]
        if not len(idx):
            continue
        radius = tcfg["attractiveness_range_km"] * 1000.0
        pt_tree = cKDTree(_xy(points.geometry.iloc[idx]))
        m = pop_tree.sparse_distance_matrix(pt_tree, radius, output_type="coo_matrix")
        weights = pop_values[m.row] * kernel(m.data, radius)
        a[idx] = np.bincount(m.col, weights=weights, minlength=len(idx))
        a_norm[idx] = a[idx] / (a[idx] + tcfg["a_half"])
    return a, a_norm


def _node(x, y):
    return (round(float(x)), round(float(y)))


def propagate_corridor(points: gpd.GeoDataFrame, a_norm: np.ndarray, roads: gpd.GeoDataFrame,
                        cfg: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Atrakcyjnosc odcinkow drog lesnych (kind closed/fire) po sieci.

    Zwraca (attractiveness_per_road[len(roads)], corridor_xy, corridor_a,
    corridor_road). Odcinki drog publicznych dostaja NaN (sa zrodlem, nie
    korytarzem). Wezly sieci = wierzcholki zaokraglone do 1 m; drogi
    przecinajace sie bez wspolnego wierzcholka nie sa laczone (uproszczenie)."""
    n_roads = len(roads)
    per_road = np.full(n_roads, np.nan)
    kinds = roads["kind"].values if n_roads else np.array([])
    corridor_rows = np.where(np.isin(kinds, ("closed", "fire")))[0] if n_roads else np.array([], dtype=int)
    empty = (per_road, np.empty((0, 2)), np.empty(0), np.empty(0, dtype=int))
    if not len(corridor_rows):
        return empty
    half_m = cfg["network_half_km"] * 1000.0
    lam = half_m / math.log(2.0)
    graph = nx.Graph()
    edge_road = {}
    for r in corridor_rows:
        geom = roads.geometry.iloc[r]
        if geom.geom_type != "LineString":
            continue
        coords = list(geom.coords)
        for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
            u, v = _node(x1, y1), _node(x2, y2)
            if u == v:
                continue
            length = math.hypot(x2 - x1, y2 - y1)
            if graph.has_edge(u, v):
                continue
            graph.add_edge(u, v, weight=length)
            edge_road[(u, v)] = (r, x1, y1, x2, y2, length)
    if graph.number_of_nodes() == 0:
        return empty

    nodes = list(graph.nodes)
    node_tree = cKDTree(np.array(nodes, dtype=float))
    src_mask = np.isin(points["type"].values, CORRIDOR_SOURCE_TYPES) & (a_norm > 0)
    super_src = ("S", "S")
    snap_max = cfg["snap_max_m"]
    pxy = _xy(points.geometry)
    attached = 0
    for i in np.where(src_mask)[0]:
        dist, j = node_tree.query(pxy[i])
        if dist > snap_max:
            continue
        offset = lam * math.log(1.0 / a_norm[i]) + float(dist)
        u = nodes[j]
        if graph.has_edge(super_src, u):
            graph[super_src][u]["weight"] = min(graph[super_src][u]["weight"], offset)
        else:
            graph.add_edge(super_src, u, weight=offset)
        attached += 1
    if attached == 0:
        return empty
    dist_to = nx.single_source_dijkstra_path_length(graph, super_src)
    potential = {n: 2.0 ** (-d / half_m) for n, d in dist_to.items() if n != super_src}

    mult = cfg["surface_multiplier"]
    surface = roads["surface_class"].values
    sample_m = cfg["corridor_sample_m"]
    cell = sample_m / 2.0
    best = {}  # komorka -> (a, x, y, road)
    for (u, v), (r, x1, y1, x2, y2, length) in edge_road.items():
        pu, pv = potential.get(u, 0.0), potential.get(v, 0.0)
        if pu == 0.0 and pv == 0.0:
            continue
        s = length / 2.0
        a_mid = max(pu * 2.0 ** (-s / half_m), pv * 2.0 ** (-(length - s) / half_m))
        a_seg = a_mid * mult.get(surface[r], mult["unknown"])
        per_road[r] = a_seg if np.isnan(per_road[r]) else max(per_road[r], a_seg)
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        key = (int(mx // cell), int(my // cell))
        if key not in best or a_seg > best[key][0]:
            best[key] = (a_seg, mx, my, r)
    # Drogi kwalifikujace sie jako korytarz, ale nieosiagniete z zadnego punktu: 0, nie NaN.
    unreached = np.isnan(per_road) & np.isin(kinds, ("closed", "fire"))
    per_road[unreached] = 0.0
    if not best:
        return per_road, empty[1], empty[2], empty[3]
    arr = np.array(list(best.values()))
    return per_road, arr[:, 1:3], arr[:, 0], arr[:, 3].astype(int)


def build_access_model(access: AccessSet, pop_xy: np.ndarray, pop_values: np.ndarray, cfg: dict) -> AccessModel:
    points = access.points.copy()
    a, a_norm = compute_attractiveness(points, pop_xy, pop_values, cfg)
    points["A"] = a
    points["A_norm"] = a_norm
    roads = access.roads.copy()
    per_road, cxy, ca, croad = propagate_corridor(points, a_norm, roads, cfg)
    roads["attractiveness"] = per_road
    roads["road_id"] = [f"rd-{i}" for i in range(len(roads))]
    counts = dict(access.counts)
    counts["corridor_sample_count"] = int(len(ca))
    counts["corridor_roads_reached"] = int(np.sum(per_road > 0)) if len(per_road) else 0
    return AccessModel(points=points, roads=roads, corridor_xy=cxy, corridor_a=ca, corridor_road=croad,
                       cfg=cfg, counts=counts)


def _nearest_distance(geoms, query_xy: np.ndarray) -> np.ndarray:
    if not len(geoms) or not len(query_xy):
        return np.full(len(query_xy), np.nan)
    tree = shapely.STRtree(np.asarray(geoms, dtype=object))
    qpts = shapely.points(query_xy[:, 0], query_xy[:, 1])
    _, dist = tree.query_nearest(qpts, return_distance=True, all_matches=False)
    # query_nearest zwraca po jednym trafieniu na punkt wejsciowy, w kolejnosci wejscia
    return np.asarray(dist, dtype=float)


def compute_access_pressure(centroids_xy: np.ndarray, model: AccessModel) -> pd.DataFrame:
    """Presja per wydzielenie (kolejnosc jak `centroids_xy`).

    Kolumny: access_raw, P, pcontrib_<typ> (wklad kazdego typu, w tym
    forest_road), top_point_id / top_point_type (element o najwiekszym
    wkladzie), oraz odleglosci dla karty: d_parking_m, d_entrance_m
    (wjazd lub szlaban), d_hard_forest_road_m (utwardzona droga lesna)."""
    cfg = model.cfg
    n = len(centroids_xy)
    stand_tree = cKDTree(centroids_xy) if n else None
    contrib = {t: np.zeros(n) for t in list(POINT_TYPES_FOR_PRESSURE) + ["forest_road"]}
    best_val = np.zeros(n)
    best_id = np.array([""] * n, dtype=object)
    best_type = np.array([""] * n, dtype=object)

    def _consider(stand_idx, values, ids, ptype):
        # dla kazdego wydzielenia zapamietaj najwiekszy wklad
        if not len(stand_idx):
            return
        df = pd.DataFrame({"s": stand_idx, "v": values, "id": ids})
        top = df.loc[df.groupby("s")["v"].idxmax()]
        better = top["v"].values > best_val[top["s"].values]
        s = top["s"].values[better]
        best_val[s] = top["v"].values[better]
        best_id[s] = top["id"].values[better]
        best_type[s] = ptype

    pts = model.points
    if n and len(pts):
        for ptype in POINT_TYPES_FOR_PRESSURE:
            tcfg = cfg["types"][ptype]
            sel = np.where(pts["type"].values == ptype)[0]
            if not len(sel):
                continue
            pt_tree = cKDTree(_xy(pts.geometry.iloc[sel]))
            m = stand_tree.sparse_distance_matrix(pt_tree, tcfg["range_m"], output_type="coo_matrix")
            vals = tcfg["weight"] * pts["A_norm"].values[sel][m.col] * kernel(m.data, tcfg["range_m"])
            contrib[ptype] = np.bincount(m.row, weights=vals, minlength=n)
            _consider(m.row, vals, pts["point_id"].values[sel][m.col], ptype)
    if n and len(model.corridor_a):
        fcfg = cfg["types"]["forest_road"]
        c_tree = cKDTree(model.corridor_xy)
        m = stand_tree.sparse_distance_matrix(c_tree, fcfg["range_m"], output_type="coo_matrix")
        vals = fcfg["weight"] * model.corridor_a[m.col] * kernel(m.data, fcfg["range_m"])
        c = np.zeros(n)
        np.maximum.at(c, m.row, vals)
        contrib["forest_road"] = c
        road_ids = model.roads["road_id"].values[model.corridor_road[m.col]]
        _consider(m.row, vals, road_ids, "forest_road")

    raw = sum(contrib.values())
    p = 1.0 - np.exp(-raw / cfg["saturation_s"])
    out = pd.DataFrame({"access_raw": raw, "P": p})
    for t, v in contrib.items():
        out[f"pcontrib_{t}"] = v
    out["top_point_id"] = best_id
    out["top_point_type"] = best_type

    if n:
        pts_types = pts["type"].values if len(pts) else np.array([])
        geoms = list(pts.geometry) if len(pts) else []
        out["d_parking_m"] = _nearest_distance([g for g, t in zip(geoms, pts_types) if t == "parking"], centroids_xy)
        out["d_entrance_m"] = _nearest_distance(
            [g for g, t in zip(geoms, pts_types) if t in ("entrance", "gate")], centroids_xy)
        roads = model.roads
        hard = roads[(roads["kind"].isin(["closed", "fire"])) & (roads["surface_class"] == "hard")] if len(roads) else roads
        out["d_hard_forest_road_m"] = _nearest_distance(list(hard.geometry), centroids_xy)
    else:
        for col in ("d_parking_m", "d_entrance_m", "d_hard_forest_road_m"):
            out[col] = np.empty(0)
    return out
