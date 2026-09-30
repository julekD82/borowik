import math
from datetime import date

import numpy as np
import pandas as pd

from pipeline.rain_normal import eobs_cells_in_radius, rain26_pool


class _FakeStore:
    """Staly opad 1 mm/dobe albo brak danych (NaN) -- bez plikow E-OBS."""

    def __init__(self, rr: float):
        self.rr = rr

    def daily(self, lat, lon, start, end, variables=("rr",)):
        index = pd.date_range(start, end, freq="D")
        return pd.DataFrame({"rr": self.rr}, index=index)


def _km(lat1, lon1, lat2, lon2):
    rad = math.radians
    h = (math.sin(rad(lat2 - lat1) / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def test_cells_in_radius_include_the_centre_cell_and_stay_inside():
    cells = eobs_cells_in_radius(50.6191, 18.4611, 20)
    assert (50.65, 18.45) in cells
    assert len(cells) > 10
    assert all(_km(50.6191, 18.4611, la, lo) <= 20 for la, lo in cells)


def test_small_radius_still_returns_one_cell():
    assert len(eobs_cells_in_radius(50.6191, 18.4611, 1)) >= 1


def test_pool_holds_26_day_sums_from_1991_2020_near_the_day_of_year():
    pool = rain26_pool(_FakeStore(1.0), [(50.65, 18.45)], date(2026, 9, 30).timetuple().tm_yday)
    assert len(pool) == 30 * 31           # 30 lat x (dzien +-15)
    assert np.all(pool == 26.0)


def test_pool_is_empty_without_eobs_data():
    assert len(rain26_pool(_FakeStore(float("nan")), [(50.65, 18.45)], 273)) == 0
