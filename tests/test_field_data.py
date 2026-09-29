import json

from pipeline.field_data import validate

OUTINGS = "id_wyjscia,data,start,koniec,plik_gpx,powod_wyboru,id_migawki,uwagi\n"
FINDS = "id_wyjscia,lat,lon,gatunek,liczba,klasa_wieku\n"
GPX = """<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
<trkpt lat="50.5000" lon="18.6000"><time>2026-09-26T09:00:00Z</time></trkpt>
<trkpt lat="50.5010" lon="18.6010"><time>2026-09-26T11:00:00Z</time></trkpt>
</trkseg></trk></gpx>"""


def _setup(tmp_path, outings, finds, snapshots=("mig-1",)):
    (tmp_path / "wyjscia.csv").write_text(OUTINGS + outings, encoding="utf-8")
    (tmp_path / "znaleziska.csv").write_text(FINDS + finds, encoding="utf-8")
    (tmp_path / "a.gpx").write_text(GPX, encoding="utf-8")
    trips = tmp_path / "trips"
    trips.mkdir()
    (trips / "index.json").write_text(json.dumps([{"id": s} for s in snapshots]), encoding="utf-8")
    return trips


def test_valid_data_gives_summary_and_no_errors(tmp_path):
    trips = _setup(tmp_path,
                   "w1,2026-09-26,11:00,13:00,a.gpx,aplikacja,mig-1,\n",
                   "w1,50.5005,18.6005,Boletus edulis,3,dojrzale\n")
    r = validate(tmp_path, trips)
    assert r.errors == [] and r.warnings == []
    assert (r.outings, r.hours, r.finds, r.boletus_count) == (1, 2.0, 1, 3)


def test_detects_missing_fields_unknown_snapshot_and_bad_enum(tmp_path):
    trips = _setup(tmp_path,
                   "w1,2026-09-26,13:00,11:00,a.gpx,losowo,brak,\n",
                   "w9,50.5,18.6,Boletus edulis,1,stare\n")
    r = validate(tmp_path, trips)
    text = " | ".join(r.errors)
    assert "niepoprawna data/start/koniec" in text
    assert "powod_wyboru" in text
    assert "migawka 'brak' nie istnieje" in text
    assert "nieznane id_wyjscia 'w9'" in text


def test_warns_when_gpx_missing_gap_or_find_off_track(tmp_path):
    trips = _setup(tmp_path,
                   "w1,2026-09-26,11:00,13:00,a.gpx,aplikacja,mig-1,\n"
                   "w2,2026-09-26,11:00,13:00,,aplikacja,mig-1,\n",
                   "w1,50.6,18.9,Boletus edulis,1,stare\n")
    r = validate(tmp_path, trips)
    assert r.errors == []
    text = " | ".join(r.warnings)
    assert "w2: brak sladu GPX" in text
    assert "od sladu" in text
    # slad konczy sie o 13:00 lokalnie (11:00Z) -> pokrywa wyjscie 11-13; start 09:00Z = 11:00 lokalnie: bez luki
    assert "nie pokrywa czasu" not in text


def test_missing_files_and_columns_are_errors(tmp_path):
    r = validate(tmp_path)
    assert any("Brak pliku wyjscia.csv" in e for e in r.errors)
    (tmp_path / "wyjscia.csv").write_text("id_wyjscia\nw1\n", encoding="utf-8")
    r = validate(tmp_path)
    assert any("brakuje kolumn" in e for e in r.errors)
