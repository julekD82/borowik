import hashlib
import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "pobierz_bielefeld", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "pobierz_bielefeld.py")
pb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pb)


class _Resp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def test_download_checks_md5_and_records_sha256(tmp_path):
    body = b"a,b\n1,2\n"
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _Resp(body)

    sums = {}
    digest = pb.ensure_file(tmp_path / "x.csv", "u", hashlib.md5(body).hexdigest(), sums, get=fake_get)
    assert digest == hashlib.sha256(body).hexdigest() == sums["x.csv"]
    # drugie uruchomienie: bez sieci, tylko weryfikacja
    assert pb.ensure_file(tmp_path / "x.csv", "u", "zle-md5", sums, get=None) == digest
    assert calls == ["u"]


def test_md5_mismatch_leaves_no_file(tmp_path):
    with pytest.raises(RuntimeError, match="MD5"):
        pb.ensure_file(tmp_path / "x.csv", "u", "0" * 32, {}, get=lambda url, timeout: _Resp(b"abc"))
    assert not any(tmp_path.iterdir())


def test_changed_file_fails_sha256_check(tmp_path):
    f = tmp_path / "x.csv"
    f.write_bytes(b"zmienione")
    with pytest.raises(RuntimeError, match="SHA-256"):
        pb.ensure_file(f, "u", "m", {"x.csv": "0" * 64}, get=None)


def test_sums_roundtrip(tmp_path):
    p = tmp_path / "SHA256SUMS"
    pb.write_sums(p, {"b.zip": "22", "a.csv": "11"})
    assert p.read_text(encoding="utf-8") == "11  a.csv\n22  b.zip\n"
    assert pb.read_sums(p) == {"a.csv": "11", "b.zip": "22"}
