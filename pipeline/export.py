import json
import math
import pathlib

import geopandas as gpd
import pandas as pd

from pipeline.scoring import compute_ranking
from pipeline.searchability import searchability_hint
from pipeline.tie_break import veg_cover_label

SCORE_FIELDS = [
    "stand_id", "H", "F", "F_loc", "P", "confidence", "confidence_reasons", "explanation",
    "distance_method", "entrance_status", "d_park_m",
    # spec §3.3: how many days of the weather window are forecast (not yet
    # observed) rather than history -- plan 2.1 step A3. Same value for
    # every stand in a run (pipeline.orchestrate.run_poc's forecast_days).
    "forecast_days",
    # Plan 2.1 "Zmiana 1": seasonal fruiting-frequency multiplier for this
    # run's target_date (pipeline.phenology.compute_g_season) -- same value
    # for every stand in one export.
    "G_season",
    # plan 2.1 step B2: whether this stand's S_host came from a real BDL
    # package's full species composition ("paczka") or the WFS
    # panujący+part_cd fallback ("wfs"), plus that package's own
    # generation date (metadane.txt) when applicable -- null for "wfs".
    "s_host_source", "s_host_package_date",
    # Plan 2.1 "Zmiana 4": ground-cover/density ordinal secondary sort key
    # (pipeline.tie_break) -- presentation-only, see that module's docstring.
    "tie_break",
    # Plan 2026-09-26 A1: exp-weighted share of the P26w window whose rain
    # came from the IMGW radar (pipeline.radar), 0 = Open-Meteo only.
    "rain_radar_coverage",
    # Plan wdrozenia 1.6: "sprawdzono brak blokady" vs "nie sprawdzono" vs
    # "zrodlo zawiodlo" (zakaz_status), and "brak" vs "blokada" vs kafel
    # pominiety z powodu bledu sieci (gdos_status) -- both computed in
    # pipeline.mvp.enrich_with_mvp_layers, exported here (not just in
    # diagnostics_{day}.json) so the frontend card/list can show a discrete
    # "zakazow nie sprawdzono" notice without needing the diagnostics file.
    "zakaz_status", "gdos_status",
]


def _json_safe(value):
    """NaN (e.g. H=None on a mask-failing stand, coerced to NaN once the
    column holds floats) has no JSON representation; json.dumps emits it as
    a bare `NaN` token by default, which is invalid JSON and throws in a
    browser's JSON.parse -- the stated consumer (spec §6.1). Convert to
    None/null instead."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def build_score_record(row, day: str) -> dict:
    """Matches the architecture diagram's scores_YYYY-MM-DD.json shape (spec
    §6.1: "id -> H, F, P, R, conf, wyjaśnienie") and the score_daily table
    columns (spec §6.2)."""
    record = {field: _json_safe(row[field]) for field in SCORE_FIELDS}
    record["day"] = day
    record["R"] = _json_safe(float(row["R_final"]))
    record["mask"] = bool(row["mask_full"])
    # Faza UI.1: wynik bez presji grzybiarzy, 100 * H * F_loc (ta sama maska).
    # Kolumna pochodzi z pipeline.mvp; wiersz bez niej (starsza ramka) liczony tu
    # tym samym compute_ranking z alpha = 0.
    r_bez = row["R_bez_presji"] if "R_bez_presji" in row.index else compute_ranking(
        bool(row["mask_full"]), _json_safe(row["H"]), _json_safe(row["F_loc"]), p=0.0, alpha=0.0)
    record["R_bez_presji"] = _json_safe(float(r_bez))
    # Faza UI (tryb mapy "Wilgotnosc"): skladowa M (0-1) i percentyl bilansu wodnego z 26 dni,
    # dla WSZYSTKICH wydzielen (rowniez poza maska -- wilgotnosc od maski nie zalezy). Tylko
    # prezentacja; null dla ramki bez tych kolumn.
    record["M"] = _json_safe(row["M"]) if "M" in row.index else None
    record["pct_CWB26"] = _json_safe(row["pct_CWB26"]) if "pct_CWB26" in row.index else None
    # Plan 2.1 step A4 (spec §5.2): from the EPSG:2180 geometry itself (same
    # source pipeline.regions.py already uses for its own area_ha), not
    # BDL's own sub_area attribute -- unused elsewhere, possibly stale.
    # Frontend-only presentation filter (hide sub-0.5ha stands as standalone
    # targets); not a mask, so every stand still gets a real value here.
    record["area_ha"] = _json_safe(float(row["geometry"].area / 10000.0))
    # Nowy frontend: dlaczego wydzielenie jest poza filtrami modelu (pusta lista w masce).
    record["mask_reason"] = mask_reason_list(row)
    return record


def mask_reason_list(row) -> list[str]:
    """Powody odrzucenia: maska strukturalna (kolumna mask_reasons z run_poc, kody z
    pipeline.habitat.mask_reasons) plus GDOS i zakaz okresowy z pelnej maski. Pusta lista
    dla wydzielenia w masce albo gdy ramka nie ma tych kolumn. Tylko prezentacja."""
    if bool(row["mask_full"]):
        return []
    structural = row["mask_reasons"] if "mask_reasons" in row.index else None
    reasons = list(structural) if isinstance(structural, (list, tuple)) else []
    if row.get("gdos_status") == "blokada":
        reasons.append("gdos")
    if row.get("zakaz_status") == "zakaz":
        reasons.append("zakaz")
    return reasons


def site_type_entry(code, dictionaries: dict) -> dict | None:
    """Typ siedliskowy do karty: kod i nazwa ze slownika BDL (sam kod, gdy brak nazwy)."""
    if not isinstance(code, str) or not code.strip():
        return None
    code = code.strip()
    return {"code": code, "label": dictionaries.get("site_type", {}).get(code, code)}


def dominant_species_entry(code, dictionaries: dict) -> dict | None:
    """Gatunek panujacy z WFS (kod + nazwa ze slownika BDL) -- jedyny sklad wydzielenia bez paczki BDL."""
    if not isinstance(code, str) or not code.strip():
        return None
    code = code.strip()
    return {"code": code, "label": dictionaries.get("tree_species", {}).get(code, code)}


def age_years_int(value) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return int(round(float(value)))


def write_scores_json(stands: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [build_score_record(row, day) for _, row in stands.iterrows()]
    # allow_nan=False: fail loudly if some other field ever smuggles a NaN
    # past _json_safe, instead of silently writing invalid JSON again.
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


def export_stand_geometries(stands: gpd.GeoDataFrame, out_path) -> pathlib.Path:
    """Minimal id+geometry export -- the input the eventual tippecanoe/PMTiles
    packaging step (spec §9 step 11/12, out of scope for this plan, see
    Global Constraints) will consume once the frontend exists to read it."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stands[["stand_id", "geometry"]].to_parquet(out_path)
    return out_path


def export_stand_geometries_geojson(stands: gpd.GeoDataFrame, out_path) -> pathlib.Path:
    """Export minimal stand polygons in WGS84 for the static MapLibre UI."""
    if stands.crs is None:
        raise ValueError("Stand geometries require a source CRS")
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    geographic = stands[["stand_id", "geometry"]].to_crs("EPSG:4326")
    out_path.write_text(geographic.to_json(drop_id=True, na="null"), encoding="utf-8")
    return out_path


REGION_FIELDS = ["region_id", "rank_score", "stand_count", "stand_ids"]


def build_region_record(row, day: str) -> dict:
    """Matches spec §7.2's regions_{date}.json: the rejony list that becomes
    the application's main output, alongside the existing scores_{date}.json
    detail view."""
    record = {field: _json_safe(row[field]) for field in REGION_FIELDS}
    record["region_id"] = str(record["region_id"])
    record["rank_score"] = _json_safe(float(row["rank_score"]))
    record["stand_count"] = int(row["stand_count"])
    record["stand_ids"] = list(row["stand_ids"])
    record["day"] = day
    return record


def _share_label(part_cd: str, dictionaries: dict) -> str:
    return dictionaries.get("part", {}).get(part_cd, part_cd)


def _species_entries(species: list[tuple[str, str]], dictionaries: dict) -> list[dict]:
    tree_names = dictionaries.get("tree_species", {})
    return [
        {
            "species_cd": species_cd,
            "name": tree_names.get(species_cd, species_cd),
            "share": _share_label(part_cd, dictionaries),
        }
        for species_cd, part_cd in species
    ]


def build_details_record(stand_id: str, adr_for: str, stand_stru, prot_categ, day: str,
                           package_details_index: dict, neighbors_by_stand: dict, dictionaries: dict,
                           tie_break_index: dict, extra_features_index: dict | None = None,
                           access: dict | None = None, weather: dict | None = None,
                           habitat: dict | None = None, forest_district: str | None = None,
                           site_type=None, age_years=None, dominant_species=None) -> dict:
    """One card's worth of plan 2.1 step B3 detail (spec §5.3 pkt 3):
    species composition, density, understory, soil type -- from a BDL
    package when `adr_for` is covered by one (fields null/empty
    otherwise) -- plus neighbours and stand_stru/prot_categ, which come
    from WFS and are present regardless of package coverage. Purely
    additive: never touches H/F/R (see pipeline.bdl_package_details'
    module docstring for why that's structurally guaranteed, not just
    tested).

    Since plan 2.1 "Zmiana 4": also ground cover (word form) and the
    stand density index -- from pipeline.tie_break, empty/null when
    `adr_for` isn't covered by any package. Purely additive presentation
    fields: never touches H/F/R (see pipeline.tie_break's own module
    docstring)."""
    details = package_details_index.get(adr_for)
    prot_categ_name = None
    if prot_categ is not None and not (isinstance(prot_categ, float) and math.isnan(prot_categ)):
        prot_categ_name = dictionaries.get("prot_categ", {}).get(prot_categ, prot_categ)
    tie_break_raw = tie_break_index.get(adr_for)
    extra = (extra_features_index or {}).get(adr_for)
    return {
        "stand_id": stand_id,
        "day": day,
        # Plan Faza 3.5: odleglosci do punktow dostepu i element o najwiekszym
        # wkladzie w presje (None poza modelem pressure.model: access_points).
        "access": access,
        # Faza 4.3/4.5: skladniki pogody i udzial prognozy w oknie (prezentacja).
        "weather": weather,
        # Faza UI.2: skladniki siedliska (S_host, S_site, S_age) do rozwiniecia paska.
        "habitat": habitat,
        # Faza UI.3: nazwa nadlesnictwa z nazwy paczki BDL (bez polskich znakow) -- do nazwy
        # wydzielenia "Oddz. 96a · Nadl. Koszecin".
        "forest_district": forest_district,
        # Nowy frontend: typ siedliskowy (kod + nazwa) i wiek uzyty w modelu -- prezentacja.
        "site_type": site_type_entry(site_type, dictionaries),
        "age_years": age_years_int(age_years),
        # Gatunek panujacy z WFS: sklad, gdy wydzielenie nie ma paczki BDL (drzew_species puste).
        "dominant_species": dominant_species_entry(dominant_species, dictionaries),
        "drzew_species": _species_entries(details.drzew_species, dictionaries) if details else [],
        "density": (
            dictionaries.get("density", {}).get(details.density_cd, details.density_cd)
            if details and details.density_cd else None
        ),
        "podszyt_species": _species_entries(details.podszyt_species, dictionaries) if details else [],
        "soil_type": (
            dictionaries.get("soil_subtype", {}).get(details.soil_subtype_cd, details.soil_subtype_cd)
            if details and details.soil_subtype_cd else None
        ),
        "package_date": details.package_date if details else None,
        "neighbors": neighbors_by_stand.get(adr_for, []),
        "stand_stru": _json_safe(stand_stru),  # no BDL dictionary exists for this field (verified B3 research)
        "prot_categ": prot_categ_name,
        "veg_cover": veg_cover_label(tie_break_raw.veg_cover_cd) if tie_break_raw else None,
        "standdensity_index": _json_safe(tie_break_raw.standdensity_index) if tie_break_raw else None,
        # Plan 1.6.5: short practical note for the card, built from podszyt/
        # podrost presence + DRZEW zwarcie -- presentation only, never
        # affects R/sort order (pipeline.searchability's own docstring).
        "searchability_hint": searchability_hint(
            details.density_cd if details else None,
            details.podszyt_species if details else [],
            extra.podrost_species if extra else [],
        ),
    }


def write_details_json(stands: gpd.GeoDataFrame, package_details_index: dict, neighbors_by_stand: dict,
                         dictionaries: dict, day: str, out_path, tie_break_index: dict,
                         extra_features_index: dict | None = None,
                         profile: dict | None = None) -> pathlib.Path:
    """Plan 2.1 step B3: card-detail data (species composition, density,
    understory, soil type, neighbours, stand_stru/prot_categ) for every
    wydzielenie in `stands`, kept in its own file rather than
    scores_{day}.json -- adding this per stand there would have grown a
    real Będziemyśl export (6.6MB/4703 records) by an estimated 35-55%,
    even though a card's detail is opened for a handful of wydzielenia,
    while the "Wydzielenia" list (scores.json) is read on every load.
    Optional on the frontend, same pattern as regions_{day}.json: a
    missing details file just means no B3 section on the card, not an
    error.

    `tie_break_index` (plan 2.1 "Zmiana 4"):
    pipeline.tie_break.load_tie_break_raw's adr_for -> raw output, used
    only to render veg_cover/standdensity_index on the card
    (build_details_record) -- the numeric tie_break sort value itself
    lives in scores_{day}.json, not here."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        build_details_record(
            row["stand_id"], row["adr_for"], row.get("stand_stru"), row.get("prot_categ"),
            day, package_details_index, neighbors_by_stand, dictionaries, tie_break_index,
            extra_features_index=extra_features_index,
            access=build_access_card(row),
            weather=build_weather_card(row, profile),
            habitat=build_habitat_card(row, profile),
            forest_district=forest_district_name(row.get("nazwa")),
            site_type=row.get("site_type"),
            age_years=row.get("age_years"),
            dominant_species=row.get("species_cd"),
        )
        for _, row in stands.iterrows()
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


def forest_district_name(package_name) -> str | None:
    """"BDL_02_16_KOSZECIN_2026" -> "Koszecin" (bez polskich znakow -- tak nazywaja sie
    paczki BDL); None dla braku/innego formatu. Tylko prezentacja."""
    if not isinstance(package_name, str):
        return None
    parts = package_name.split("_")
    if len(parts) < 5 or parts[0] != "BDL":
        return None
    return " ".join(w.capitalize() for w in parts[3:-1]) or None


def build_habitat_card(row, profile: dict | None = None) -> dict | None:
    """Faza UI.2: skladniki H tego wydzielenia (S_host, S_site, S_age) i tryb wieku
    z profilu -- tylko prezentacja, wartosci wprost z modelu. None dla wiersza
    bez tych kolumn."""
    if "S_host" not in row.index:
        return None
    return {
        "S_host": _json_safe(row.get("S_host")),
        "S_site": _json_safe(row.get("S_site")),
        "S_age": _json_safe(row.get("S_age")),
        "age_mode": (profile or {}).get("habitat", {}).get("age_mode", "neutral"),
    }


def build_weather_card(row, profile: dict | None = None) -> dict | None:
    """Faza 4.3/4.5: skladniki pogody tego wydzielenia w postaci zrozumialej dla
    czlowieka (opad z 26 dni i typowy bilans, srednia temperatura 20 dni z optimum,
    przymrozek i kiedy) + F jako liczba i udzial prognozy w oknie 26 dni. Tylko
    prezentacja -- nic stad nie wraca do F/R. None dla wiersza bez tych kolumn."""
    if "p26_mm" not in row.index:
        return None
    cfg = (profile or {}).get("fruiting", {})
    tmin3 = _json_safe(row.get("tmin3_c"))
    if tmin3 is None:
        frost = None
    elif tmin3 < cfg.get("frost_tmin3_hard_c", -2.0):
        frost = "silny"
    elif tmin3 < cfg.get("frost_tmin3_soft_c", 0.0):
        frost = "slaby"
    else:
        frost = "brak"
    return {
        "p26_mm": _json_safe(row.get("p26_mm")),
        "cwb26_mm": _json_safe(row.get("cwb26_mm")),
        "cwb26_typical_mm": _json_safe(row.get("cwb26_typical_mm")),
        "pct_cwb26": _json_safe(row.get("pct_CWB26")),
        "tmean20_c": _json_safe(row.get("tmean20_c")),
        "temp_optimum_c": cfg.get("temp_optimum_c"),
        "tmin3_c": tmin3,
        "frost": frost,
        "frost_date": _text_or_none(row.get("tmin3_date")) if frost in ("slaby", "silny") else None,
        "F": _json_safe(row.get("F")),
        "M": _json_safe(row.get("M")),
        "T": _json_safe(row.get("T")),
        "K_frost": _json_safe(row.get("K_frost")),
        "G_season": _json_safe(row.get("G_season")),
        "forecast_days": _json_safe(row.get("forecast_days")),
        "forecast_window_share": _json_safe(row.get("forecast_window_share")),
    }


def _text_or_none(value) -> str | None:
    """Pusty tekst, None i NaN (pandas zamienia None w kolumnie tekstowej na
    NaN, a NaN jest "prawdziwe") -> None; inaczej tekst."""
    return value if isinstance(value, str) and value else None


def build_access_card(row) -> dict | None:
    """Plan Faza 3.5: dane karty z modelu punktow dostepu -- None, gdy P
    pochodzi z modelu gravity (albo wiersz nie ma kolumn punktow dostepu)."""
    if row.get("pressure_model") != "access_points":
        return None
    return {
        "d_parking_m": _json_safe(row.get("d_parking_m")),
        "d_entrance_m": _json_safe(row.get("d_entrance_m")),
        "d_hard_forest_road_m": _json_safe(row.get("d_hard_forest_road_m")),
        "top_point_id": _text_or_none(row.get("top_point_id")),
        "top_point_type": _text_or_none(row.get("top_point_type")),
        "top_point_source": _text_or_none(row.get("top_point_source")),
        "top_point_name": _text_or_none(row.get("top_point_name")),
        # Faza UI.2: wklad kazdego typu w surowa presje (model punktow dostepu),
        # z ktorego pasek "Spokoj" wybiera 2-3 najwazniejsze punkty.
        "pressure_contrib": {
            t: _json_safe(row.get(f"pcontrib_{t}"))
            for t in ("parking", "entrance", "gate", "road_fallback", "settlement", "forest_road")
            if f"pcontrib_{t}" in row.index
        },
    }


_NAMED_PLACE_CLASSES = ("city", "town", "village", "hamlet", "suburb", "locality", "isolated_dwelling")


def nearest_place(point_2180, places: gpd.GeoDataFrame | None) -> dict | None:
    """Faza UI.3: najblizsza nazwana miejscowosc OSM od punktu (EPSG:2180) -- do nazwy
    rejonu "Rejon 1 · kolo Lazisk". None, gdy brak miejscowosci z nazwa. Tylko
    prezentacja."""
    if places is None or len(places) == 0 or "name" not in places.columns:
        return None
    named = places[places["name"].fillna("").astype(str).str.len() > 0]
    if "place" in named.columns:
        named = named[named["place"].isin(_NAMED_PLACE_CLASSES)]
    if len(named) == 0:
        return None
    metric = named.to_crs("EPSG:2180") if named.crs is not None and str(named.crs) != "EPSG:2180" else named
    distances = metric.geometry.distance(point_2180)
    best = distances.idxmin()
    return {"name": str(named.loc[best, "name"]), "distance_m": round(float(distances.loc[best]))}


def write_regions_json(regions: gpd.GeoDataFrame, day: str, out_path,
                       places: gpd.GeoDataFrame | None = None) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Centroid computed in the regions' own (projected, metric) CRS and only
    # then reprojected to WGS84 -- computing a centroid directly in a
    # geographic CRS is inaccurate and triggers a geopandas UserWarning.
    # Without a location, a consumer of this file (map, navigation link)
    # cannot place a region at all (final review finding).
    centroids_4326 = regions.geometry.centroid.to_crs("EPSG:4326")
    records = []
    for (_, row), point, centroid_2180 in zip(regions.iterrows(), centroids_4326, regions.geometry.centroid):
        record = build_region_record(row, day)
        record["centroid_lat"] = point.y
        record["centroid_lon"] = point.x
        # Faza UI.3: najblizsza miejscowosc (nazwa rejonu w interfejsie); brak klucza
        # w plikach sprzed tej zmiany, null gdy nie ma miejscowosci z nazwa.
        if places is not None:
            record["near_place"] = nearest_place(centroid_2180, places)
        records.append(record)
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


def write_conditions_json(timeline: dict, day: str, out_path) -> pathlib.Path:
    """Plan A2 Plan-B: area conditions timeline
    (pipeline.conditions_timeline.build_conditions_timeline), optional on
    the frontend like regions/details."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"day": day, **timeline}, ensure_ascii=False, indent=2, allow_nan=False),
                        encoding="utf-8")
    return out_path


# Plan wdrozenia 1.2: per-stand intermediate values behind H/F/P/R, so a
# ranking can be audited (or R_final reconstructed, see the acceptance test
# in tests/test_export.py) without re-fetching any network source. Field
# names follow the plan's own spec §13.2 wording, not the DataFrame's
# internal column names, where the two differ (e.g. "Demand" -> "demand").
DIAGNOSTICS_FIELDS = [
    "S_host", "S_site", "S_age", "H", "pct_CWB26", "M", "T", "K_frost", "G_season", "F", "q", "F_loc",
    "P", "distance_method", "s_host_source", "s_host_package_date",
    # Plan 1.3: share sum < 0.9 in this stand's package composition (does not
    # apply to a WFS-sourced S_host, which has no share sum to check).
    "sklad_niepelny",
    # Plan 1.5.3: exp-weighted share of the P26w window whose rain came from
    # the IMGW radar rather than Open-Meteo's model -- per stand (its own 1 km
    # RainGRS series) in radar.mode: stand, per shared weather point otherwise.
    "rain_radar_coverage",
    # Plan 1.6.2: "skorygowano" / "wylaczona" / "brak_roku_stanu" -- whether
    # this stand's age was shifted to the analysis year, and why not when it
    # wasn't (pipeline.age_update.update_age).
    "age_update_status",
    # Plan 1.6.4: BDL package fields with no ranking weight (>=50% filled per
    # docs/BDL_slownik_pol.md) -- None/[] for a stand without package
    # coverage, never blended into H/F/R (pipeline.bdl_extra_features).
    "veg_cover_cd", "site_class_cd", "density_cd", "soil_subtype_cd", "degradation_cd",
    "stand_struct_cd", "podszyt_species", "podrost_species", "zabiegi_planowane",
    "rok_wskazan", "dist_do_granicy_oddzialu_m", "dlugosc_granicy_z_oddzialem_m",
]


# Plan Faza 3.4: wklad kazdego typu punktu w presje surowa i element o
# najwiekszym wkladzie. Opcjonalne (brak w wierszach sprzed Fazy 3).
OPTIONAL_DIAGNOSTICS_FIELDS = [
    "pressure_model", "P_gravity", "access_raw",
    "pcontrib_parking", "pcontrib_entrance", "pcontrib_gate", "pcontrib_road_fallback",
    "pcontrib_settlement", "pcontrib_forest_road",
    "top_point_id", "top_point_type", "d_parking_m", "d_entrance_m", "d_hard_forest_road_m",
]


def build_diagnostics_record(row, day: str) -> dict:
    record = {field: _json_safe(row[field]) for field in DIAGNOSTICS_FIELDS}
    for field in OPTIONAL_DIAGNOSTICS_FIELDS:
        if field in row.index:
            record[field] = _json_safe(row[field])
    record["day"] = day
    record["stand_id"] = row["stand_id"]
    record["mask"] = bool(row["mask"])
    record["Demand"] = _json_safe(row["demand"])
    record["d_park_m"] = _json_safe(row["d_park_m"])
    record["weather_point"] = {"lat": _json_safe(row["weather_point_lat"]),
                               "lon": _json_safe(row["weather_point_lon"])}
    record["climatology_cell"] = {"lat": _json_safe(row["climatology_cell_lat"]),
                                  "lon": _json_safe(row["climatology_cell_lon"])}
    # Plan 1.6: gdos_status/zakaz_status are computed once, in
    # pipeline.mvp.enrich_with_mvp_layers, and just read here -- both are
    # also in SCORE_FIELDS (scores.json), so this and the score record
    # always agree by construction instead of two places deriving the same
    # status from raw booleans.
    record["gdos_status"] = row["gdos_status"]
    record["zakaz_status"] = row["zakaz_status"]
    return record


def write_diagnostics_json(stands: gpd.GeoDataFrame, day: str, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [build_diagnostics_record(row, day) for _, row in stands.iterrows()]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out_path


_DIAGNOSTICS_SIZE_LIMIT_BYTES = 20 * 1024 * 1024


def write_diagnostics(stands: gpd.GeoDataFrame, day: str, out_dir) -> pathlib.Path:
    """Plan 1.2: JSON normally, parquet when that would exceed ~20 MB (spec
    §13.2's own "lub parquet, jesli rozmiar > 20 MB"). Writes JSON first and
    only switches format if it's actually too big, rather than guessing from
    row count -- record size varies enough (nested weather_point/
    climatology_cell dicts, nullable fields) that a byte-count check on the
    real output is more honest than a row-count heuristic."""
    out_dir = pathlib.Path(out_dir)
    json_path = out_dir / f"diagnostics_{day}.json"
    write_diagnostics_json(stands, day, json_path)
    if json_path.stat().st_size <= _DIAGNOSTICS_SIZE_LIMIT_BYTES:
        return json_path
    json_path.unlink()
    records = [build_diagnostics_record(row, day) for _, row in stands.iterrows()]
    parquet_path = out_dir / f"diagnostics_{day}.parquet"
    pd.DataFrame(records).to_parquet(parquet_path)
    return parquet_path


# Plan wdrozenia 1.1: one run_manifest_YYYY-MM-DD.json per run_trip_preparation
# call, alongside the other exports. pipeline.prepare_trip.build_manifest
# assembles the dict from values already computed during the run (git state,
# profile hash, orchestrate.py's scored.attrs["diagnostics"], tile/entrance/
# zakaz counters) -- this function only serializes it, same pattern as the
# other write_*_json helpers above.
def write_manifest_json(manifest: dict, out_path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False),
                        encoding="utf-8")
    return out_path
