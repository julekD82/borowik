"""Faza 2.5: skladowe F z lokalnego E-OBS (ta sama matematyka co pipeline.weather/scoring/phenology).

Okna jak w produkcji i w notatniku 03: CWB26 = suma wykladniczo wazona (polokres 10 dni, 26 dni)
opadu minus ET0; tmean20 / tmean5 = srednie z TG; p5 = suma RR z 5 dni; tmin3 = min TN z 3 dni.
Wartosc NaN, jesli w oknie brakuje choc jednego dnia. ET0: Hargreaves-Samani z TN/TX.

Plan 2.8 (docs/WALIDACJA_BIELEFELD.md): wagi opadu w czasie sparametryzowane (`precip_weights`); domyslnie K0
= wagi produkcji. Kolumna nadal nazywa sie `cwb26`, ale przy innym wariancie to CWB wazony wagami wariantu
(klimatologia w CellClimate liczona jest z tej samej kolumny, wiec tymi samymi wagami). Produkcja bez zmian.
"""
from datetime import date

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from pipeline.eobs import EobsStore, hargreaves_et0
from pipeline.phenology import compute_g_season
from pipeline.scoring import (
    apply_moisture_modulation, compute_fruiting, moisture_percentile, score_frost, score_moisture, score_temperature,
)

CWB_WINDOW = 26
HALF_LIFE_DAYS = 10.0
CLIM_YEARS = (1991, 2020)
CLIM_WINDOW_DAYS = 15
ASSUMED_MOISTURE_CLS = 1  # jak w notatniku 03: brak dopasowania wydzielenia dla punktu GBIF
PRECIP_WEIGHT_KINDS = ("K0", "K1", "K2", "K3")
VARIANTS = ["F_bez_G_season", "F_z_G_season", "sam_kalendarz", "samo_M", "sama_T", "model_staly"]


def precip_weights(kind: str = "K0") -> np.ndarray:
    """Wagi w(j) dla j = 0, 1, ... dni wstecz (j = 0: dzien oceny). Warianty z docs/WALIDACJA_BIELEFELD.md:
    K0 = 0,5^(j/10), j 0-25 (produkcja); K1 = j/5 dla j < 5, 1 dla 5-10, 0,5^((j-10)/10) dla j > 10, j 0-35;
    K2 = 1, j 0-25 (rowne wagi jak w pracy z Bielefeld); K3 = 1 dla 5-10, j 0-10."""
    if kind == "K0":
        return 0.5 ** (np.arange(CWB_WINDOW) / HALF_LIFE_DAYS)
    if kind == "K1":
        j = np.arange(36, dtype=float)
        return np.where(j < 5, j / 5, np.where(j <= 10, 1.0, 0.5 ** ((j - 10) / 10)))
    if kind == "K2":
        return np.ones(CWB_WINDOW)
    if kind == "K3":
        return (np.arange(11) >= 5).astype(float)
    raise ValueError(f"nieznany wariant wag opadu: {kind}")


def rolling_features(daily: pd.DataFrame, lat: float, weights: np.ndarray | None = None) -> pd.DataFrame:
    """Cechy pogodowe na kazdy dzien z tabeli EobsStore.daily (kolumny tg, tn, tx, rr).
    weights: w(j) dla j = 0.. dni wstecz (domyslnie K0 = produkcja); dotyczy tylko `cwb26`."""
    et0 = hargreaves_et0(daily["tn"], daily["tx"], lat).to_numpy()
    p = daily["rr"].to_numpy(float)
    w = np.asarray(precip_weights("K0") if weights is None else weights, float)[::-1]  # od najstarszego do biezacego
    n = len(daily)

    def win(arr, size, fn):
        out = np.full(n, np.nan)
        if n >= size:
            out[size - 1:] = fn(sliding_window_view(arr.astype(float), size))  # NaN w oknie -> NaN wyniku
        return out

    cwb = win(p, len(w), lambda v: v @ w) - win(et0, len(w), lambda v: v @ w)
    return pd.DataFrame({
        "cwb26": cwb,
        "tmean20": win(daily["tg"].to_numpy(), 20, lambda v: v.mean(axis=1)),
        "tmean5": win(daily["tg"].to_numpy(), 5, lambda v: v.mean(axis=1)),
        "p5": win(p, 5, lambda v: v.sum(axis=1)),
        "tmin3": win(daily["tn"].to_numpy(), 3, lambda v: v.min(axis=1)),
    }, index=daily.index)


class CellClimate:
    """Cechy dobowe i klimatologia CWB26 (1991-2020) dla jednej komorki E-OBS."""

    def __init__(self, store: EobsStore, lat: float, lon: float, weights: np.ndarray | None = None):
        clat, clon = store.cell(lat, lon)
        self.lat = clat
        daily = store.daily(clat, clon, date(1990, 12, 1), date(2025, 12, 31))
        self.daily = daily
        self.features = rolling_features(daily, clat, weights)
        clim = self.features.loc[f"{CLIM_YEARS[0]}-01-01":f"{CLIM_YEARS[1]}-12-31", "cwb26"]
        clim = clim.dropna()
        self._clim_doy = clim.index.dayofyear.to_numpy()
        self._clim_vals = clim.to_numpy()

    def climatology(self, doy: int) -> np.ndarray:
        diff = np.abs(self._clim_doy - doy)
        return self._clim_vals[np.minimum(diff, 365 - diff) <= CLIM_WINDOW_DAYS]


def percentile(value: float, hist: np.ndarray) -> float:
    from pipeline.weather import percentile_rank
    return percentile_rank(value, hist)


def variant_scores(feat: pd.Series, doy: int, hist: np.ndarray, profile: dict) -> dict[str, float]:
    """Wartosc kazdego wariantu dla jednego dnia (feat = wiersz z rolling_features)."""
    assert profile["fruiting"]["soil_moisture_weight"] == 0.0, "E-OBS nie ma wilgotnosci gleby -- wymagana waga 0"
    pct = percentile(float(feat["cwb26"]), hist)
    m = score_moisture(pct, 0.5, profile)
    t = score_temperature(float(feat["tmean20"]), float(feat["tmean5"]), float(feat["p5"]), profile)
    k = score_frost(float(feat["tmin3"]), profile)
    pct_m = moisture_percentile(pct, 0.5, profile)
    g = compute_g_season(doy, profile)
    return {
        "F_bez_G_season": apply_moisture_modulation(compute_fruiting(m, t, k, g_season=1.0), ASSUMED_MOISTURE_CLS, pct_m, profile),
        "F_z_G_season": apply_moisture_modulation(compute_fruiting(m, t, k, g_season=g), ASSUMED_MOISTURE_CLS, pct_m, profile),
        "sam_kalendarz": g,
        "samo_M": m,
        "sama_T": t,
        "model_staly": 1.0,
    }
