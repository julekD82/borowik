import geopandas as gpd
from shapely.geometry import box

from pipeline.bdl_packages import load_packages


def _write_package(package_dir, subarea_rows, species_text, metadane_text=None):
    """Writes a minimal synthetic BDL data package: G_SUBAREA.shp (a_i_num,
    adr_for) + f_storey_species.txt (+ optional metadane.txt) -- the two
    files pipeline.bdl_packages actually reads, matching the real package
    layout verified in plan 2.1 steps B1/B2 research (not the real
    Kedzierzyn/Bedziemysl packages, which stay out of the repo)."""
    package_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        subarea_rows,
        geometry=[box(0, 0, 100, 100)] * len(subarea_rows),
        crs="EPSG:2180",
    )
    gdf.to_file(package_dir / "G_SUBAREA.shp")
    (package_dir / "f_storey_species.txt").write_text(species_text, encoding="utf-8")
    if metadane_text is not None:
        (package_dir / "metadane.txt").write_text(metadane_text, encoding="utf-8")


_SPECIES_HEADER = "arodes_int_num\ta_year\tstorey_cd\tsp_rank_order_act\tspecies_cd\tspecies_age\tpart_cd_act\tsite_class_cd\theight\tbhd\tvolume\n"


def test_load_packages_returns_empty_dict_for_missing_directory(tmp_path):
    assert load_packages(tmp_path / "does_not_exist") == {}


def test_load_packages_returns_empty_dict_for_empty_directory(tmp_path):
    (tmp_path / "empty").mkdir()
    assert load_packages(tmp_path) == {}


def test_load_packages_joins_by_adr_for_and_sums_numeric_shares(tmp_path):
    _write_package(
        tmp_path / "PKG_ONE",
        [{"a_i_num": "1001", "adr_for": "02-10-1-05-317   -d   -00"}],
        _SPECIES_HEADER +
        "1001\t2026\tDRZEW\t1\tSO\t60\t7\tI\t20\t30\t10.0\n"
        "1001\t2026\tDRZEW\t2\tBK\t60\t3\tI\t18\t25\t5.0\n"
        # non-DRZEW storey must be ignored even with a numeric share
        "1001\t2026\tPODSZ\t1\tBRZ\t20\t5\t\t\t\t\n",
        metadane_text="Data wytworzenia danych: 2026-06-23\r\n",
    )
    index = load_packages(tmp_path)
    assert set(index) == {"02-10-1-05-317   -d   -00"}
    comp = index["02-10-1-05-317   -d   -00"]
    assert sorted(comp.species) == [("BK", 0.3), ("SO", 0.7)]
    assert comp.package_date == "2026-06-23"
    assert comp.source_name == "PKG_ONE"


def test_load_packages_excludes_mjs_and_pjd_trace_rows(tmp_path):
    # f_part_dic: MJS = "below 5%, in patches", PJD = "below 5%, single
    # trees" -- neither is a quantified share and both must be excluded,
    # not treated as 0 or skipped-with-a-gap (real packages' numeric shares
    # already sum to 10 without them -- see module docstring).
    _write_package(
        tmp_path / "PKG_TWO",
        [{"a_i_num": "2002", "adr_for": "AA-11"}],
        _SPECIES_HEADER +
        "2002\t2026\tDRZEW\t1\tSO\t100\t10\tI\t25\t35\t12.0\n"
        "2002\t2026\tDRZEW\t2\tDB\t150\tMJS\t\t\t\t\n"
        "2002\t2026\tDRZEW\t3\tBK\t80\tPJD\t\t\t\t\n",
    )
    index = load_packages(tmp_path)
    assert index["AA-11"].species == [("SO", 1.0)]


def test_load_packages_sums_repeated_species_across_age_cohorts(tmp_path):
    # Verified on real data (B2 research): the same species can carry two
    # separate numeric rows in one stand's DRZEW storey (different age
    # cohorts of an uneven-aged stand), not a duplicate/data-quality bug.
    _write_package(
        tmp_path / "PKG_THREE",
        [{"a_i_num": "3003", "adr_for": "BB-22"}],
        _SPECIES_HEADER +
        "3003\t2026\tDRZEW\t1\tDB\t120\t6\tI\t30\t50\t20.0\n"
        "3003\t2026\tDRZEW\t2\tDB\t40\t4\tII\t12\t15\t2.0\n",
    )
    index = load_packages(tmp_path)
    species = index["BB-22"].species
    assert len(species) == 2  # both age cohorts kept, not collapsed
    assert sum(share for _sp, share in species if _sp == "DB") == 1.0


def test_load_packages_ignores_repeated_subarea_geometry_rows(tmp_path):
    # Real Strzyzow package: one wydzielenie stored as several G_SUBAREA
    # rows (same a_i_num/adr_for, separate polygons). Joining species onto
    # those rows multiplied every share (shares summing to 2-5, H up to 1.5).
    _write_package(
        tmp_path / "PKG_MULTIPART",
        [{"a_i_num": "5005", "adr_for": "DD-44"}] * 3,
        _SPECIES_HEADER +
        "5005\t2026\tDRZEW\t1\tBK\t76\t5\tI\t28\t37\t139.0\n"
        "5005\t2026\tDRZEW\t2\tDB\t76\t5\tI\t27\t46\t63.0\n",
    )
    comp = load_packages(tmp_path)["DD-44"]
    assert sorted(comp.species) == [("BK", 0.5), ("DB", 0.5)]


def test_load_packages_skips_stand_whose_shares_exceed_whole(tmp_path, capsys):
    # Guard against any other join/data problem: numeric shares above 10/10
    # cannot be a real composition, so the stand falls back to WFS (absent
    # from the index) loudly instead of feeding S_host > 1 into H.
    _write_package(
        tmp_path / "PKG_BAD",
        [{"a_i_num": "6006", "adr_for": "EE-55"}, {"a_i_num": "6007", "adr_for": "EE-56"}],
        _SPECIES_HEADER +
        "6006\t2026\tDRZEW\t1\tSO\t60\t8\tI\t20\t30\t10.0\n"
        "6006\t2026\tDRZEW\t2\tBK\t60\t5\tI\t18\t25\t5.0\n"
        "6007\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
    )
    index = load_packages(tmp_path)
    assert "EE-55" not in index
    assert index["EE-56"].species == [("SO", 1.0)]
    assert "EE-55" in capsys.readouterr().out


def test_load_packages_normalizes_diacritic_species_codes(tmp_path):
    _write_package(
        tmp_path / "PKG_FOUR",
        [{"a_i_num": "4004", "adr_for": "CC-33"}],
        _SPECIES_HEADER + "4004\t2026\tDRZEW\t1\tŚW\t80\t10\tI\t22\t28\t8.0\n",
    )
    index = load_packages(tmp_path)
    assert index["CC-33"].species == [("SW", 1.0)]


def test_load_packages_merges_multiple_package_directories(tmp_path):
    _write_package(
        tmp_path / "PKG_A",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
    )
    _write_package(
        tmp_path / "PKG_B",
        [{"a_i_num": "1", "adr_for": "BB-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tBK\t60\t10\tI\t20\t30\t10.0\n",
    )
    index = load_packages(tmp_path)
    assert set(index) == {"AA-1", "BB-1"}


def test_load_packages_missing_metadane_gives_none_date(tmp_path):
    _write_package(
        tmp_path / "PKG_NO_META",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
    )
    assert load_packages(tmp_path)["AA-1"].package_date is None
