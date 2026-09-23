from pipeline.tiles import tile_bbox_2180, wfs_bbox_param


def test_tile_bbox_is_exactly_size_km_square():
    n_min, e_min, n_max, e_max = tile_bbox_2180(50.526944, 18.605000, size_km=10.0)
    assert e_max - e_min == 10_000.0
    assert n_max - n_min == 10_000.0


def test_tile_bbox_center_is_inside_bbox():
    lat, lon = 50.526944, 18.605000
    n_min, e_min, n_max, e_max = tile_bbox_2180(lat, lon, size_km=10.0)
    from pyproj import Transformer
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    e_center, n_center = transformer.transform(lon, lat)
    assert e_min < e_center < e_max
    assert n_min < n_center < n_max


def test_wfs_bbox_param_uses_n_e_n_e_axis_order():
    bbox = (486000.0, 380000.0, 496000.0, 390000.0)  # n_min, e_min, n_max, e_max
    param = wfs_bbox_param(bbox)
    assert param == "486000.0,380000.0,496000.0,390000.0,urn:ogc:def:crs:EPSG::2180"
