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
