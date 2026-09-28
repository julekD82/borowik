"""Backtest: does F_loc (pipeline.scoring's weather-driven fruiting score,
esp. the M/T lag-window logic in fruiting.temp_optimum_c/temp_sigma_c and
weather.p26w/cwb26) actually track when Boletus edulis was really observed
in Poland?

Data: GBIF occurrences (scientificName=Boletus edulis, country=PL),
filtered to exact-date records with coordinateUncertaintyInMeters <= 1000m
(a proxy for "not iNaturalist-obscured" -- GBIF doesn't expose iNaturalist's
own geoprivacy flag, so this is an imperfect stand-in, not a guarantee).

Method: for each usable observation, fetch the FULL calendar year's daily
weather at that exact point (Open-Meteo archive API) and compute F_loc for
every day of a fixed candidate season (1 Jun - 31 Oct) at that SAME point
and year. The test statistic is the observation day's percentile rank
within that per-location, per-year distribution -- this holds habitat and
regional climate constant by construction (same point, same year), so it
isolates specifically the weather-driven window logic scoring.py
implements. Under a null of "no real signal", the expected mean rank is
0.5 by construction; a mean significantly above 0.5 is evidence the model's
temporal window tracks real fruiting timing.

Known caveats (report, don't hide):
- profile["phenology"]["gbif_monthly_counts"] (G_season) is itself fit to
  this same GBIF dataset's monthly distribution, so the "with G_season"
  result is partly circular for the seasonal-curve question. Also reported
  with G_season fixed at 1.0, to isolate the temperature/moisture window
  claim specifically (the actual thing being validated).
- No BDL stand match for a bare GBIF point -> moisture_cls is assumed 1
  ("świeży"), the modal class for the profile's best porcini site types
  (BMSW/BSW/LMSW/LSW).
- Small N, single country, presence-only, effort-biased citizen-science
  data (foragers are known to under-report/obscure porcini locations).
  This is a sanity check, not a statistical proof -- see the audit report
  this script was requested from for the full bias discussion.

Run: .venv/Scripts/python.exe notebooks/03_backtest_gbif.py
"""
import collections
import json
import math
import pathlib
import time

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from scipy import stats

from pipeline.habitat import load_profile
from pipeline.phenology import compute_g_season
from pipeline.scoring import (
    score_moisture, score_temperature, score_frost, compute_fruiting, apply_moisture_modulation,
    moisture_percentile,
)
from pipeline.weather import (
    fetch_climatology_raw, fetch_archive_daily,
    _default_climatology_call, _default_archive_daily_call,
    _exp_weighted_sum, climatology_window_values, percentile_rank,
)

CACHE_DIR = pathlib.Path("cache")
GBIF_CACHE = pathlib.Path(".cache/backtest_gbif/occurrences.json")
OUT_DIR = pathlib.Path("notebooks/output")

WEATHER_GRID_SPACING_M = 5000.0        # same as pipeline.orchestrate.WEATHER_GRID_SPACING_M
# 200km, NOT pipeline.orchestrate's 20km: Open-Meteo's free-tier hourly quota
# (~5000 "weight units", 1 pt x 30yr x 3 climatology vars = ~235 units --
# see pipeline.weather._OPEN_METEO_CLIMATOLOGY_BATCH_SIZE's docstring) makes
# a per-observation climatology fetch at production resolution infeasible
# for a few-hundred-point one-off backtest (611 obs -> 243 cells at 20km ->
# ~57k units, >11x a single hour's budget -- confirmed by a live failure,
# "Hourly API request limit exceeded"). 200km trades spatial precision in
# the moisture/soil-moisture PERCENTILE BASELINE for feasibility -- climate
# normals vary far more smoothly than weather, so this is a real but
# bounded approximation, not a methodology error; noted in the report.
CLIMATOLOGY_GRID_SPACING_M = 200000.0
MAX_OCCURRENCES = 200  # stratified-by-year subsample cap, same free-tier-budget reason
CANDIDATE_DOYS = list(range(152, 305))  # 1 Jun - 31 Oct, day-of-year (non-leap reference)
MIN_UNCERTAINTY_M = 1000.0
MIN_YEAR = 2015
MAX_YEAR = 2023  # 2024-2026 dropped: Open-Meteo hourly quota exhausted twice
# fetching them; 2016-2023 archive weather + all 15 climatology cells are
# already cached on disk, so capping here makes this run purely cache-read,
# no further API calls (user decision: report partial results now rather
# than wait for another quota window).
MIN_DAYS_BEFORE_TODAY = 10   # archive API has ~5-7 day latency (see audit)
ASSUMED_MOISTURE_CLS = 1     # "świeży" -- modal class for the best porcini site types
RANDOM_SEED = 42

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def _snap(lat: float, lon: float, spacing_m: float) -> tuple[float, float]:
    """Snap a point to a fixed lattice, same convention as
    pipeline.weather.make_grid, so nearby GBIF observations share one
    weather/climatology fetch instead of each paying for its own."""
    e, n = _TO_2180.transform(lon, lat)
    e_s = math.floor(e / spacing_m) * spacing_m + spacing_m / 2
    n_s = math.floor(n / spacing_m) * spacing_m + spacing_m / 2
    lon_s, lat_s = _TO_4326.transform(e_s, n_s)
    return round(lat_s, 6), round(lon_s, 6)


def _rate_limited(fn, *args, max_attempts=6, backoff_s=65, pace_s=2.0):
    time.sleep(pace_s)
    for attempt in range(max_attempts):
        try:
            return fn(*args)
        except Exception as exc:
            msg = str(exc).lower()
            if "limit" not in msg or attempt == max_attempts - 1:
                raise
            print(f"  rate limited, waiting {backoff_s}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(backoff_s)


def fetch_gbif_occurrences() -> list[dict]:
    if GBIF_CACHE.exists():
        print(f"GBIF cache hit: {GBIF_CACHE}")
        return json.loads(GBIF_CACHE.read_text(encoding="utf-8"))
    print("Fetching GBIF occurrences (Boletus edulis, PL)...")
    records = []
    offset = 0
    limit = 300
    while True:
        r = requests.get(
            "https://api.gbif.org/v1/occurrence/search",
            params={
                "scientificName": "Boletus edulis",
                "country": "PL",
                "hasCoordinate": "true",
                "hasGeospatialIssue": "false",
                "limit": limit,
                "offset": offset,
            },
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        records.extend(d["results"])
        print(f"  {len(records)}/{d.get('count')}")
        if d.get("endOfRecords") or len(records) >= d.get("count", 0):
            break
        offset += limit
        time.sleep(0.5)
    GBIF_CACHE.parent.mkdir(parents=True, exist_ok=True)
    GBIF_CACHE.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return records


def filter_occurrences(records: list[dict], today: pd.Timestamp) -> list[dict]:
    cutoff = today - pd.Timedelta(days=MIN_DAYS_BEFORE_TODAY)
    out = []
    for r in records:
        if r.get("day") is None or r.get("month") is None or r.get("year") is None:
            continue
        if r["year"] < MIN_YEAR:
            continue
        unc = r.get("coordinateUncertaintyInMeters")
        if unc is None or unc > MIN_UNCERTAINTY_M:
            continue
        lat, lon = r.get("decimalLatitude"), r.get("decimalLongitude")
        if lat is None or lon is None:
            continue
        try:
            obs_date = pd.Timestamp(year=r["year"], month=r["month"], day=r["day"])
        except ValueError:
            continue
        if obs_date > cutoff:
            continue
        doy = obs_date.dayofyear
        if doy < 30:  # not enough lookback for a 26-day window
            continue
        out.append({
            "key": r.get("key"), "date": obs_date, "year": r["year"], "doy": doy,
            "lat": lat, "lon": lon, "uncertainty_m": unc,
        })
    return out


def _daily_features(sub: pd.DataFrame) -> list[dict | None] | None:
    """Per-day-of-year feature dict (index = day_of_year - 1), for every
    day with a full 26-day trailing window available in `sub` (one point,
    one calendar year, sorted by date)."""
    if sub.empty:
        return None
    p = sub["precipitation_mm"].to_numpy()
    et0 = sub["et0_mm"].to_numpy()
    tmean = sub["tmean_c"].to_numpy()
    tmin = sub["tmin_c"].to_numpy()
    sm = sub["soil_moisture"].to_numpy()
    # Plan 1.8a (spec S18.4 #1): Open-Meteo's `date` is the UTC instant of
    # LOCAL midnight -- notebooks 06/09 convert to Europe/Warsaw before
    # taking .dayofyear, this one didn't, so every row's doy here was the
    # PREVIOUS calendar day's (local midnight = ~22:00-23:00 UTC the day
    # before), shifting every candidate-day feature back by one day. Noon-
    # recentred first (same fix as pipeline.weather.to_local_date, plan
    # 1.8b) so the October DST transition doesn't shift things a SECOND
    # time on top of the plain UTC offset -- late-October is inside this
    # notebook's own 1 Jun-31 Oct candidate season.
    raw_dates = sub["date"].reset_index(drop=True)
    dates = (
        (raw_dates + pd.Timedelta(hours=12)).dt.tz_convert("Europe/Warsaw")
        if raw_dates.dt.tz is not None else raw_dates
    )
    n = len(sub)
    out: list[dict | None] = [None] * 367
    for i in range(25, n):
        p_tail = pd.Series(p[i - 25: i + 1])
        et0_tail = pd.Series(et0[i - 25: i + 1])
        p26w = _exp_weighted_sum(p_tail, window=26)
        et026w = _exp_weighted_sum(et0_tail, window=26)
        doy = int(dates.iloc[i].dayofyear)
        if doy >= len(out):
            continue
        out[doy] = {
            "cwb26": p26w - et026w,
            "tmean20": float(np.mean(tmean[max(0, i - 19): i + 1])),
            "tmean5": float(np.mean(tmean[i - 4: i + 1])),
            "p5": float(np.sum(p[i - 4: i + 1])),
            "tmin3": float(np.min(tmin[i - 2: i + 1])),
            "soil_moisture": float(sm[i]),
        }
    return out


def _rank(series: dict[int, float], day: int) -> float:
    values = np.array(list(series.values()))
    val = series[day]
    return float((values < val).mean() + 0.5 * (values == val).mean())


def main():
    profile = load_profile("profiles/boletus_edulis.yaml")
    today = pd.Timestamp(pd.Timestamp.today().date())

    raw = fetch_gbif_occurrences()
    occ = filter_occurrences(raw, today)
    print(f"Usable occurrences after filtering: {len(occ)} / {len(raw)} raw")
    if not occ:
        print("Brak danych po filtrach -- przerywam.")
        return

    if len(occ) > MAX_OCCURRENCES:
        occ_df = pd.DataFrame({"i": range(len(occ)), "year": [o["year"] for o in occ]})
        frac = MAX_OCCURRENCES / len(occ)
        sampled = occ_df.groupby("year", group_keys=False).apply(
            lambda g: g.sample(n=max(1, round(len(g) * frac)), random_state=RANDOM_SEED)
        )
        keep_idx = set(sampled["i"].tolist())
        occ = [o for i, o in enumerate(occ) if i in keep_idx][:MAX_OCCURRENCES]
        print(f"Stratified subsample (by year, budget cap): {len(occ)} / {len(occ_df)}")

    if MAX_YEAR is not None:
        # Applied AFTER subsampling (not as an earlier population filter):
        # this must be an exact subset of the already-fetched/cached sample
        # from the prior successful run, or it re-triggers new API calls
        # against an exhausted hourly quota (observed live 2026-09-26).
        before = len(occ)
        occ = [o for o in occ if o["year"] <= MAX_YEAR]
        print(f"Capped to year <= {MAX_YEAR} (cache-only rerun): {len(occ)} / {before}")
    print()

    for o in occ:
        o["weather_point"] = _snap(o["lat"], o["lon"], WEATHER_GRID_SPACING_M)
        o["clim_point"] = _snap(o["lat"], o["lon"], CLIMATOLOGY_GRID_SPACING_M)

    clim_points = sorted({o["clim_point"] for o in occ})
    print(f"Unique climatology cells (20km grid): {len(clim_points)}")
    clim_df = fetch_climatology_raw(
        clim_points, 1991, 2020,
        call_api=lambda pts, sy, ey: _rate_limited(_default_climatology_call, pts, sy, ey),
        cache_dir=CACHE_DIR,
    )

    by_year: dict[int, set] = collections.defaultdict(set)
    for o in occ:
        by_year[o["year"]].add(o["weather_point"])

    daily_by_year: dict[int, pd.DataFrame] = {}
    for year, pts in sorted(by_year.items()):
        pts = sorted(pts)
        print(f"Fetching archive daily weather for {year}: {len(pts)} points...")
        daily_by_year[year] = fetch_archive_daily(
            pts, f"{year}-01-01", f"{year}-12-31",
            call_api=lambda p, sd, ed: _rate_limited(_default_archive_daily_call, p, sd, ed),
            cache_dir=CACHE_DIR,
        )

    print("\nComputing per-day fruiting scores and per-location climatology lookups...")
    feature_cache: dict[tuple, list | None] = {}
    clim_lookup_cache: dict[tuple, dict[int, tuple]] = {}

    results = []
    skipped_no_weather = 0
    skipped_no_window = 0
    for o in occ:
        wp, year, cp, doy = o["weather_point"], o["year"], o["clim_point"], o["doy"]

        fk = (wp, year)
        if fk not in feature_cache:
            sub = daily_by_year[year]
            sub = sub[(sub["lat"] == wp[0]) & (sub["lon"] == wp[1])].sort_values("date")
            feature_cache[fk] = _daily_features(sub)
        feats = feature_cache[fk]
        if feats is None:
            skipped_no_weather += 1
            continue

        candidate_doys = [d for d in (CANDIDATE_DOYS + [doy]) if d < len(feats) and feats[d] is not None]
        candidate_doys = sorted(set(candidate_doys))
        if doy not in candidate_doys or len(candidate_doys) < 10:
            skipped_no_window += 1
            continue

        if cp not in clim_lookup_cache:
            clim_sub = clim_df[(clim_df["lat"] == cp[0]) & (clim_df["lon"] == cp[1])]
            lookup = {}
            for d in candidate_doys:
                if d in clim_lookup_cache.get(cp, {}):
                    continue
                lookup[d] = (
                    climatology_window_values(clim_sub, cp[0], cp[1], d, "cwb26"),
                    climatology_window_values(clim_sub, cp[0], cp[1], d, "soil_moisture"),
                )
            clim_lookup_cache[cp] = lookup
        else:
            clim_sub = clim_df[(clim_df["lat"] == cp[0]) & (clim_df["lon"] == cp[1])]
            missing = [d for d in candidate_doys if d not in clim_lookup_cache[cp]]
            for d in missing:
                clim_lookup_cache[cp][d] = (
                    climatology_window_values(clim_sub, cp[0], cp[1], d, "cwb26"),
                    climatology_window_values(clim_sub, cp[0], cp[1], d, "soil_moisture"),
                )

        m_series, t_series, f_series, f_g1_series = {}, {}, {}, {}
        for d in candidate_doys:
            f_raw = feats[d]
            cwb26_hist, sm_hist = clim_lookup_cache[cp][d]
            pct_cwb26 = percentile_rank(f_raw["cwb26"], cwb26_hist)
            pct_sm = percentile_rank(f_raw["soil_moisture"], sm_hist)
            m = score_moisture(pct_cwb26, pct_sm, profile)
            t = score_temperature(f_raw["tmean20"], f_raw["tmean5"], f_raw["p5"], profile)
            k_frost = score_frost(f_raw["tmin3"], profile)
            pct_m = moisture_percentile(pct_cwb26, pct_sm, profile)
            g_season = compute_g_season(d, profile)
            f_full = compute_fruiting(m, t, k_frost, g_season=g_season)
            f_noseason = compute_fruiting(m, t, k_frost, g_season=1.0)
            m_series[d] = m
            t_series[d] = t
            f_series[d] = apply_moisture_modulation(f_full, ASSUMED_MOISTURE_CLS, pct_m, profile)
            f_g1_series[d] = apply_moisture_modulation(f_noseason, ASSUMED_MOISTURE_CLS, pct_m, profile)

        results.append({
            "gbif_key": o["key"], "date": o["date"].date().isoformat(),
            "lat": o["lat"], "lon": o["lon"], "n_candidates": len(candidate_doys),
            "rank_F_loc": _rank(f_series, doy),
            "rank_F_loc_no_gseason": _rank(f_g1_series, doy),
            "rank_M": _rank(m_series, doy),
            "rank_T": _rank(t_series, doy),
        })

    print(f"\nPominięte (brak pogody dla punktu/roku): {skipped_no_weather}")
    print(f"Pominięte (za mało dni z pełnym oknem 26-dniowym): {skipped_no_window}")

    if not results:
        print("Brak wynikow po dopasowaniu danych pogodowych -- przerywam.")
        return

    res_df = pd.DataFrame(results)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "backtest_gbif_results.csv"
    res_df.to_csv(out_path, index=False)
    print(f"\nZapisano {len(res_df)} wynikow -> {out_path}\n")

    _report(res_df)


def _report(res_df: pd.DataFrame):
    print(f"N = {len(res_df)} realnych obserwacji Boletus edulis (GBIF PL)\n")
    for col, label in [
        ("rank_F_loc", "F_loc (pełny wzór, z G_season)"),
        ("rank_F_loc_no_gseason", "F_loc bez G_season (izolacja M/T, bez kołowości sezonowej)"),
        ("rank_M", "sama wilgotność M"),
        ("rank_T", "sama temperatura T"),
    ]:
        ranks = res_df[col].to_numpy()
        mean_r, median_r = ranks.mean(), float(np.median(ranks))
        try:
            p_w = stats.wilcoxon(ranks - 0.5).pvalue
        except ValueError:
            p_w = float("nan")
        p_t = stats.ttest_1samp(ranks, 0.5).pvalue
        top_quartile = (ranks >= 0.75).mean()
        bottom_quartile = (ranks < 0.25).mean()
        print(f"{label}:")
        print(f"  średnia percentyla = {mean_r:.3f}   mediana = {median_r:.3f}   (0.5 = brak sygnału)")
        print(f"  Wilcoxon p = {p_w:.4g}   t-test p = {p_t:.4g}")
        print(f"  górny kwartyl (>=0.75): {top_quartile:.1%} | dolny kwartyl (<0.25): {bottom_quartile:.1%} (oczekiwane pod H0: 25% każdy)")
        print()


if __name__ == "__main__":
    main()
