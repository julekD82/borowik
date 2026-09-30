import json

from launcher.trip_archive import slugify, trip_id, read_index, write_index, upsert_entry


def test_slugify_lowercases_and_transliterates_polish_diacritics():
    assert slugify("Będziemyśl") == "bedziemysl"


def test_slugify_collapses_symbols_and_whitespace_to_single_dashes():
    assert slugify("  Nadl.  Kędzierzyn ! ") == "nadl-kedzierzyn"


def test_slugify_strips_path_traversal_attempts():
    assert slugify("../../etc/passwd") == "etc-passwd"
    assert ".." not in slugify("../../etc/passwd")
    assert "/" not in slugify("a/b\\c")


def test_slugify_empty_or_symbols_only_falls_back_to_trip():
    assert slugify("") == "trip"
    assert slugify("   ") == "trip"
    assert slugify("###") == "trip"


def test_trip_id_combines_slug_and_day():
    assert trip_id("Będziemyśl", "2026-09-26") == "bedziemysl-2026-09-26"


def test_read_index_missing_file_is_empty_list(tmp_path):
    assert read_index(tmp_path / "index.json") == []


def test_read_index_corrupted_json_is_empty_list(tmp_path):
    path = tmp_path / "index.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert read_index(path) == []


def test_read_index_wrong_shape_is_empty_list(tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert read_index(path) == []


def test_write_index_then_read_index_roundtrips(tmp_path):
    path = tmp_path / "trips" / "index.json"
    entries = [{"id": "a-2026-09-26", "name": "A"}]
    write_index(path, entries)
    assert read_index(path) == entries


def test_upsert_entry_prepends_new_entry():
    entries = [{"id": "old", "name": "Old"}]
    result = upsert_entry(entries, {"id": "new", "name": "New"})
    assert result == [{"id": "new", "name": "New"}, {"id": "old", "name": "Old"}]


def test_upsert_entry_replaces_existing_entry_with_same_id_and_keeps_order():
    entries = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    result = upsert_entry(entries, {"id": "a", "name": "A2"})
    assert result == [{"id": "a", "name": "A2"}, {"id": "b", "name": "B"}]


from datetime import datetime, timezone

import pytest

from launcher.trip_archive import (
    TripMeta, read_day, TRIP_FILES, copy_trip_files, trip_exists, save_trip,
)


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_read_day_returns_day_of_first_record(tmp_path):
    path = tmp_path / "scores.json"
    _write_json(path, [{"stand_id": "A", "day": "2026-09-26"}])
    assert read_day(path) == "2026-09-26"


def test_read_day_missing_file_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        read_day(tmp_path / "scores.json")


def test_read_day_empty_list_raises_value_error(tmp_path):
    path = tmp_path / "scores.json"
    _write_json(path, [])
    with pytest.raises(ValueError):
        read_day(path)


def test_read_day_corrupted_json_raises_value_error(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_day(path)


def test_copy_trip_files_copies_only_existing_files(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "scores.json").write_text("[]", encoding="utf-8")
    (data_dir / "stands.geojson").write_text("{}", encoding="utf-8")
    # regions.json / details.json intentionally absent (optional files)
    dest = tmp_path / "trips" / "some-id"
    copied = copy_trip_files(data_dir, dest)
    assert sorted(copied) == ["scores.json", "stands.geojson"]
    assert (dest / "scores.json").read_text(encoding="utf-8") == "[]"
    assert not (dest / "regions.json").exists()


def test_copy_trip_files_copies_optional_files_when_present(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in TRIP_FILES:
        (data_dir / name).write_text("x", encoding="utf-8")
    dest = tmp_path / "trips" / "some-id"
    copied = copy_trip_files(data_dir, dest)
    assert sorted(copied) == sorted(TRIP_FILES)


def test_trip_exists_false_for_missing_folder(tmp_path):
    assert trip_exists(tmp_path / "trips", "nope") is False


def test_trip_exists_true_for_existing_folder(tmp_path):
    trips_dir = tmp_path / "trips"
    (trips_dir / "here").mkdir(parents=True)
    assert trip_exists(trips_dir, "here") is True


def test_save_trip_copies_files_and_writes_index_entry(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "scores.json", [{"stand_id": "A", "day": "2026-09-26"}])
    (data_dir / "stands.geojson").write_text("{}", encoding="utf-8")
    trips_dir = tmp_path / "data" / "trips"
    now = datetime(2026, 9, 26, 18, 4, 12, tzinfo=timezone.utc)

    meta = save_trip(data_dir, trips_dir, "Będziemyśl", 20.0, 50.0555, 21.7889, now=now)

    assert meta == TripMeta(
        id="bedziemysl-2026-09-26", name="Będziemyśl", radius_km=20.0,
        day="2026-09-26", lat=50.0555, lon=21.7889,
        saved_at="2026-09-26T18:04:12+00:00",
    )
    assert (trips_dir / "bedziemysl-2026-09-26" / "scores.json").exists()
    index = json.loads((trips_dir / "index.json").read_text(encoding="utf-8"))
    assert index == [
        {"id": "bedziemysl-2026-09-26", "name": "Będziemyśl", "radius_km": 20.0,
         "day": "2026-09-26", "lat": 50.0555, "lon": 21.7889,
         "saved_at": "2026-09-26T18:04:12+00:00"}
    ]


def test_save_trip_raises_when_no_synced_data(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with pytest.raises(ValueError):
        save_trip(data_dir, tmp_path / "trips", "X", 20.0, 50.0, 21.0)


def test_save_trip_overwrites_existing_entry_with_same_id(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "scores.json", [{"stand_id": "A", "day": "2026-09-26"}])
    trips_dir = tmp_path / "data" / "trips"
    save_trip(data_dir, trips_dir, "X", 20.0, 50.0, 21.0)
    save_trip(data_dir, trips_dir, "X", 25.0, 50.0, 21.0)
    index = json.loads((trips_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 1
    assert index[0]["radius_km"] == 25.0


# --- Post-review fixes (final review of the whole branch, 2026-09-26) ---


def test_copy_trip_files_removes_stale_optional_files_not_in_new_source(tmp_path):
    # Review finding (Important #1): re-saving a trip whose new source lacks
    # regions.json/details.json must not leave the OLD snapshot's copies
    # behind -- otherwise the "overwritten" trip mixes old regions with new
    # stands, silently wrong.
    dest = tmp_path / "trips" / "some-id"
    dest.mkdir(parents=True)
    (dest / "regions.json").write_text("old-regions", encoding="utf-8")
    (dest / "details.json").write_text("old-details", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "scores.json").write_text("[]", encoding="utf-8")
    (data_dir / "stands.geojson").write_text("{}", encoding="utf-8")
    # regions.json / details.json intentionally absent from the new source.

    copy_trip_files(data_dir, dest)

    assert not (dest / "regions.json").exists()
    assert not (dest / "details.json").exists()


def test_save_trip_overwrite_does_not_leave_stale_regions_file(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "scores.json", [{"stand_id": "A", "day": "2026-09-26"}])
    (data_dir / "regions.json").write_text("[]", encoding="utf-8")
    trips_dir = tmp_path / "trips"
    save_trip(data_dir, trips_dir, "X", 20.0, 50.0, 21.0)
    assert (trips_dir / "x-2026-09-26" / "regions.json").exists()

    (data_dir / "regions.json").unlink()  # new run has no regions export
    save_trip(data_dir, trips_dir, "X", 20.0, 50.0, 21.0)

    assert not (trips_dir / "x-2026-09-26" / "regions.json").exists()


def test_write_index_leaves_no_temp_file_behind(tmp_path):
    path = tmp_path / "trips" / "index.json"
    write_index(path, [{"id": "a"}])
    leftovers = list(path.parent.glob("*.tmp*"))
    assert leftovers == []
    assert read_index(path) == [{"id": "a"}]


def test_save_trip_backs_up_a_corrupted_index_instead_of_discarding_it(tmp_path):
    # Review finding (Important #2): read_index treats corrupted/wrong-shape
    # JSON the same as "no entries yet" -- fine for the browser (nothing to
    # show), but save_trip's read-modify-write must not silently overwrite a
    # corrupted index with just the one new entry, discarding whatever was
    # in it. Back it up instead, so it's recoverable.
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "scores.json", [{"stand_id": "A", "day": "2026-09-26"}])
    trips_dir = tmp_path / "trips"
    trips_dir.mkdir()
    index_path = trips_dir / "index.json"
    index_path.write_text("{not valid json, has real entries lost here", encoding="utf-8")

    save_trip(data_dir, trips_dir, "New", 20.0, 50.0, 21.0)

    backups = list(trips_dir.glob("index.json.bak-*"))
    assert len(backups) == 1
    assert "has real entries lost here" in backups[0].read_text(encoding="utf-8")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index) == 1
    assert index[0]["name"] == "New"


def test_read_day_rejects_non_dict_first_record(tmp_path):
    # Review finding (Important #3): a malformed scores.json whose first
    # element isn't an object (e.g. [5]) made `"day" not in data[0]` raise
    # TypeError instead of the intended ValueError -- an uncaught TypeError
    # in the launcher is silent under pythonw (no console).
    path = tmp_path / "scores.json"
    _write_json(path, [5])
    with pytest.raises(ValueError):
        read_day(path)


def test_slugify_truncates_very_long_names(tmp_path):
    # Review finding (Important #3): an unbounded slug can exceed Windows'
    # MAX_PATH once combined with the repo path and file names inside it.
    long_name = "a" * 300
    slug = slugify(long_name)
    assert len(slug) <= 60


def test_resave_without_conditions_removes_old_conditions_snapshot(tmp_path):
    data, dest = tmp_path / "data", tmp_path / "trip"
    data.mkdir()
    for name in ["scores.json", "stands.geojson"]:
        (data / name).write_text("{}", encoding="utf-8")
    dest.mkdir()
    (dest / "conditions.json").write_text("old-conditions", encoding="utf-8")
    copied = copy_trip_files(data, dest)
    assert "conditions.json" not in copied
    assert not (dest / "conditions.json").exists()


# --- eksport na telefon: wybor zrodla w launcherze ------------------------------

def test_trip_choices_start_with_current_analysis_then_saved_trips():
    from launcher.trip_archive import trip_choices
    entries = [
        {"id": "a-2026-09-30", "name": "Zawadzkie", "radius_km": 20.0, "day": "2026-09-30"},
        {"id": "b-2026-09-29", "name": "Kieleczka", "radius_km": 15.5, "day": "2026-09-29"},
    ]
    labels, ids = trip_choices(entries)
    assert labels == ["Bieżąca analiza", "Zawadzkie - 20km - 2026-09-30", "Kieleczka - 15.5km - 2026-09-29"]
    assert ids == [None, "a-2026-09-30", "b-2026-09-29"]


def test_trip_choices_with_no_saved_trips_offers_only_current_analysis():
    from launcher.trip_archive import trip_choices
    assert trip_choices([]) == (["Bieżąca analiza"], [None])


def test_phone_export_args_for_current_analysis_pass_place_name():
    from launcher.trip_archive import phone_export_args
    assert phone_export_args("Zawadzkie 30", None) == ["--nazwa", "Zawadzkie 30"]
    assert phone_export_args("  ", None) == []


def test_phone_export_args_for_snapshot_pass_id_and_ignore_typed_place():
    from launcher.trip_archive import phone_export_args
    assert phone_export_args("cokolwiek", "a-2026-09-30") == ["--migawka", "a-2026-09-30"]
