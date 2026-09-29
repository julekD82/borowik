import geopandas as gpd
from shapely.geometry import box

from pipeline.habitat import load_profile
from pipeline.spatial_check import record_h

PROFILE = load_profile("profiles/boletus_edulis.yaml")


def _stands(rows):
    return gpd.GeoDataFrame(rows, geometry=[r.pop("geom") for r in rows], crs="EPSG:2180")


def _row(geom, **kw):
    base = {"area_type": "D-STAN", "spec_age": 80, "a_year": 2026, "species_cd": "SO", "part_cd": 10,
            "site_type": "BMSW", "adr_for": "X-1", "geom": geom}
    base.update(kw)
    return base


def test_masked_stand_counts_as_zero_and_is_weighted_by_area():
    good = _row(box(0, 0, 100, 100), adr_for="G")
    young = _row(box(100, 0, 200, 100), spec_age=5, adr_for="Y")  # maska wieku -> H = 0
    only_good = record_h(_stands([dict(good)]), 50, 50, 20, PROFILE)
    both = record_h(_stands([dict(good), dict(young)]), 100, 50, 30, PROFILE)
    assert only_good.forest and not only_good.masked and only_good.h > 0
    assert 0 < both.h < only_good.h                     # polowa bufora to wydzielenie z H = 0
    assert both.main_stand in ("G", "Y")


def test_all_masked_and_no_forest_cases():
    young = _row(box(0, 0, 100, 100), spec_age=5)
    r = record_h(_stands([young]), 50, 50, 20, PROFILE)
    assert r.forest and r.masked and r.h == 0.0
    meadow = _row(box(0, 0, 100, 100), area_type="ŁĄKA")
    assert record_h(_stands([meadow]), 50, 50, 20, PROFILE).forest is False


def test_unknown_site_code_is_flagged_only_for_mask_passing_stands():
    r = record_h(_stands([_row(box(0, 0, 100, 100), site_type="NIEZNANY")]), 50, 50, 20, PROFILE)
    assert r.unknown_code is True
