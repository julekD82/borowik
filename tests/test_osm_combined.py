"""Jedno zapytanie Overpass na kafel zamiast dwoch (presja/wjazdy + warstwy dostepu).

Atrapa Overpass naprawde wykonuje warunki z zapytania na wspolnym zbiorze elementow, wiec test
porownuje polaczone zapytanie z dwoma dotychczasowymi tak, jak zrobilby to serwer."""
import re

import pandas as pd

from pipeline.access_data import combined_osm_fetcher, fetch_access_osm, fetch_osm_combined, load_access_sources
from pipeline.habitat import load_profile
from pipeline.osm import fetch_osm_features
from pipeline.search_area import fetch_cached_osm

PROFILE = load_profile("profiles/boletus_edulis.yaml")
CFG = PROFILE["pressure"]["access_points"]
TILE = (300000, 470000, 310000, 480000)


def _way(i, tags):
    return {"type": "way", "id": i, "tags": tags,
            "geometry": [{"lat": 50.5 + i * 1e-4, "lon": 18.6}, {"lat": 50.5 + i * 1e-4, "lon": 18.601}]}


def _node(i, tags):
    return {"type": "node", "id": i, "lat": 50.5 + i * 1e-4, "lon": 18.6, "tags": tags}


ELEMENTS = [
    _node(1, {"amenity": "parking", "name": "Leśny"}),
    _way(2, {"amenity": "parking"}),
    _way(3, {"highway": "track", "surface": "gravel", "tracktype": "grade2"}),
    _way(4, {"highway": "residential", "name": "Leśna"}),
    _way(5, {"highway": "service"}),                          # tylko warstwy dostepu
    _way(6, {"highway": "service", "service": "driveway"}),   # wykluczony podtyp
    _way(7, {"highway": "track", "service": "parking_aisle"}),  # presja tak, dostep nie
    _way(8, {"highway": "footway"}),                          # zadne zapytanie
    _node(9, {"place": "village", "name": "Łaziska", "population": "800"}),
    _node(10, {"place": "isolated_dwelling"}),                 # zadne zapytanie
    _node(11, {"barrier": "gate", "access": "forestry"}),
    _node(12, {"barrier": "lift_gate"}),
    _node(13, {"barrier": "bollard"}),                        # zadne zapytanie
    _node(14, {"highway": "crossing"}),                       # wezel, nie droga
]


def _matches(tags, key, op, value):
    if op == "=":
        return tags.get(key) == value
    hit = key in tags and re.search(value, tags[key]) is not None
    return hit if op == "~" else not hit


class FakeOverpass:
    def __init__(self):
        self.queries = []

    def __call__(self, query):
        self.queries.append(query)
        out, seen = [], set()
        for kind, filters in re.findall(r'(node|way)((?:\[[^\]]*\])+)\([^)]*\);', query):
            conditions = re.findall(r'\["([^"]+)"(=|~|!~)"([^"]*)"\]', filters)
            for el in ELEMENTS:
                key = (el["type"], el["id"])
                if el["type"] == kind and key not in seen and all(
                        _matches(el.get("tags", {}), *c) for c in conditions):
                    seen.add(key)
                    out.append(el)
        return {"elements": out}


def _canonical(frame):
    return frame.assign(_wkb=frame.geometry.to_wkb()).sort_values(["osm_id", "_wkb"]).reset_index(drop=True)


def _assert_same(a, b):
    assert set(a) == set(b)
    for name in a:
        left, right = _canonical(a[name]), _canonical(b[name])
        assert list(left["osm_id"]) == list(right["osm_id"]), name
        pd.testing.assert_frame_equal(
            pd.DataFrame(left.drop(columns="geometry")), pd.DataFrame(right.drop(columns="geometry")), check_dtype=False)


def test_one_combined_query_gives_exactly_the_data_of_both_separate_queries():
    separate = FakeOverpass()
    model_old = fetch_osm_features(TILE, PROFILE, call_api=separate)
    access_old = fetch_access_osm(TILE, CFG, separate)
    combined = FakeOverpass()
    model_new, access_new = fetch_osm_combined(TILE, PROFILE, CFG, combined)

    assert len(separate.queries) == 2 and len(combined.queries) == 1
    _assert_same(model_new, model_old)
    _assert_same(access_new, access_old)
    # sanity: zbior testowy rozroznia oba zapytania
    assert set(model_old["roads"]["osm_id"]) == {3, 4, 7} and set(access_old["roads"]["osm_id"]) == {3, 4, 5}
    assert set(access_old["gates"]["osm_id"]) == {11, 12} and set(model_old["parking"]["osm_id"]) == {1, 2}


def test_access_step_reads_the_tile_saved_by_the_combined_fetch(tmp_path):
    overpass = FakeOverpass()
    fetch_cached_osm([TILE], tmp_path, PROFILE, combined_osm_fetcher(tmp_path, CFG, overpass))
    assert len(overpass.queries) == 1

    def no_more_overpass(query):
        raise AssertionError("krok dostepu nie powinien pytac Overpass drugi raz")

    sources = load_access_sources([TILE], tmp_path, CFG, no_more_overpass, bdl_get=lambda *a: {"features": []})
    assert sources["cache_hits"]["osm"] == 1 and sources["failed"]["osm"] == []
    assert set(sources["osm_roads"]["osm_id"]) == {3, 4, 5} and set(sources["osm_gates"]["osm_id"]) == {11, 12}
