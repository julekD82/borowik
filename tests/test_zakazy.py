import pytest

from pipeline.zakazy import build_zakazy_query_url, check_periodic_ban, DEFAULT_ZAKAZY_URL, ZakazyQueryError


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


def test_check_periodic_ban_raises_on_arcgis_error_response():
    # ArcGIS REST reports query errors as HTTP 200 with an {"error": ...}
    # body (confirmed live: querying a bogus layer id returns exactly this
    # shape) -- a mandatory legal mask must not silently read that as "no
    # ban" just because .get("features", []) is empty.
    def fake_call_api(lat, lon):
        return {"error": {"code": 400, "message": "Invalid or missing input parameters."}}

    with pytest.raises(ZakazyQueryError):
        check_periodic_ban(50.5, 18.6, call_api=fake_call_api)


def test_check_periodic_ban_raises_when_features_key_missing():
    def fake_call_api(lat, lon):
        return {"type": "SomethingUnexpected"}

    with pytest.raises(ZakazyQueryError):
        check_periodic_ban(50.5, 18.6, call_api=fake_call_api)
