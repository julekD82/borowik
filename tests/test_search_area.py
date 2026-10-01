import json
import math
import pathlib
from datetime import date

import geopandas as gpd
import pytest
import requests
from shapely.geometry import Point, box

from pipeline.search_area import (
    search_tiles, within_radius, fetch_search_stands, merge_frames,
    fetch_cached_gdos, fetch_cached_osm,
)
from pipeline.prepare_trip import run_trip_preparation, parse_args
from test_orchestrate import fake_weather_fetcher, fake_climatology_fetcher


def test_tiles_cover_disk_on_fixed_grid_and_radius_expands_selection():
    center, small = search_tiles(50.5318, 18.6055, 10)
    _, large = search_tiles(50.5318, 18.6055, 25)
    assert 1 < len(small) < len(large)
    assert set(small) <= set(large)
    for n0, e0, n1, e1 in large:
        assert n0 % 10000 == e0 % 10000 == 0
        assert n1-n0 == e1-e0 == 10000
        assert box(e0, n0, e1, n1).distance(center) < 25000
    tiles_union = gpd.GeoSeries([box(b[1], b[0], b[3], b[2]) for b in large], crs=2180).union_all()
    for angle in range(360):
        p = Point(center.x + 24999*math.cos(math.radians(angle)), center.y + 24999*math.sin(math.radians(angle)))
        assert tiles_union.covers(p)


def test_centroid_radius_filter_excludes_bbox_corners_preserves_geometry():
    center = Point(400000, 500000)
    stands = gpd.GeoDataFrame({"id": ["inside", "edge", "outside", "corner"]}, geometry=[
        box(400000, 500000, 400010, 500010),
        box(409900, 499900, 410100, 500100),
        box(410001, 499999, 410003, 500001),
        box(408900, 508900, 409100, 509100),
    ], crs=2180)
    result = within_radius(stands.to_crs(4326), center, 10.000001)
    assert result.id.tolist() == ["inside", "edge"]
    assert result.iloc[1].geometry.area == pytest.approx(40000, abs=.1)


def test_fetches_both_rdlp_and_deduplicates_across_tiles_and_caches_by_layer(tmp_path):
    tiles = [(500000, 400000, 510000, 410000), (500000, 410000, 510000, 420000)]
    rdlp = gpd.GeoDataFrame({"region_name": ["A", "B"]}, geometry=[box(399000,499000,415000,511000),box(405000,499000,421000,511000)], crs=2180)
    calls = []
    def fetch(layer, bbox):
        calls.append((layer, bbox))
        return gpd.GeoDataFrame({"adr_for": [layer], "a_year": [2026]}, geometry=[box(407000,502000,408000,503000)], crs=2180)
    stands, layers = fetch_search_stands(tiles, rdlp.to_crs(4326), tmp_path, fetch)
    assert len(calls) == 4
    assert len(stands) == len(layers) == 2
    assert len(list(tmp_path.rglob('*.parquet'))) == 4
    fetch_search_stands(tiles, rdlp, tmp_path, lambda *a: pytest.fail('cache missed'))


def test_source_failure_is_not_treated_as_empty(tmp_path):
    rdlp = gpd.GeoDataFrame({"region_name": ["A"]}, geometry=[box(0,0,20000,20000)], crs=2180)
    def broken(*args):
        raise RuntimeError('BDL unavailable')
    with pytest.raises(RuntimeError, match='BDL unavailable'):
        fetch_search_stands([(0,0,10000,10000)], rdlp, tmp_path, broken)
    assert not list(tmp_path.rglob('*.parquet'))


def test_fetch_cached_gdos_reuses_a_tile_across_calls(tmp_path):
    calls = []

    def gdos(bbox):
        calls.append(bbox)
        x = bbox[1] + 1  # distinct geometry per tile -- merge_frames dedups by geometry
        return gpd.GeoDataFrame({"id": [1]}, geometry=[box(x, x, x + 1, x + 1)], crs=2180)

    tiles = [(0, 0, 10000, 10000), (0, 10000, 10000, 20000)]
    result, failed = fetch_cached_gdos(tiles, tmp_path, gdos)
    assert len(calls) == 2
    assert len(result) == 2
    assert failed == []

    fetch_cached_gdos(tiles, tmp_path, lambda *a: pytest.fail("cache missed"))
    assert len(calls) == 2  # still 2 -- second call served entirely from cache


def test_fetch_cached_gdos_skips_a_tile_that_keeps_failing_and_reports_it(tmp_path, capsys):
    def flaky(bbox):
        if bbox[1] == 0:
            raise RuntimeError("network unavailable")
        return gpd.GeoDataFrame({"id": [1]}, geometry=[box(11, 11, 12, 12)], crs=2180)

    tiles = [(0, 0, 10000, 10000), (0, 10000, 10000, 20000)]
    result, failed = fetch_cached_gdos(tiles, tmp_path, flaky)

    assert failed == [(0, 0, 10000, 10000)]
    assert len(result) == 1  # the failing tile contributes no rows, not a crash
    assert "GDOS" in capsys.readouterr().out


def test_fetch_cached_gdos_does_not_cache_a_failed_tile(tmp_path):
    calls = []

    def eventually_succeeds(bbox):
        calls.append(bbox)
        if len(calls) == 1:
            raise RuntimeError("network unavailable")
        return gpd.GeoDataFrame({"id": [1]}, geometry=[box(11, 11, 12, 12)], crs=2180)

    tiles = [(0, 0, 10000, 10000)]
    _, failed = fetch_cached_gdos(tiles, tmp_path, eventually_succeeds)
    assert failed == tiles
    result, failed = fetch_cached_gdos(tiles, tmp_path, eventually_succeeds)
    assert failed == []
    assert len(result) == 1
    assert len(calls) == 2  # the failed attempt was not cached -- retried


def test_fetch_cached_gdos_fetches_only_a_new_tile(tmp_path):
    calls = []

    def gdos(bbox):
        calls.append(bbox)
        x = bbox[1] + 1
        return gpd.GeoDataFrame({"id": [1]}, geometry=[box(x, x, x + 1, x + 1)], crs=2180)

    fetch_cached_gdos([(0, 0, 10000, 10000)], tmp_path, gdos)
    fetch_cached_gdos([(0, 0, 10000, 10000), (0, 10000, 10000, 20000)], tmp_path, gdos)

    # tile (0,0,10000,10000) was already cached by the first call, so the
    # second call fetches only the new tile.
    assert calls == [(0, 0, 10000, 10000), (0, 10000, 10000, 20000)]


def _fake_osm_frames():
    return {
        "parking": gpd.GeoDataFrame({"osm_id": [1]}, geometry=[Point(1, 1)], crs=2180),
        "roads": gpd.GeoDataFrame({"osm_id": [2], "highway": ["track"]}, geometry=[Point(2, 2)], crs=2180),
        "places": gpd.GeoDataFrame({"osm_id": [3], "population": [10.0]}, geometry=[Point(3, 3)], crs=2180),
    }


def test_fetch_cached_osm_reuses_a_tile_across_calls(tmp_path):
    calls = []

    def osm(bbox, profile):
        calls.append(bbox)
        return _fake_osm_frames()

    tiles = [(0, 0, 10000, 10000)]
    profile = {"osm": {"road_highway_types": ["track"]}}
    result, failed = fetch_cached_osm(tiles, tmp_path, profile, osm)
    assert len(calls) == 1
    assert set(result) == {"parking", "roads", "places"}
    assert len(result["roads"]) == 1
    assert failed == []

    fetch_cached_osm(tiles, tmp_path, profile, lambda *a: pytest.fail("cache missed"))
    assert len(calls) == 1


def test_fetch_cached_osm_uses_a_separate_cache_per_profile(tmp_path):
    calls = []

    def osm(bbox, profile):
        calls.append(profile)
        return _fake_osm_frames()

    tiles = [(0, 0, 10000, 10000)]
    fetch_cached_osm(tiles, tmp_path, {"osm": {"road_highway_types": ["track"]}}, osm)
    fetch_cached_osm(tiles, tmp_path, {"osm": {"road_highway_types": ["path"]}}, osm)

    assert len(calls) == 2  # different profile config -> not treated as the same cache entry


def test_fetch_cached_osm_skips_a_tile_that_fails_and_reports_it(tmp_path, capsys):
    def flaky(bbox, profile):
        if bbox[1] == 0:
            raise RuntimeError("network unavailable")
        return _fake_osm_frames()

    tiles = [(0, 0, 10000, 10000)]
    result, failed = fetch_cached_osm(tiles, tmp_path, {"osm": {}}, flaky)

    assert failed == [(0, 0, 10000, 10000)]
    assert len(result["roads"]) == 0
    assert "OSM" in capsys.readouterr().out


def test_fetch_cached_osm_stops_calling_the_api_after_the_first_failure(tmp_path):
    # One failing tile means Overpass (or the network) is down for this
    # run -- calling the API again for the remaining uncached tiles would
    # just fail the same way and keep hammering an already-struggling
    # server (user request, 2026-09-24). They're reported as failed too,
    # without ever being attempted.
    calls = []

    def flaky(bbox, profile):
        calls.append(bbox)
        raise RuntimeError("network unavailable")

    tiles = [(0, 0, 10000, 10000), (0, 10000, 10000, 20000), (0, 20000, 10000, 30000)]
    result, failed = fetch_cached_osm(tiles, tmp_path, {"osm": {}}, flaky)

    assert len(calls) == 1  # only the first tile was ever attempted
    assert failed == tiles
    assert len(result["roads"]) == 0


def test_fetch_cached_osm_still_serves_a_cached_tile_after_a_later_give_up(tmp_path):
    calls = []

    def osm(bbox, profile):
        calls.append(bbox)
        return _fake_osm_frames()

    tile_a, tile_b, tile_c = (0, 0, 10000, 10000), (0, 10000, 10000, 20000), (0, 20000, 10000, 30000)
    fetch_cached_osm([tile_b], tmp_path, {"osm": {}}, osm)  # pre-cache tile_b
    calls.clear()

    def fails_then_would_succeed(bbox, profile):
        calls.append(bbox)
        raise RuntimeError("network unavailable")

    result, failed = fetch_cached_osm(
        [tile_a, tile_b, tile_c], tmp_path, {"osm": {}}, fails_then_would_succeed,
    )
    assert calls == [tile_a]  # tile_b came from cache, tile_c was never attempted
    assert failed == [tile_a, tile_c]
    assert len(result["roads"]) == 1  # tile_b's cached data still made it in


def test_fetch_cached_osm_does_not_cache_a_failed_tile(tmp_path):
    calls = []

    def eventually_succeeds(bbox, profile):
        calls.append(bbox)
        if len(calls) == 1:
            raise RuntimeError("network unavailable")
        return _fake_osm_frames()

    tiles = [(0, 0, 10000, 10000)]
    profile = {"osm": {}}
    _, failed = fetch_cached_osm(tiles, tmp_path, profile, eventually_succeeds)
    assert failed == tiles
    result, failed = fetch_cached_osm(tiles, tmp_path, profile, eventually_succeeds)
    assert failed == []
    assert len(result["roads"]) == 1
    assert len(calls) == 2  # the failed attempt was not cached -- retried


def test_merge_removes_repeated_osm_places_without_collapsing_different_geometry():
    frame = gpd.GeoDataFrame({"osm_id":[1,1],"population":[100,200]}, geometry=[Point(400000,500000),Point(400001,500001)], crs=2180)
    merged = merge_frames([frame, frame])
    assert len(merged) == 2
    assert merged.population.sum() == 300


@pytest.mark.parametrize('args', [
    ['--lat','nan','--lon','18'], ['--lat','91','--lon','18'],
    ['--lat','50','--lon','inf'], ['--lat','50','--lon','18','--radius-km','nan'],
])
def test_cli_rejects_nonfinite_or_invalid_coordinates(args):
    with pytest.raises(SystemExit):
        parse_args(args)


def configure_sources(monkeypatch):
    import pipeline.prepare_trip as trip
    import pipeline.radar as radar
    # _gdos_call_api/_osm_call_api pace every real call via time.sleep --
    # harmless in production, but real wall-clock delay against these
    # fakes otherwise (each GDOS tile call alone added 0.5s).
    monkeypatch.setattr(trip.time, 'sleep', lambda s: None)

    def _no_real_radar_http(url):
        raise AssertionError(
            f"real IMGW radar HTTP call attempted in a test ({url}) -- pass "
            "use_radar=False to run_trip_preparation instead of hitting the network"
        )
    monkeypatch.setattr(radar, '_default_http_get', _no_real_radar_http)
    rdlp = gpd.GeoDataFrame({"region_name": ["TEST"]}, geometry=[box(0,0,1000000,1000000)], crs=2180)
    monkeypatch.setattr(trip, 'fetch_rdlp_boundaries_cached', lambda *a: rdlp)
    def bdl(layer, bbox):
        n0,e0,n1,e1=bbox
        e,n=(e0+e1)/2,(n0+n1)/2
        return gpd.GeoDataFrame({
            'adr_for':[f'{e0}-{n0}'],'a_year':[2026],'area_type':['D-STAN'],
            'site_type':['BMSW'],'species_cd':['SO'],'part_cd':[10],'spec_age':[60],
        }, geometry=[box(e-100,n-100,e+100,n+100)],crs=2180)
    monkeypatch.setattr(trip, 'fetch_bdl', bdl)
    monkeypatch.setattr(trip, 'fetch_weather_raw', lambda points,days,**kw: fake_weather_fetcher(points,days))
    monkeypatch.setattr(trip, 'fetch_climatology_raw', lambda points,sy,ey,**kw: fake_climatology_fetcher(points,sy,ey))
    gd_calls, osm_calls = [], []
    def gdos(bbox):
        gd_calls.append(bbox)
        return gpd.GeoDataFrame(geometry=[],crs=2180)
    def osm(bbox,profile,**kw):
        osm_calls.append(bbox)
        return {name:gpd.GeoDataFrame(geometry=[],crs=2180) for name in ['parking','roads','places']}
    monkeypatch.setattr(trip, 'fetch_protected_areas', gdos)
    monkeypatch.setattr(trip, 'fetch_osm_features', osm)
    # Jedno zapytanie Overpass na kafel (model presji access_points): czesc modelowa deleguje do
    # podmienionego fetch_osm_features (w chwili wywolania -- testy podmieniaja go tez pozniej).
    monkeypatch.setattr(trip, 'fetch_osm_combined', lambda bbox, profile, cfg, call_api: (
        trip.fetch_osm_features(bbox, profile), {'roads': gpd.GeoDataFrame(geometry=[], crs=2180),
                                                 'gates': gpd.GeoDataFrame(geometry=[], crs=2180)}))
    monkeypatch.setattr(trip, 'check_periodic_ban', lambda *a: False)
    # Faza 3: zrodla punktow dostepu (BDL ArcGIS + Overpass) tez bez sieci
    monkeypatch.setattr(trip, '_default_bdl_get', lambda *a: {'features': []})
    monkeypatch.setattr(trip, '_default_overpass_call', lambda query: {'elements': []})
    return gd_calls, osm_calls


def test_real_pipeline_with_mocked_sources_expands_radius_and_exports_consistent_bundle(monkeypatch,tmp_path):
    # Grouping was disabled for a while (frontend toggle work reversed
    # that -- both the per-stand and region exports are always written
    # now, and the frontend chooses which to show).
    gd_calls, osm_calls = configure_sources(monkeypatch)
    outputs=[]
    for radius in [10,20]:
        out=tmp_path/str(radius)
        summary=run_trip_preparation(50.5318,18.6055,'2026-09-24',radius,'profiles/boletus_edulis.yaml',out,tmp_path/'cache',use_radar=False)
        scores=json.loads(summary['scores_path'].read_text(encoding='utf-8'))
        features=json.loads(summary['geojson_path'].read_text(encoding='utf-8'))['features']
        regions=json.loads(summary['regions_path'].read_text(encoding='utf-8'))
        ids={s['stand_id'] for s in scores}
        assert ids == {f['properties']['stand_id'] for f in features}
        assert summary['region_count'] == len(regions)
        for region in regions:
            assert set(region['stand_ids']) <= ids
            assert region['day'] == '2026-09-24'
        stands=gpd.read_parquet(summary['stands_path'])
        center,_=search_tiles(50.5318,18.6055,radius)
        assert (stands.geometry.centroid.distance(center) <= radius*1000).all()
        assert summary['radius_km'] == radius
        outputs.append(summary)
    assert outputs[1]['stand_count'] > outputs[0]['stand_count'] > 1
    # GDOS/OSM are now cached per tile (like BDL) -- the radius=20 run's
    # tiles are a superset of radius=10's (test_tiles_cover_disk_on_fixed_grid_
    # and_radius_expands_selection asserts this), so its tiles fully cover
    # every fetch across both runs; the smaller run's tiles are all reused
    # from cache on the second run, not re-fetched.
    assert len(gd_calls) == len(osm_calls) == outputs[1]['tile_count']
    assert all(b[2]-b[0] == b[3]-b[1] == 10000 for b in osm_calls)


def test_gdos_tile_failure_does_not_abort_the_run(monkeypatch,tmp_path,capsys):
    # GDOS/OSM per-tile failures are deliberately non-fatal (user request,
    # 2026-09-24): a tile that can't be fetched is skipped and reported,
    # not treated as a crash -- see fetch_cached_gdos/fetch_cached_osm in
    # pipeline/search_area.py and docs/CODEX-HANDOFF.md.
    configure_sources(monkeypatch)
    calls=[]
    def fail_once(*args):
        calls.append(args)
        if len(calls)==2:
            raise RuntimeError('GDOS unavailable')
        return gpd.GeoDataFrame(geometry=[],crs=2180)
    monkeypatch.setattr('pipeline.prepare_trip.fetch_protected_areas', fail_once)
    summary = run_trip_preparation(50.5318,18.6055,'2026-09-24',10,'profiles/boletus_edulis.yaml',tmp_path,tmp_path/'cache',use_radar=False)
    assert summary['scores_path'].exists()
    assert 'GDOS unavailable' in capsys.readouterr().out


def test_failure_mid_pipeline_preserves_previous_export(monkeypatch,tmp_path):
    # A genuinely fatal error (not a GDOS/OSM tile, and -- since plan 1.6 --
    # not a failing zakaz-okresowy check either, both now non-fatal, see
    # below and pipeline.mvp's own "blad" status tests) still aborts the run
    # and leaves whatever a previous, successful run already exported
    # untouched. A missing profile file is used here purely as a reliable
    # early fatal error, not because profile loading itself is the point.
    configure_sources(monkeypatch)
    marker=tmp_path/'scores_2026-09-24.json'
    marker.write_text('previous result')
    with pytest.raises(FileNotFoundError):
        run_trip_preparation(50.5318,18.6055,'2026-09-24',10,'profiles/does_not_exist.yaml',tmp_path,tmp_path/'cache',use_radar=False)
    assert marker.read_text() == 'previous result'


def test_failing_zakaz_check_no_longer_aborts_the_run(monkeypatch, tmp_path):
    # Plan 1.6 (spec S13.1): the zakaz-okresowy source failing is now a
    # survivable "blad" status (pipeline.mvp's own unit tests cover the
    # status value itself), not a run-aborting exception -- this is the
    # integration-level guarantee that run_trip_preparation as a whole
    # completes instead of propagating the checker's exception.
    configure_sources(monkeypatch)

    def fail_ban(*args):
        raise RuntimeError('Zakazy unavailable')
    monkeypatch.setattr('pipeline.prepare_trip.check_periodic_ban', fail_ban)
    summary = run_trip_preparation(
        50.5318, 18.6055, '2026-09-24', 10, 'profiles/boletus_edulis.yaml', tmp_path, tmp_path / 'cache',
        use_radar=False,
    )
    assert summary['stand_count'] > 0


def test_conditions_timeline_written_when_todays_weather_is_available(monkeypatch, tmp_path):
    # Plan A2 Plan-B: the fixed fake weather fetcher covers 2026-08-01..30
    # (test_orchestrate.fake_weather_fetcher) -- freeze date.today() inside
    # that range so the conditions block takes its success path, not the
    # UWAGA skip every other test in this file exercises via the real
    # (September+) wall-clock date.
    configure_sources(monkeypatch)

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 20)

    monkeypatch.setattr('pipeline.prepare_trip.date', FrozenDate)
    out = tmp_path / 'out'
    out.mkdir()
    stale = out / 'conditions_2026-09-24.json'
    stale.write_text('{"day": "stale"}', encoding='utf-8')

    summary = run_trip_preparation(50.5318, 18.6055, '2026-09-24', 10, 'profiles/boletus_edulis.yaml',
                                    out, tmp_path / 'cache', use_radar=False)

    assert summary['conditions_path'] is not None
    data = json.loads(pathlib.Path(summary['conditions_path']).read_text(encoding='utf-8'))
    assert data['day'] == '2026-09-24'
    assert isinstance(data['days'], list) and len(data['days']) == 7
    assert isinstance(data['summary'], str)


def test_conditions_skipped_and_stale_same_day_file_removed_when_weather_lacks_today(monkeypatch, tmp_path):
    # The fixed fake weather (2026-08-01..30) does not cover the real
    # wall-clock "today" -- the conditions block must skip gracefully
    # (UWAGA, not a crash) AND must not leave a stale same-day file behind.
    configure_sources(monkeypatch)
    out = tmp_path / 'out'
    out.mkdir()
    stale = out / 'conditions_2026-09-24.json'
    stale.write_text('{"day": "stale"}', encoding='utf-8')

    summary = run_trip_preparation(50.5318, 18.6055, '2026-09-24', 10, 'profiles/boletus_edulis.yaml',
                                    out, tmp_path / 'cache', use_radar=False)

    assert summary['conditions_path'] is None
    assert not stale.exists()


def test_conditions_fetch_network_error_does_not_abort_an_otherwise_successful_run(monkeypatch, tmp_path, capsys):
    # Review finding: the conditions-timeline weather fetch is a SEPARATE,
    # optional API call after run_poc has already succeeded -- a transient
    # network error there must not abort a trip preparation that otherwise
    # completed fine. Fails only the conditions call (forecast_days=7,
    # unique to it -- run_poc's own same-day search always requests
    # forecast_days=1), leaving run_poc's own weather fetch untouched.
    configure_sources(monkeypatch)

    def flaky_weather(points, past_days, forecast_days=1, **kw):
        if forecast_days == 7:
            raise requests.ConnectionError('network unavailable')
        return fake_weather_fetcher(points, past_days, forecast_days=forecast_days)
    monkeypatch.setattr('pipeline.prepare_trip.fetch_weather_raw', flaky_weather)

    summary = run_trip_preparation(50.5318, 18.6055, '2026-09-24', 10, 'profiles/boletus_edulis.yaml',
                                    tmp_path, tmp_path / 'cache', use_radar=False)

    assert summary['scores_path'].exists()
    assert summary['conditions_path'] is None
    assert 'UWAGA' in capsys.readouterr().out


def test_pipeline_with_access_points_exports_layers_manifest_and_card(monkeypatch, tmp_path):
    # Faza 3: BDL parking + fire road at every tile centre, Overpass unused --
    # the access model must drive P and be reported end to end.
    import pipeline.prepare_trip as trip
    configure_sources(monkeypatch)

    def bdl_get(service, type_name, bbox, start):
        n0, e0, n1, e1 = bbox
        e, n = (e0 + e1) / 2, (n0 + n1) / 2
        if 'turystyczna' in service:
            return {'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [e + 300, n]},
                                  'properties': {'objectid': int(e), 'tur_rec_pnt_cd': 'PARKING', 'nzw_ob': 'Test'}}]}
        return {'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString',
                              'coordinates': [[[e, n], [e + 800, n]]]},
                              'properties': {'objectid': int(e) + 1, 'nr_ppoz': '7'}}]}
    monkeypatch.setattr(trip, '_default_bdl_get', bdl_get)
    center, _ = search_tiles(50.5318, 18.6055, 10)

    def osm_with_town(bbox, profile, **kw):
        # jedna duza miejscowosc w centrum -- ludnosc wzmacnia punkty dostepu
        empty = gpd.GeoDataFrame(geometry=[], crs=2180)
        town = gpd.GeoDataFrame({'osm_id': [1], 'place': ['city'], 'population': [50000.0]},
                                geometry=[center], crs=2180)
        return {'parking': empty, 'roads': empty, 'places': town}
    monkeypatch.setattr(trip, 'fetch_osm_features', osm_with_town)
    summary = run_trip_preparation(50.5318, 18.6055, '2026-09-24', 10, 'profiles/boletus_edulis.yaml',
                                   tmp_path, tmp_path / 'cache', use_radar=False)
    points = json.loads(summary['access_points_path'].read_text(encoding='utf-8'))
    roads = json.loads(summary['forest_roads_path'].read_text(encoding='utf-8'))
    assert any(f['properties']['type'] == 'parking' and f['properties']['source'] == 'bdl' for f in points['features'])
    assert any(f['properties']['kind'] == 'fire' and f['properties']['fire_no'] == '7' for f in roads['features'])
    manifest = json.loads(summary['manifest_path'].read_text(encoding='utf-8'))
    assert manifest['pressure_model_used'] == 'access_points'
    assert manifest['access_points']['used'] is True
    assert manifest['access_points']['parking_bdl'] >= 1
    scores = json.loads(summary['scores_path'].read_text(encoding='utf-8'))
    assert any(s['P'] > 0 for s in scores) and {s['distance_method'] for s in scores} == {'access_points'}
    details = json.loads(summary['details_path'].read_text(encoding='utf-8'))
    with_access = [d for d in details if d['access']]
    assert with_access and with_access[0]['access']['d_parking_m'] is not None
    diagnostics = json.loads(summary['diagnostics_path'].read_text(encoding='utf-8'))
    assert 'pcontrib_parking' in diagnostics[0] and diagnostics[0]['pressure_model'] == 'access_points'


def test_pipeline_falls_back_to_gravity_and_says_so_when_no_access_points(monkeypatch, tmp_path):
    configure_sources(monkeypatch)   # zrodla dostepu puste
    summary = run_trip_preparation(50.5318, 18.6055, '2026-09-24', 10, 'profiles/boletus_edulis.yaml',
                                   tmp_path, tmp_path / 'cache', use_radar=False)
    manifest = json.loads(summary['manifest_path'].read_text(encoding='utf-8'))
    assert manifest['pressure_model_used'] == 'gravity'
    assert manifest['access_points'] == {'used': False, 'reason': 'brak_punktow_dostepu',
                                          'failed_tiles': {'bdl': 0, 'osm': 0}}
    assert summary['access_points_path'] is None
