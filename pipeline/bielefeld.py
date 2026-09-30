"""Plan 2.8: dane monitoringu Boletus edulis z Bielefeld (Brejon Lamartiniere & Hoffman, Zenodo V1.2).

Czysta logika (bez sieci): jednolita tabela dzienna owocnikow, pogoda autorow, liczby opisowe
i ujemny dwumianowy model zliczen NB1 (jak glmmTMB nbinom1, ale rok jako efekt STALY; scipy zamiast
statsmodels/glmmTMB).

Plik autorow (`Data/Environmental_fruiting_data_jun8.csv`): jeden wiersz na dzien 1.08-30.11 w latach
2015-2024 i "stanowisko" (All = wszystkie stanowiska razem, Site_A = stanowiska 3+23, Site_B = 6).
`Mnb` = liczba rekordow owocnikow z danego dnia; dni bez rekordu autorzy wypelnili zerem
(`ifelse(is.na(Mnb), 0, Mnb)`), a dni wizyt NIE sa w danych -- zero nie odroznia "byla wizyta, nic nie
znaleziono" od "nie bylo wizyty" (wizyty 2-4 razy w tygodniu). Dlatego `wizyta` = True tylko dla dni
z owocnikami, w pozostalych dniach brak wartosci (nieznana).
Pogoda autorow: E-OBS 0,1 st. (TG, RR) interpolowane dwuliniowo na srodek obszaru.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import digamma, gammaln

AUTHORS_CSV = "Data/Environmental_fruiting_data_jun8.csv"
SITES = ("All", "Site_A", "Site_B")
# Srodek obszaru z pracy: 52 st. 03'42,2"N 8 st. 27'03,3"E (dokladne stanowiska nie sa publiczne)
CENTROID = (52 + 3 / 60 + 42.2 / 3600, 8 + 27 / 60 + 3.3 / 3600)


def daily_counts(raw: pd.DataFrame) -> pd.DataFrame:
    """Tabela dzienna: data, stanowisko, nowe_owocniki (int), wizyta (True / brak = nieznana)."""
    n = pd.to_numeric(raw["Mnb"])
    if (n < 0).any() or (n % 1 != 0).any():
        raise ValueError("Mnb musi byc nieujemna liczba calkowita")
    out = pd.DataFrame({
        "data": pd.to_datetime(raw["Date"]),
        "stanowisko": raw["site"].astype(str),
        "nowe_owocniki": n.astype(int),
    })
    out["wizyta"] = pd.Series([True if v > 0 else None for v in out["nowe_owocniki"]], dtype=object,
                              index=out.index)
    return out.sort_values(["stanowisko", "data"]).reset_index(drop=True)


def authors_weather(raw: pd.DataFrame) -> pd.DataFrame:
    """Pogoda autorow (index = data): tg (C, srednia dobowa), rr (mm). Musi byc ta sama dla stanowisk."""
    w = raw.assign(data=pd.to_datetime(raw["Date"]))
    pivot_t = w.pivot_table(index="data", columns="site", values="Temp")
    pivot_p = w.pivot_table(index="data", columns="site", values="Precip")
    for p in (pivot_t, pivot_p):
        if not np.allclose(p.to_numpy(), p.iloc[:, [0]].to_numpy(), equal_nan=True):
            raise ValueError("pogoda autorow rozni sie miedzy stanowiskami")
    return pd.DataFrame({"tg": pivot_t.iloc[:, 0], "rr": pivot_p.iloc[:, 0]}).rename_axis(None)


def write_validation_tables(raw: pd.DataFrame, out_dir) -> dict[str, str]:
    """Trwaly zapis do dane_walidacyjne/bielefeld/: tabela dzienna owocnikow i pogoda autorow (CSV, UTF-8,
    kropka dziesietna, stala kolejnosc wierszy -> ten sam plik przy kazdym uruchomieniu). Zwraca sciezki."""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    daily = daily_counts(raw)
    daily = daily.assign(data=daily["data"].dt.strftime("%Y-%m-%d"),
                         wizyta=daily["wizyta"].map(lambda v: 1 if v is True else None).astype("Int64"))
    weather = authors_weather(raw).rename_axis("data").reset_index()
    weather["data"] = weather["data"].dt.strftime("%Y-%m-%d")
    paths = {"owocniki": out / "owocniki_dzienne.csv", "pogoda_autorow": out / "pogoda_autorow_eobs.csv"}
    daily.to_csv(paths["owocniki"], index=False, lineterminator="\n")
    weather.to_csv(paths["pogoda_autorow"], index=False, float_format="%.6f", lineterminator="\n")
    return {k: str(v) for k, v in paths.items()}


EOBS_CELL_CSV = "pogoda_eobs_v33e_komorka.csv"


def write_eobs_cell(daily: pd.DataFrame, out_dir) -> str:
    """Dzienna pogoda E-OBS jednej komorki (kolumny tg, tn, tx, rr z EobsStore.daily; wartosci w setnych, wiec
    2 miejsca po przecinku sa dokladne) do dane_walidacyjne/bielefeld/. Brak = puste pole."""
    from pathlib import Path
    path = Path(out_dir) / EOBS_CELL_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    out = daily[["tg", "tn", "tx", "rr"]].rename_axis("data").reset_index()
    out["data"] = pd.to_datetime(out["data"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, float_format="%.2f", lineterminator="\n")
    return str(path)


def compare_weather(ours: pd.DataFrame, authors: pd.DataFrame) -> dict:
    """Porownanie dziennej pogody (tg, rr) z pogoda autorow na wspolnych dniach: korelacja, srednia roznica
    (nasze - autorzy), sredni blad bezwzgledny, maks. roznica bezwzgledna."""
    out = {}
    for var in ("tg", "rr"):
        j = pd.concat([ours[var], authors[var]], axis=1, keys=["nasze", "autorzy"]).dropna()
        d = j["nasze"] - j["autorzy"]
        out[var] = {"n": int(len(j)), "korelacja": float(j["nasze"].corr(j["autorzy"])), "srednia_roznica": float(d.mean()),
                    "sredni_blad_bezwzgledny": float(d.abs().mean()), "maks_roznica_bezwzgledna": float(d.abs().max())}
    return out


def descriptive(daily: pd.DataFrame, site: str = "All", md_range: tuple[str, str] | None = None) -> dict:
    """Liczby opisowe jak w pracy. md_range = ("MM-DD", "MM-DD") zaweza dni w kazdym roku."""
    d = daily[daily["stanowisko"] == site]
    if md_range is not None:
        md = d["data"].dt.strftime("%m-%d")
        d = d[(md >= md_range[0]) & (md <= md_range[1])]
    pos = d[d["nowe_owocniki"] > 0]
    return {
        "stanowisko": site,
        "owocniki": int(d["nowe_owocniki"].sum()),
        "dni": int(len(d)),
        "dni_z_owocnikami": int(len(pos)),
        "udzial_dni_zerowych": float((d["nowe_owocniki"] == 0).mean()),
        "pierwszy_dzien_z_owocnikami": pos["data"].min().strftime("%Y-%m-%d") if len(pos) else None,
        "ostatni_dzien_z_owocnikami": pos["data"].max().strftime("%Y-%m-%d") if len(pos) else None,
        "zakres_MM_DD_z_owocnikami": [pos["data"].dt.strftime("%m-%d").min(), pos["data"].dt.strftime("%m-%d").max()]
        if len(pos) else None,
        "na_rok": {int(y): int(v) for y, v in d.groupby(d["data"].dt.year)["nowe_owocniki"].sum().items()},
    }


def rolling_mean_within_year(series: pd.Series, window: int) -> pd.Series:
    """Srednia kroczaca z rownymi wagami, wyrownana do prawej (dzien oceny w oknie), liczona osobno
    w kazdym roku kalendarzowym -- jak `rollmean(..., align = "right")` po `group_by(year)` u autorow."""
    return series.groupby(series.index.year).transform(lambda s: s.rolling(window).mean())


# --- NB1: Var(y) = mu * (1 + phi); log mu = X beta ---------------------------------------------

def nb1_loglik(y, mu, phi: float) -> np.ndarray:
    """Log-wiarygodnosc NB1 dla kazdej obserwacji (rozmiar = mu / phi, p = 1 / (1 + phi))."""
    y, mu = np.asarray(y, float), np.asarray(mu, float)
    r = mu / phi
    return gammaln(y + r) - gammaln(r) - gammaln(y + 1) - r * np.log1p(phi) + y * (np.log(phi) - np.log1p(phi))


def _nb1_negll_and_grad(theta: np.ndarray, y: np.ndarray, X: np.ndarray,
                        codes: np.ndarray | None = None) -> tuple[float, np.ndarray]:
    """y: liczby na blok; X: dni; codes: numer bloku kazdego dnia (None = kazdy dzien to blok).
    Srednia bloku = suma mu dni bloku (NB1 ze wspolnym phi jest zamkniety na sumowanie)."""
    beta, log_phi = theta[:-1], theta[-1]
    phi = np.exp(log_phi)
    mu_d = np.exp(np.clip(X @ beta, -50, 50))
    mu = mu_d if codes is None else np.bincount(codes, weights=mu_d, minlength=len(y))
    r = mu / phi
    ll = nb1_loglik(y, mu, phi)
    core = digamma(y + r) - digamma(r) - np.log1p(phi)
    per_day = core if codes is None else core[codes]
    g_beta = X.T @ (mu_d * per_day / phi)
    d_phi = -(mu / phi ** 2) * core - mu / (phi * (1 + phi)) + y / (phi * (1 + phi))
    g = np.append(g_beta, (d_phi * phi).sum())
    return -float(ll.sum()), -g


def block_totals(y_daily, blocks) -> tuple[np.ndarray, np.ndarray]:
    """Sumy liczb w blokach (np. tygodniach) i numer bloku dla kazdego dnia (bloki w kolejnosci sortowania)."""
    codes, _ = pd.factorize(pd.Series(np.asarray(blocks)), sort=True)
    return np.bincount(codes, weights=np.asarray(y_daily, float)), codes


def week_block(dates) -> np.ndarray:
    """Tydzien kalendarzowy (pon.-niedz.) jako data poniedzialku, RRRR-MM-DD."""
    d = pd.DatetimeIndex(dates)
    return (d - pd.to_timedelta(d.dayofweek, unit="D")).strftime("%Y-%m-%d").to_numpy()


def weighted_precip(rr: pd.Series, weights) -> pd.Series:
    """Srednia wazona opadu sum_j w(j) rr(d - j) / sum_j w(j), j = 0 dzien oceny (mm/dobe); NaN przy braku
    ktoregokolwiek dnia okna. rr: seria dzienna bez luk w indeksie."""
    from numpy.lib.stride_tricks import sliding_window_view
    w = np.asarray(weights, float)
    vals = rr.to_numpy(float)
    out = np.full(len(vals), np.nan)
    if len(vals) >= len(w):
        out[len(w) - 1:] = sliding_window_view(vals, len(w)) @ w[::-1] / w.sum()
    return pd.Series(out, index=rr.index)


def fit_nb1(y, covariates, groups, blocks=None, se: bool = False) -> dict:
    """NB1 z osobnym wyrazem wolnym dla kazdej grupy (np. roku) i wspolnymi wspolczynnikami covariates.
    covariates: macierz n x k dni (moze miec 0 kolumn), groups: grupa kazdego dnia. Bez `blocks` y to liczby
    dzienne; z `blocks` (np. week_block) liczby dzienne sa sumowane w blokach, a srednia bloku to suma mu
    jego dni. Zmienne sa standaryzowane wewnetrznie (stabilnosc), wynik w skali oryginalnej. Wyraz wolny
    grupy ograniczony do >= -30 (grupa bez owocnikow). se=True: bledy standardowe beta z hesjanu (Wald)."""
    y = np.asarray(y, float)
    Z = np.asarray(covariates, float).reshape(len(y), -1)
    block_codes = None
    y_day = y
    if blocks is not None:
        y, block_codes = block_totals(y, blocks)
    codes, levels = pd.factorize(pd.Series(np.asarray(groups)), sort=True)
    D = np.eye(len(levels))[codes]
    mean, sd = Z.mean(axis=0), Z.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Zs = (Z - mean) / sd
    X = np.hstack([D, Zs])
    start_alpha = np.log(np.maximum(np.bincount(codes, weights=y_day) / np.bincount(codes), 1e-3))
    theta0 = np.concatenate([start_alpha, np.zeros(Z.shape[1]), [0.0]])
    bounds = [(-30, None)] * len(levels) + [(None, None)] * Z.shape[1] + [(-10, 10)]
    res = minimize(_nb1_negll_and_grad, theta0, args=(y, X, block_codes), jac=True, method="L-BFGS-B",
                   bounds=bounds, options={"maxiter": 5000, "ftol": 1e-12, "gtol": 1e-8})
    alpha_s, beta_s, log_phi = res.x[:len(levels)], res.x[len(levels):-1], res.x[-1]
    beta = beta_s / sd
    alpha = alpha_s - float((beta_s * mean / sd).sum())
    loglik = -float(res.fun)
    k = len(levels) + Z.shape[1] + 1
    out = {
        "alpha": dict(zip(levels.tolist(), alpha.tolist())), "beta": beta, "phi": float(np.exp(log_phi)),
        "loglik": loglik, "n_params": k, "aic": 2 * k - 2 * loglik, "converged": bool(res.success), "n": len(y),
    }
    if se:
        h = 1e-5
        H = np.array([(_nb1_negll_and_grad(res.x + h * e, y, X, block_codes)[1]
                       - _nb1_negll_and_grad(res.x - h * e, y, X, block_codes)[1]) / (2 * h)
                      for e in np.eye(len(res.x))])
        cov = np.linalg.inv((H + H.T) / 2)
        idx = slice(len(levels), len(levels) + Z.shape[1])
        out["beta_se"] = np.sqrt(np.diag(cov)[idx]) / sd
    return out


def heldout_loglik(fit: dict, y, covariates, blocks=None) -> tuple[float, float]:
    """Log-wiarygodnosc danych jednej grupy (pominietego roku) przy beta i phi z `fit`; wyraz wolny tej grupy
    wyznaczany na tych danych (jeden parametr, jednakowo dla porownywanych wariantow). Zwraca (LL, alpha)."""
    y = np.asarray(y, float)
    Z = np.asarray(covariates, float).reshape(len(y), -1)
    codes = None
    if blocks is not None:
        y, codes = block_totals(y, blocks)
    lin = Z @ fit["beta"]
    phi = fit["phi"]

    def negll(a):
        mu_d = np.exp(np.clip(a + lin, -50, 50))
        mu = mu_d if codes is None else np.bincount(codes, weights=mu_d, minlength=len(y))
        return -float(nb1_loglik(y, mu, phi).sum())

    shift = float(np.log(max(y.sum(), 1e-3)) - np.log(np.exp(np.clip(lin, -50, 50)).sum()))
    res = minimize_scalar(negll, bounds=(shift - 30, shift + 30), method="bounded", options={"xatol": 1e-9})
    return -float(res.fun), float(res.x)


def loyo(y, covariates, groups, blocks=None) -> pd.DataFrame:
    """Zostaw jedna grupe (rok): dopasowanie na pozostalych, LL pominietej wg heldout_loglik."""
    y = np.asarray(y, float)
    Z = np.asarray(covariates, float).reshape(len(y), -1)
    g = np.asarray(groups)
    b = None if blocks is None else np.asarray(blocks)
    rows = []
    for level in sorted(set(g.tolist())):
        test = g == level
        fit = fit_nb1(y[~test], Z[~test], g[~test], None if b is None else b[~test])
        ll, _ = heldout_loglik(fit, y[test], Z[test], None if b is None else b[test])
        rows.append({"grupa": level, "ll": ll, "converged": fit["converged"]})
    return pd.DataFrame(rows)


def predict_nb1(fit: dict, covariates, groups) -> np.ndarray:
    """Oczekiwana liczba owocnikow; grupa nieznana w dopasowaniu -> blad (KeyError)."""
    Z = np.asarray(covariates, float).reshape(len(groups), -1)
    alpha = np.array([fit["alpha"][g] for g in np.asarray(groups).tolist()])
    return np.exp(alpha + Z @ fit["beta"])
