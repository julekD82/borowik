import geopandas as gpd
import pytest
from shapely.geometry import box

from pipeline.tie_break import (
    TieBreakRaw, load_tie_break_raw, compute_tie_break, tie_break_for_stand, veg_cover_label,
)

_SUBAREA_HEADER = "arodes_int_num\ta_year\tarea_type_cd\tsite_type_cd\tmoisture_cd\tdegradation_cd\tsoil_subtype_cd\tplant_comm_cd\tstand_struct_cd\tforest_func_cd\tsilviculture_cd\trotation_age\tsub_area\tveg_cover_cd\tdamage_degree\tcause_cd\n"
_STOREY_HEADER = "arodes_int_num\ta_year\tdensity_cd\tmixture_cd\tstanddensity_index\ttree_stock_cd\tst_rank_order_act\tstorey_cd\n"


def _write_package(package_dir, subarea_rows, subarea_text, storey_text):
    package_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(subarea_rows, geometry=[box(0, 0, 100, 100)] * len(subarea_rows), crs="EPSG:2180")
    gdf.to_file(package_dir / "G_SUBAREA.shp")
    (package_dir / "f_subarea.txt").write_text(subarea_text, encoding="utf-8")
    (package_dir / "f_arod_storey.txt").write_text(storey_text, encoding="utf-8")


def test_load_tie_break_raw_returns_empty_dict_for_missing_directory(tmp_path):
    assert load_tie_break_raw(tmp_path / "does_not_exist") == {}


def test_load_tie_break_raw_full_record(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tŚCIO\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t0.9\t\t1\tDRZEW\n",
    )
    raw = load_tie_break_raw(tmp_path)["AA-1"]
    assert raw.veg_cover_cd == "SCIO"  # normalize_code transliterates the diacritic
    assert raw.standdensity_index == pytest.approx(0.9)


def test_load_tie_break_raw_blank_veg_cover_cell_is_none_not_nan(tmp_path):
    # Real-data quirk already hit twice in B2/B3 (pipeline.bdl_packages,
    # pipeline.bdl_package_details): a blank CELL in an existing row reads
    # as pandas NaN (float), not "". Must not crash json.dumps(allow_nan=False)
    # downstream (pipeline.export.build_details_record).
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\t\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t0.9\t\t1\tDRZEW\n",
    )
    raw = load_tie_break_raw(tmp_path)["AA-1"]
    assert raw.veg_cover_cd is None


def test_load_tie_break_raw_blank_density_index_cell_is_none(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tZAD\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t\t\t1\tDRZEW\n",
    )
    raw = load_tie_break_raw(tmp_path)["AA-1"]
    assert raw.standdensity_index is None


def test_load_tie_break_raw_dedupes_repeated_subarea_geometry_rows(tmp_path):
    # Same real-data quirk as pipeline.bdl_packages/bdl_package_details:
    # one wydzielenie can appear as several G_SUBAREA rows.
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "AA-1"}, {"a_i_num": "1001", "adr_for": "AA-1"}],
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tZAD\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7\t\t0.9\t\t1\tDRZEW\n",
    )
    result = load_tie_break_raw(tmp_path)
    assert list(result.keys()) == ["AA-1"]


def test_veg_cover_label_known_codes():
    assert veg_cover_label("ZAD") == "zadarniona"
    assert veg_cover_label("SCIO") == "ścioła"
    assert veg_cover_label("MSZC") == "mszysto-czernicowa"
    assert veg_cover_label("NAGA") == "naga"


def test_veg_cover_label_none_for_missing_code():
    assert veg_cover_label(None) is None


def test_compute_tie_break_prefers_moss_litter_over_bare_ground():
    good = compute_tie_break("MSZC", 0.85)
    bad = compute_tie_break("NAGA", 0.85)
    assert good > bad


def test_compute_tie_break_prefers_intermediate_density_over_extremes():
    mid = compute_tie_break("ZAD", 0.85)
    sparse = compute_tie_break("ZAD", 0.1)
    dense = compute_tie_break("ZAD", 3.0)
    assert mid > sparse
    assert mid > dense


def test_compute_tie_break_neutral_when_both_missing():
    assert compute_tie_break(None, None) == pytest.approx(0.5)


def test_compute_tie_break_is_bounded_0_to_1():
    for veg in [None, "MSZC", "NAGA", "ZAD"]:
        for idx in [None, 0.0, 0.5, 1.0, 5.0]:
            value = compute_tie_break(veg, idx)
            assert 0.0 <= value <= 1.0


def test_tie_break_for_stand_falls_back_to_neutral_when_adr_for_uncovered():
    assert tie_break_for_stand("NOT-IN-INDEX", {}) == pytest.approx(0.5)


def test_tie_break_for_stand_uses_raw_entry_when_present():
    index = {"AA-1": TieBreakRaw(veg_cover_cd="MSZC", standdensity_index=0.85)}
    assert tie_break_for_stand("AA-1", index) == compute_tie_break("MSZC", 0.85)
