import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline.bdl_extra_features import load_extra_features

_SPECIES_HEADER = (
    "arodes_int_num\ta_year\tstorey_cd\tsp_rank_order_act\tspecies_cd\t"
    "species_age\tpart_cd_act\tsite_class_cd\theight\tbhd\tvolume\n"
)
_SUBAREA_HEADER = (
    "arodes_int_num\ta_year\tarea_type_cd\tsite_type_cd\tmoisture_cd\tdegradation_cd\t"
    "soil_subtype_cd\tplant_comm_cd\tstand_struct_cd\tforest_func_cd\tsilviculture_cd\t"
    "rotation_age\tsub_area\tveg_cover_cd\tdamage_degree\tcause_cd\n"
)
_AROD_STOREY_HEADER = (
    "arodes_int_num\ta_year\tdensity_cd\tmixture_cd\tstanddensity_index\ttree_stock_cd\t"
    "st_rank_order_act\tstorey_cd\n"
)
_CUE_HEADER = (
    "arodes_int_num\ta_year\tsite_nr\tmeasure_cd\turgency\tcutting_nr\tcutting_area\t"
    "large_timber_perc\tcue_rank_order\n"
)


def _write_package(package_dir, subarea_rows, species_text, subarea_text,
                    arod_storey_text=None, cue_text=None, compartment_rows=None):
    package_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        subarea_rows, geometry=[box(0, 0, 100, 100)] * len(subarea_rows), crs="EPSG:2180",
    )
    gdf.to_file(package_dir / "G_SUBAREA.shp")
    (package_dir / "f_storey_species.txt").write_text(species_text, encoding="utf-8")
    (package_dir / "f_subarea.txt").write_text(subarea_text, encoding="utf-8")
    (package_dir / "f_arod_storey.txt").write_text(
        arod_storey_text if arod_storey_text is not None else _AROD_STOREY_HEADER, encoding="utf-8",
    )
    (package_dir / "f_arod_cue.txt").write_text(
        cue_text if cue_text is not None else _CUE_HEADER, encoding="utf-8",
    )
    if compartment_rows is not None:
        comp_gdf = gpd.GeoDataFrame(
            compartment_rows, geometry=[box(-50, -50, 150, 150)] * len(compartment_rows), crs="EPSG:2180",
        )
        comp_gdf.to_file(package_dir / "G_COMPARTMENT.shp")


def test_load_extra_features_reads_subarea_scalar_fields(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1001", "adr_for": "02-10-1-05-317   -d   -00"}],
        _SPECIES_HEADER,
        _SUBAREA_HEADER +
        "1001\t2026\tD-STAN\tLMSW\tSS\tN2\tBw\t\tDRZEW\tGOSP\tP-Z\t70\t3.91\tSZCH\t\t\n",
    )
    features = load_extra_features(tmp_path)
    f = features["02-10-1-05-317   -d   -00"]
    assert f.veg_cover_cd == "SZCH"
    assert f.degradation_cd == "N2"
    assert f.stand_struct_cd == "DRZEW"
    assert f.soil_subtype_cd == "Bw"


def test_load_extra_features_bonitacja_from_dominant_species_row(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "2002", "adr_for": "AA-11"}],
        _SPECIES_HEADER +
        "2002\t2026\tDRZEW\t1\tSO\t60\t7\tI\t20\t30\t10.0\n"
        "2002\t2026\tDRZEW\t2\tBK\t60\t3\tII\t18\t25\t5.0\n",
        _SUBAREA_HEADER,
    )
    f = load_extra_features(tmp_path)["AA-11"]
    assert f.site_class_cd == "I"  # dominant species (sp_rank_order_act=1) only, not II


def test_load_extra_features_density_from_drzew_storey(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "3003", "adr_for": "BB-22"}],
        _SPECIES_HEADER,
        _SUBAREA_HEADER,
        arod_storey_text=_AROD_STOREY_HEADER +
        "3003\t2026\t0.8\tKEP \t1.0\t\t1\tDRZEW   \n"
        "3003\t2026\t\t\t\t\t1\tPODSZ   \n",
    )
    f = load_extra_features(tmp_path)["BB-22"]
    assert f.density_cd == "0.8"


def test_load_extra_features_podszyt_and_podrost_species_kept_separate(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "4004", "adr_for": "CC-33"}],
        _SPECIES_HEADER +
        "4004\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n"
        "4004\t2026\tPODSZ\t1\tBRZ\t20\t5\t\t\t\t\n"
        "4004\t2026\tPODR\t1\tBK\t10\t3\t\t\t\t\n",
        _SUBAREA_HEADER,
    )
    f = load_extra_features(tmp_path)["CC-33"]
    assert f.podszyt_species == [("BRZ", "5")]
    assert f.podrost_species == [("BK", "3")]


def test_load_extra_features_planned_treatments_from_cue(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "5005", "adr_for": "DD-44"}],
        _SPECIES_HEADER,
        _SUBAREA_HEADER,
        cue_text=_CUE_HEADER + "5005\t2026\t1\tPIEL     \tN\t\t3.91\t\t1\n",
    )
    f = load_extra_features(tmp_path)["DD-44"]
    assert f.zabiegi_planowane == [{"measure_cd": "PIEL", "urgency": "N", "cutting_area": 3.91}]
    assert f.rok_wskazan == "2026"


def test_load_extra_features_compartment_boundary_when_layer_present(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "6006", "adr_for": "02-10-1-01-100   -a   -00"}],
        _SPECIES_HEADER,
        _SUBAREA_HEADER,
        compartment_rows=[{"a_i_num": "1", "adr_for": "02-10-1-01-100   -    -"}],
    )
    f = load_extra_features(tmp_path)["02-10-1-01-100   -a   -00"]
    assert f.dist_do_granicy_oddzialu_m is not None
    assert f.dlugosc_granicy_z_oddzialem_m is not None


def test_load_extra_features_compartment_boundary_none_without_layer(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "7007", "adr_for": "EE-55"}],
        _SPECIES_HEADER,
        _SUBAREA_HEADER,
    )
    f = load_extra_features(tmp_path)["EE-55"]
    assert f.dist_do_granicy_oddzialu_m is None
    assert f.dlugosc_granicy_z_oddzialem_m is None


def test_load_extra_features_returns_empty_dict_for_missing_directory(tmp_path):
    assert load_extra_features(tmp_path / "does_not_exist") == {}
