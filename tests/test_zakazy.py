import pytest

from pipeline.zakazy import build_zakazy_query_url, check_periodic_ban, DEFAULT_ZAKAZY_URL


def test_build_zakazy_query_url_contains_point_and_geojson_format():
    url = build_zakazy_query_url(50.526944, 18.605000)
    assert url.startswith(DEFAULT_ZAKAZY_URL)
    assert "geometryType=esriGeometryPoint" in url
    assert "f=geojson" in url
    assert "18.605" in url and "50.526944" in url


def test_check_periodic_ban_true_when_features_present():
    def fake_call_api(lat, lon):
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}}]}

    assert check_periodic_ban(50.5, 18.6, call_api=fake_call_api) is True


def test_check_periodic_ban_false_when_no_features():
    def fake_call_api(lat, lon):
        return {"type": "FeatureCollection", "features": []}

    assert check_periodic_ban(50.5, 18.6, call_api=fake_call_api) is False
