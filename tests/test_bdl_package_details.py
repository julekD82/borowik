import geopandas as gpd
from shapely.geometry import box

from pipeline.bdl_package_details import load_package_details

_SPECIES_HEADER = "arodes_int_num\ta_year\tstorey_cd\tsp_rank_order_act\tspecies_cd\tspecies_age\tpart_cd_act\tsite_class_cd\theight\tbhd\tvolume\n"
_STOREY_HEADER = "arodes_int_num\ta_year\tdensity_cd\tmixture_cd\tstanddensity_index\ttree_stock_cd\tst_rank_order_act\tstorey_cd\n"
_SUBAREA_HEADER = "arodes_int_num\ta_year\tarea_type_cd\tsite_type_cd\tmoisture_cd\tdegradation_cd\tsoil_subtype_cd\tplant_comm_cd\tstand_struct_cd\tforest_func_cd\tsilviculture_cd\trotation_age\tsub_area\tveg_cover_cd\tdamage_degree\tcause_cd\n"


def _write_package(package_dir, subarea_rows, species_text, storey_text, subarea_text, metadane_text=None):
    package_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        subarea_rows, geometry=[box(0, 0, 100, 100)] * len(subarea_rows), crs="EPSG:2180",
    )
    gdf.to_file(package_dir / "G_SUBAREA.shp")
    (package_dir / "f_storey_species.txt").write_text(species_text, encoding="utf-8")
    (package_dir / "f_arod_storey.txt").write_text(storey_text, encoding="utf-8")
    (package_dir / "f_subarea.txt").write_text(subarea_text, encoding="utf-8")
    if metadane_text is not None:
        (package_dir / "metadane.txt").write_text(metadane_text, encoding="utf-8")


def test_load_package_details_returns_empty_dict_for_missing_directory(tmp_path):
    assert load_package_details(tmp_path / "does_not_exist") == {}


def test_load_package_details_full_record(tmp_path):
    _write_package(
        tmp_path / "PKG_ONE",
        [{"a_i_num": "1001", "adr_for": "AA-1"}],
        _SPECIES_HEADER +
        "1001\t2026\tDRZEW\t1\tSO\t60\t7\tI\t20\t30\t10.0\n"
        "1001\t2026\tDRZEW\t2\tBK\t60\t3\tI\t18\t25\t5.0\n"
        "1001\t2026\tPODSZ\t1\tCZM\t20\tMJS\t\t\t\t\n"
        "1001\t2026\tPODSZ\t2\tBRZ\t15\t3\t\t\t\t\n",
        _STOREY_HEADER +
        "1001\t2026\t0.7 \t\t\t\t1\tDRZEW   \n"
        "1001\t2026\t\t\t0.3\t\t2\tPODSZ   \n",
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tBMSW\tSW-EM\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tSZCH\t\t\n",
        metadane_text="Data wytworzenia danych: 2026-06-23\r\n",
    )
    details = load_package_details(tmp_path)["AA-1"]
    assert sorted(details.drzew_species) == [("BK", "3"), ("SO", "7")]
    assert sorted(details.podszyt_species) == [("BRZ", "3"), ("CZM", "MJS")]
    assert details.density_cd == "0.7"
    assert details.soil_subtype_cd == "Bw"
    assert details.package_date == "2026-06-23"
    assert details.source_name == "PKG_ONE"


def test_load_package_details_normalizes_diacritic_codes(tmp_path):
    _write_package(
        tmp_path / "PKG_DIA",
        [{"a_i_num": "2002", "adr_for": "BB-2"}],
        _SPECIES_HEADER + "2002\t2026\tDRZEW\t1\tŚW\t60\t10\tI\t20\t30\t10.0\n",
        _STOREY_HEADER + "2002\t2026\tPEŁ \t\t\t\t1\tDRZEW   \n",
        _SUBAREA_HEADER + "2002\t2026\tD-STAN\tBMSW\t\t\tMŁw\t\t\t\t\t\t\t\t\t\n",
    )
    details = load_package_details(tmp_path)["BB-2"]
    assert details.drzew_species == [("SW", "10")]
    assert details.density_cd == "PEL"
    assert details.soil_subtype_cd == "MLw"  # "Ł" -> "L", normalize_code


def test_load_package_details_missing_optional_fields_are_none(tmp_path):
    # A stand with only a DRZEW row (no PODSZ, no matching storey/subarea
    # rows) still gets a record, with the missing pieces as None/[].
    _write_package(
        tmp_path / "PKG_MINIMAL",
        [{"a_i_num": "3003", "adr_for": "CC-3"}],
        _SPECIES_HEADER + "3003\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
        _STOREY_HEADER,
        _SUBAREA_HEADER,
    )
    details = load_package_details(tmp_path)["CC-3"]
    assert details.drzew_species == [("SO", "10")]
    assert details.podszyt_species == []
    assert details.density_cd is None
    assert details.soil_subtype_cd is None


def test_load_package_details_blank_density_and_soil_cells_are_none(tmp_path):
    # Real-data finding (Będziemyśl verification, 2026-09-25): a present
    # f_arod_storey/f_subarea ROW whose density_cd/soil_subtype_cd CELL is
    # blank reads as pandas NaN (float), not an empty string -- different
    # from a stand with no such row at all (see the "missing optional
    # fields" test above, where dict.get's default already gives None).
    # NaN must become None too, or it reaches json.dumps(allow_nan=False)
    # in pipeline.export and crashes the whole details export.
    _write_package(
        tmp_path / "PKG_BLANK",
        [{"a_i_num": "5005", "adr_for": "EE-5"}],
        _SPECIES_HEADER + "5005\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
        _STOREY_HEADER + "5005\t2026\t\t\t\t\t1\tDRZEW   \n",
        _SUBAREA_HEADER + "5005\t2026\tD-STAN\tBMSW\tSW-EM\tN2\t\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tSZCH\t\t\n",
    )
    details = load_package_details(tmp_path)["EE-5"]
    assert details.density_cd is None
    assert details.soil_subtype_cd is None


def test_load_package_details_blank_podszyt_share_is_empty_string_not_nan(tmp_path):
    # Real-data finding (Będziemyśl verification, 2026-09-25): PODSZ rows
    # (unlike DRZEW's numeric-only filter) keep every row, and 30050 of
    # them in the real cached packages have a blank part_cd_act cell --
    # pandas NaN (float), not an empty string. podszyt_species must never
    # carry a NaN through to pipeline.export's json.dumps(allow_nan=False).
    _write_package(
        tmp_path / "PKG_BLANK_SHARE",
        [{"a_i_num": "6006", "adr_for": "FF-6"}],
        _SPECIES_HEADER +
        "6006\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n"
        "6006\t2026\tPODSZ\t1\tCZM\t20\t\t\t\t\t\n",
        _STOREY_HEADER,
        _SUBAREA_HEADER,
    )
    details = load_package_details(tmp_path)["FF-6"]
    assert details.podszyt_species == [("CZM", "")]


def test_load_package_details_dedupes_repeated_subarea_geometry_rows(tmp_path):
    _write_package(
        tmp_path / "PKG_MULTIPART",
        [{"a_i_num": "4004", "adr_for": "DD-4"}] * 3,
        _SPECIES_HEADER + "4004\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
        _STOREY_HEADER + "4004\t2026\t0.6 \t\t\t\t1\tDRZEW   \n",
        _SUBAREA_HEADER + "4004\t2026\tD-STAN\tBMSW\t\t\tBw\t\t\t\t\t\t\t\t\t\n",
    )
    details = load_package_details(tmp_path)["DD-4"]
    # not tripled by the 3 duplicate G_SUBAREA rows
    assert details.drzew_species == [("SO", "10")]


def test_load_package_details_skips_incomplete_package_directory(tmp_path):
    incomplete = tmp_path / "PKG_INCOMPLETE"
    incomplete.mkdir()
    (incomplete / "f_storey_species.txt").write_text(_SPECIES_HEADER, encoding="utf-8")
    assert load_package_details(tmp_path) == {}
