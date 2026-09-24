import geopandas as gpd
import networkx as nx
import pytest
from shapely.geometry import LineString, Point

from pipeline.routing import build_road_graph, network_distance, nearest_entrance_distance


def _two_segment_roads():
    return gpd.GeoDataFrame(
        {"highway": ["track", "track"]},
        geometry=[
            LineString([(380000, 486000), (380100, 486000)]),
            LineString([(380100, 486000), (380100, 486100)]),  # shares (380100, 486000)
        ],
        crs="EPSG:2180",
    )


def test_build_road_graph_connects_shared_vertices():
    graph = build_road_graph(_two_segment_roads())
    assert graph.number_of_nodes() == 3
    assert nx.has_path(graph, (380000.0, 486000.0), (380100.0, 486100.0))


def test_build_road_graph_empty_input():
    roads = gpd.GeoDataFrame({"highway": []}, geometry=[], crs="EPSG:2180")
    graph = build_road_graph(roads)
    assert graph.number_of_nodes() == 0


def test_network_distance_along_two_segments():
    graph = build_road_graph(_two_segment_roads())
    distance = network_distance(graph, Point(380000, 486000), Point(380100, 486100))
    assert distance == pytest.approx(200.0)  # 100 + 100, exact vertex match, zero snap distance


def test_network_distance_returns_none_for_disconnected_components():
    roads = gpd.GeoDataFrame(
        {"highway": ["track", "track"]},
        geometry=[
            LineString([(380000, 486000), (380100, 486000)]),
            LineString([(500000, 600000), (500100, 600000)]),  # far away, disconnected
        ],
        crs="EPSG:2180",
    )
    graph = build_road_graph(roads)
    distance = network_distance(graph, Point(380000, 486000), Point(500000, 600000))
    assert distance is None


def test_network_distance_returns_none_for_empty_graph():
    graph = nx.Graph()
    assert network_distance(graph, Point(0, 0), Point(1, 1)) is None


def test_nearest_entrance_distance_picks_the_closer_entrance_regardless_of_status():
    roads = gpd.GeoDataFrame(
        {"highway": ["track"]},
        geometry=[LineString([(380000, 486000), (380200, 486000)])],
        crs="EPSG:2180",
    )
    graph = build_road_graph(roads)
    entrances = gpd.GeoDataFrame(
        {"status": ["potential", "confirmed"]},
        geometry=[Point(380000, 486000), Point(380200, 486000)],
        crs="EPSG:2180",
    )
    distance, status = nearest_entrance_distance(graph, Point(380000, 486000), entrances)
    assert distance == pytest.approx(0.0)
    assert status == "potential"


def test_nearest_entrance_distance_none_for_empty_entrances():
    graph = nx.Graph()
    empty = gpd.GeoDataFrame({"status": []}, geometry=[], crs="EPSG:2180")
    distance, status = nearest_entrance_distance(graph, Point(0, 0), empty)
    assert distance is None
    assert status is None
