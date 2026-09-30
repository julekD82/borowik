import json
from pathlib import Path

from pipeline.phone_kmz import classify_by_percentile

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "klasy_procentowe.json").read_text(encoding="utf-8"))


def test_classify_by_percentile_matches_the_shared_fixture():
    for case in FIXTURE["przypadki"]:
        assert classify_by_percentile(case["wartosci"]) == case["klasy"]
