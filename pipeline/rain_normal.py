"""Nowy frontend (panel pogody): norma sumy opadu z 26 dni dla tej pory roku z lokalnego E-OBS.

Pula = wszystkie 26-dniowe sumy opadu (rr) z lat 1991-2020 konczace sie w dniach roku
odleglych o <= 15 dni od biezacego (z zawinieciem roku), dla komorek E-OBS 0,1 st. w kole
analizy. Tylko prezentacja -- nic stad nie wraca do modelu. Brak plikow E-OBS = pusta pula
(panel bez normy). Zastrzezenie: biezaca suma pochodzi z radaru IMGW scalonego z modelem,
norma z E-OBS (siec stacji) -- dwa rozne produkty, porownanie przyblizone."""
import math
from datetime import date

import numpy as np

CLIM_YEARS = (1991, 2020)
WINDOW_DAYS = 26
DOY_HALF_WIDTH = 15
EOBS_NORMAL_LABEL = "E-OBS v33.0e, 1991–2020"


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rad = math.radians
    h = (math.sin(rad(lat2 - lat1) / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))


def eobs_cells_in_radius(lat: float, lon: float, radius_km: float) -> list[tuple[float, float]]:
    """Srodki komorek siatki 0,1 st. (x.x5) w kole; zawsze co najmniej komorka srodka."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    cells = []
    for i in range(math.floor((lat - dlat) * 10), math.floor((lat + dlat) * 10) + 1):
        for j in range(math.floor((lon - dlon) * 10), math.floor((lon + dlon) * 10) + 1):
            la, lo = round(i / 10 + 0.05, 2), round(j / 10 + 0.05, 2)
            if _km(lat, lon, la, lo) <= radius_km:
                cells.append((la, lo))
    if not cells:
        cells.append((round(round(lat * 10 - 0.5) / 10 + 0.05, 2), round(round(lon * 10 - 0.5) / 10 + 0.05, 2)))
    return cells


def rain26_pool(store, cells, doy: int, years=CLIM_YEARS, half_width: int = DOY_HALF_WIDTH) -> np.ndarray:
    """26-dniowe sumy opadu z lat `years` konczace sie w dniu roku odleglym o <= half_width
    od `doy`, z wszystkich `cells`. `store` jak pipeline.eobs.EobsStore (metoda daily)."""
    values = []
    for clat, clon in cells:
        rr = store.daily(clat, clon, date(years[0] - 1, 12, 1), date(years[1], 12, 31), variables=["rr"])["rr"]
        sums = rr.rolling(WINDOW_DAYS, min_periods=WINDOW_DAYS).sum()
        idx = sums.index
        in_years = (idx.year >= years[0]) & (idx.year <= years[1])
        diff = np.abs(idx.dayofyear.to_numpy() - doy)
        near = np.minimum(diff, 365 - diff) <= half_width
        values.append(sums[in_years & near].dropna().to_numpy())
    return np.concatenate(values) if values else np.array([])


def local_rain26_pool(cache_dir, cells, doy: int) -> np.ndarray | None:
    """rain26_pool z lokalnego cache E-OBS; blad odczytu = None (panel bez normy, analiza idzie dalej)."""
    from pipeline.eobs import EobsStore
    try:
        return rain26_pool(EobsStore(cache_dir), cells, doy)
    except Exception as exc:  # np. obciety .npz (zipfile.BadZipFile) -- norma to tylko prezentacja
        print(f"UWAGA: norma opadu z E-OBS pominieta ({exc}).", flush=True)
        return None
