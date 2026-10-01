import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline.bdl_packages import load_packages, forest_district_code, coverage_report, PackageComposition


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


def test_load_packages_captures_lower_storey_species_separately_from_drzew(tmp_path):
    # Plan 1.6.3: species_lower pools numeric-share rows from every storey
    # OTHER than DRZEW (PODSZ/PODR/PRZES/... -- "nizsze pietra"), kept apart
    # from `species` (DRZEW only, unaffected by 1.6.3).
    _write_package(
        tmp_path / "PKG_LOWER",
        [{"a_i_num": "3003", "adr_for": "BB-22"}],
        _SPECIES_HEADER +
        "3003\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n"
        "3003\t2026\tPODSZ\t1\tBRZ\t20\t6\t\t\t\t\n"
        "3003\t2026\tPRZES\t1\tDB\t80\t4\t\t\t\t\n"
        # trace codes excluded here too, same rule as DRZEW.
        "3003\t2026\tPODR\t1\tBK\t10\tMJS\t\t\t\t\n",
    )
    index = load_packages(tmp_path)
    comp = index["BB-22"]
    assert comp.species == [("SO", 1.0)]
    assert sorted(comp.species_lower) == [("BRZ", 0.6), ("DB", 0.4)]


def test_load_packages_lower_storey_species_empty_when_only_drzew_present(tmp_path):
    _write_package(
        tmp_path / "PKG_NOLOWER",
        [{"a_i_num": "4004", "adr_for": "CC-33"}],
        _SPECIES_HEADER + "4004\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
    )
    comp = load_packages(tmp_path)["CC-33"]
    assert comp.species_lower == []


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


# --- Plan 1.3: latest-by-metadata-date wins on a shared adr_for -------------

def test_load_packages_prefers_newer_package_date_even_when_loaded_first(tmp_path):
    # PKG_A sorts (and so loads) before PKG_B alphabetically, but PKG_B's
    # composition is dated LATER -- pre-1.3 behaviour picked A's (loaded
    # last... no, A loads first, B overwrites -- the bug this fixes is the
    # opposite case, proven by the next test). This one just establishes
    # that whichever has the newer date wins regardless of load order.
    _write_package(
        tmp_path / "PKG_A_OLDER",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
        metadane_text="Data wytworzenia danych: 2026-01-01\r\n",
    )
    _write_package(
        tmp_path / "PKG_B_NEWER",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tBK\t60\t10\tI\t20\t30\t10.0\n",
        metadane_text="Data wytworzenia danych: 2026-06-23\r\n",
    )
    comp = load_packages(tmp_path)["AA-1"]
    assert comp.species == [("BK", 1.0)]
    assert comp.package_date == "2026-06-23"


def test_load_packages_keeps_older_but_loaded_last_package_when_it_is_older(tmp_path):
    # The actual pre-1.3 bug: PKG_Z loads AFTER PKG_A alphabetically but is
    # dated OLDER -- a plain dict.update() would let it silently win. It
    # must not: the newer PKG_A composition (SO) must survive.
    _write_package(
        tmp_path / "PKG_A_NEWER",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
        metadane_text="Data wytworzenia danych: 2026-06-23\r\n",
    )
    _write_package(
        tmp_path / "PKG_Z_OLDER",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tBK\t60\t10\tI\t20\t30\t10.0\n",
        metadane_text="Data wytworzenia danych: 2026-01-01\r\n",
    )
    comp = load_packages(tmp_path)["AA-1"]
    assert comp.species == [("SO", 1.0)]


def test_load_packages_dated_package_beats_an_undated_one_loaded_later(tmp_path):
    _write_package(
        tmp_path / "PKG_A_DATED",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t10\tI\t20\t30\t10.0\n",
        metadane_text="Data wytworzenia danych: 2026-06-23\r\n",
    )
    _write_package(
        tmp_path / "PKG_Z_UNDATED",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tBK\t60\t10\tI\t20\t30\t10.0\n",
    )
    comp = load_packages(tmp_path)["AA-1"]
    assert comp.species == [("SO", 1.0)]


# --- Plan 1.3: sklad_niepelny (share sum below 0.9) -------------------------

def test_load_packages_flags_sklad_niepelny_below_point_nine(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t8\tI\t20\t30\t10.0\n",  # sum = 0.8
    )
    assert load_packages(tmp_path)["AA-1"].sklad_niepelny is True


def test_load_packages_does_not_flag_sklad_niepelny_at_or_above_point_nine(tmp_path):
    _write_package(
        tmp_path / "PKG",
        [{"a_i_num": "1", "adr_for": "AA-1"}],
        _SPECIES_HEADER + "1\t2026\tDRZEW\t1\tSO\t60\t9\tI\t20\t30\t10.0\n",  # sum = 0.9
    )
    assert load_packages(tmp_path)["AA-1"].sklad_niepelny is False


# --- Plan 1.3: coverage report ----------------------------------------------

def test_forest_district_code_takes_first_two_dash_segments():
    assert forest_district_code("02-10-1-05-317   -d   -00") == "02-10"
    assert forest_district_code("AA-1") == "AA-1"
    assert forest_district_code("nodash") == "nodash"


def test_coverage_report_groups_by_district_and_sorts_worst_first():
    stands = pd.DataFrame({
        "adr_for": ["02-10-1", "02-10-2", "02-25-1", "02-25-2", "02-25-3", "99-99-1"],
        "mask": [True, True, True, True, True, False],  # last stand fails structural mask
    })
    package_index = {
        "02-10-1": PackageComposition(species=[], source_name="x", package_date=None),
        "02-25-1": PackageComposition(species=[], source_name="x", package_date=None),
    }
    report = coverage_report(stands, package_index)
    by_district = {r["district"]: r for r in report}
    assert by_district["02-10"] == {"district": "02-10", "stand_count": 2, "package_stand_count": 1, "coverage": 0.5}
    assert by_district["02-25"]["package_stand_count"] == 1
    assert by_district["02-25"]["stand_count"] == 3
    assert "99-99" not in by_district  # only mask-passing stand, excluded (not structurally in scope)
    # sorted worst-covered first
    assert report[0]["coverage"] <= report[-1]["coverage"]


def test_coverage_report_returns_empty_list_when_nothing_passes_the_mask():
    stands = pd.DataFrame({"adr_for": ["AA-1"], "mask": [False]})
    assert coverage_report(stands, {}) == []


def test_area_package_message_counts_area_not_whole_directory():
    from pipeline.bdl_packages import area_package_message
    index = {f"02-09-1-01-{i}": object() for i in range(100)} | {"02-10-1-01-1": object()}
    stands = pd.DataFrame({"adr_for": ["02-09-1-01-1", "02-09-1-01-2", "13-05-1-01-1", "13-05-1-01-2", "13-07-1-01-1"]})
    msg = area_package_message(stands, index)
    assert "2/5 drzewostanow obszaru" in msg
    assert "w katalogu: 101 wydzielen z 2 nadlesnictw" in msg
    assert "13-05 (2), 13-07 (1)" in msg and "BDL_13_05_*" in msg


def test_area_package_message_when_area_has_no_package():
    from pipeline.bdl_packages import area_package_message
    index = {"02-09-1-01-1": object()}
    stands = pd.DataFrame({"adr_for": ["13-05-1-01-1"] * 3 + ["14-02-1-01-1"]})
    msg = area_package_message(stands, index)
    assert msg.startswith("Paczki BDL: 0/4 drzewostanow obszaru")
    assert "13-05 (3), 14-02 (1)" in msg


def test_area_package_message_full_coverage_lists_nothing_missing_and_limits_list():
    from pipeline.bdl_packages import area_package_message
    stands = pd.DataFrame({"adr_for": ["02-09-1-01-1"]})
    assert "Bez paczki" not in area_package_message(stands, {"02-09-1-01-1": object()})
    many = pd.DataFrame({"adr_for": [f"{10 + i}-01-1-01-1" for i in range(8)]})
    msg = area_package_message(many, {"02-09-1-01-1": object()})
    assert msg.count("(1)") == 5 and "i 3 innych" in msg


def test_area_package_message_separates_districts_whose_package_lacks_some_stands():
    from pipeline.bdl_packages import area_package_message
    index = {"02-14-1-01-1": object()}
    stands = pd.DataFrame({"adr_for": ["02-14-1-01-1", "02-14-1-01-2", "02-40-1-01-1"]})
    msg = area_package_message(stands, index)
    assert "nadlesnictwa 02-40 (1)" in msg and "BDL_02_14_*" not in msg
    assert "1 drzewostanow z nadlesnictw, ktore maja paczke" in msg


def test_area_package_message_counts_only_dstan_when_area_type_known():
    from pipeline.bdl_packages import area_package_message
    stands = pd.DataFrame({"adr_for": ["02-09-1-01-1", "02-09-1-01-2", "02-09-1-01-3"],
                           "area_type": ["D-STAN", "D-STAN", "DROGA"]})
    msg = area_package_message(stands, {"02-09-1-01-1": object()})
    assert "1/2 drzewostanow" in msg and "1 drzewostanow z nadlesnictw" in msg
