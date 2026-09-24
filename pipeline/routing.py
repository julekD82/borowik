import networkx as nx
from shapely.geometry import Point


def build_road_graph(roads_gdf) -> nx.Graph:
    """Nodes = every distinct vertex coordinate across all road/track/path
    LineStrings (rounded to 3 decimals -- millimetre precision in EPSG:2180
    metres -- so ways sharing an OSM node produce the same graph-node key);
    edges = consecutive vertex pairs within a LineString, weighted by
    Euclidean segment length. Roads that share a vertex (the normal case at
    OSM way intersections) are connected."""
    graph = nx.Graph()
    for geom in roads_gdf.geometry:
        if geom is None or geom.is_empty or geom.geom_type != "LineString":
            continue
        coords = [(round(x, 3), round(y, 3)) for x, y in geom.coords]
        for a, b in zip(coords[:-1], coords[1:]):
            length = Point(a).distance(Point(b))
            graph.add_edge(a, b, weight=length)
    return graph


def _nearest_graph_node(graph: nx.Graph, point):
    if graph.number_of_nodes() == 0:
        return None
    return min(graph.nodes, key=lambda n: (n[0] - point.x) ** 2 + (n[1] - point.y) ** 2)


def network_distance(graph: nx.Graph, point_a, point_b) -> float | None:
    """Shortest-path distance along the road/track graph between the graph
    nodes nearest point_a and point_b, plus the straight-line snap distance
    from each point to its nearest node (spec §5.5.2's own "snap to nearest
    node" simplification). None if the graph is empty or the two points
    fall in disconnected components -- callers must fall back to the
    euclidean estimate in that case, not treat None as zero."""
    node_a = _nearest_graph_node(graph, point_a)
    node_b = _nearest_graph_node(graph, point_b)
    if node_a is None or node_b is None:
        return None
    try:
        path_length = nx.shortest_path_length(graph, node_a, node_b, weight="weight")
    except nx.NetworkXNoPath:
        return None
    return path_length + point_a.distance(Point(node_a)) + point_b.distance(Point(node_b))


def nearest_entrance_distance(graph: nx.Graph, stand_centroid, entrances_gdf) -> tuple:
    """(distance_m, status) for whichever entrance in entrances_gdf has the
    smallest network_distance from stand_centroid -- the nearest one
    overall, not necessarily a confirmed one; status just reports what that
    nearest entrance is (spec §5.5.2: distance is about "wygoda dojazdu",
    confirmed/potential is a separate, honestly-labelled fact). (None, None)
    if entrances_gdf is empty or nothing is reachable.

    Runs a single single-source Dijkstra search from the stand's node and
    looks up each entrance's snapped node in the result, instead of calling
    network_distance (a fresh single-pair search) once per entrance -- on a
    real tile's track network (hundreds to thousands of edges) with dozens
    of candidate entrances, the naive per-entrance version re-explores
    largely the same graph repeatedly and was observed taking minutes per
    stand; this is the same total distances computed, just once per stand
    instead of once per (stand, entrance) pair."""
    node_a = _nearest_graph_node(graph, stand_centroid)
    if node_a is None or len(entrances_gdf) == 0:
        return (None, None)
    distances = nx.single_source_dijkstra_path_length(graph, node_a, weight="weight")
    snap_a = stand_centroid.distance(Point(node_a))
    best = None
    for _, row in entrances_gdf.iterrows():
        node_b = _nearest_graph_node(graph, row.geometry)
        if node_b is None or node_b not in distances:
            continue
        total = distances[node_b] + snap_a + row.geometry.distance(Point(node_b))
        if best is None or total < best[0]:
            best = (total, row["status"])
    return best if best is not None else (None, None)
