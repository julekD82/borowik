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
    if entrances_gdf is empty or nothing is reachable."""
    best = None
    for _, row in entrances_gdf.iterrows():
        distance = network_distance(graph, stand_centroid, row.geometry)
        if distance is not None and (best is None or distance < best[0]):
            best = (distance, row["status"])
    return best if best is not None else (None, None)
