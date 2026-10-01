import type { Feature, FeatureCollection, Geometry, Polygon, MultiPolygon } from "geojson";

export type Explanation = {
  factor: string;
  contribution: number;
  text: string;
};

export type Score = {
  stand_id: string;
  H: number | null;
  F: number | null;
  F_loc: number | null;
  P: number | null;
  R: number | null;
  mask: boolean;
  day: string;
  confidence: string;
  confidence_reasons: string[];
  explanation: Explanation[];
  distance_method: string;
  entrance_status: string;
  d_park_m?: number | null;
  // Plan 2.1 step A4: optional so older exports (before this field existed)
  // still load -- see isStandaloneTarget below.
  area_ha?: number | null;
  // Plan 2.1 "Zmiana 1": seasonal fruiting-frequency multiplier, same
  // shape as area_ha above -- optional so older exports (before this
  // field existed) still load.
  G_season?: number | null;
  // Plan 2.1 "Zmiana 4": ground-cover/density ordinal secondary sort key
  // (pipeline.tie_break), same optional-field pattern as area_ha/G_season.
  tie_break?: number | null;
  // Plan 2026-09-26 A1: exp-weighted share of the P26w window whose rain
  // came from the IMGW radar (pipeline.radar), same optional-field pattern.
  rain_radar_coverage?: number | null;
  // Plan wdrozenia 1.6: "sprawdzono brak blokady" vs "nie sprawdzono" vs
  // "zrodlo zawiodlo" (zakaz_status) / kafel pominiety z powodu bledu sieci
  // (gdos_status) -- same optional-field pattern as the others above.
  zakaz_status?: string;
  gdos_status?: string;
  // Faza UI.1: wynik bez presji grzybiarzy, 100 * H * F_loc (alpha = 0) -- brak w
  // eksportach sprzed tej zmiany (przelacznik presji jest wtedy nieaktywny).
  R_bez_presji?: number | null;
  // Tryb mapy "Wilgotnosc": skladowa M (0-1) i percentyl bilansu wodnego z 26 dni, dla
  // wszystkich wydzielen (rowniez poza maska); brak w migawkach sprzed tej zmiany.
  M?: number | null;
  pct_CWB26?: number | null;
  // Nowy frontend: powody odrzucenia przez filtry modelu (pusta lista w masce); brak w starszych eksportach.
  mask_reason?: string[];
  s_host_source?: string | null;
  s_host_package_date?: string | null;
};

export type StandFeature = Feature<
  Polygon | MultiPolygon,
  { stand_id: string }
>;

export type Stands = FeatureCollection<
  Polygon | MultiPolygon,
  { stand_id: string }
>;

export type StandView = {
  score: Score;
  feature: StandFeature;
  point: [number, number];
  // Wynik uzywany w rankingu, na mapie i w karcie: R przy wlaczonej presji
  // grzybiarzy, R_bez_presji przy wylaczonej (Faza UI.1).
  r: number;
};

// Plan 2.1 step B3 (spec §5.3 pkt 3): card-detail data only -- never fed
// into H/F/R (see pipeline.bdl_package_details' module docstring and
// tests/test_prepare_trip.py's explicit regression check on the Python
// side). drzew_species/density/podszyt_species/soil_type/package_date come
// from a BDL package and are empty/null when the wydzielenie has none;
// neighbors/stand_stru/prot_categ come from WFS and are present regardless.
export type SpeciesShare = {
  species_cd: string;
  name: string;
  share: string;
};

export type AccessCard = {
  d_parking_m: number | null;
  d_entrance_m: number | null;
  d_hard_forest_road_m: number | null;
  top_point_id: string | null;
  top_point_type: string | null;
  top_point_source: string | null;
  top_point_name: string | null;
  // Faza UI.2: wklad kazdego typu punktu w surowa presje (opcjonalne w plikach sprzed UI).
  pressure_contrib?: Record<string, number | null>;
};

export type AccessCollection = FeatureCollection<Geometry, Record<string, unknown>>;

// Plan Faza 3.5: warstwy punktow dostepu przelaczane w legendzie.
export type AccessLayerId =
  | "parkings"
  | "entrances"
  | "roads"
  | "fire"
  | "settlements"
  | "pressure";

export type StandDetail = {
  stand_id: string;
  day: string;
  drzew_species: SpeciesShare[];
  density: string | null;
  podszyt_species: SpeciesShare[];
  soil_type: string | null;
  package_date: string | null;
  neighbors: string[];
  stand_stru: string | null;
  prot_categ: string | null;
  // Plan 2.1 "Zmiana 4": word-form ground cover + numeric stand density
  // index, next to the existing `density` (zwarcie) field -- null when
  // adr_for isn't covered by any package, same as the other package-only
  // fields above. Optional (unlike this type's other fields): a
  // details_{day}.json written before this field existed has no key for
  // it at all, not even null -- final review finding, real synced
  // frontend/public/data/details.json failed to load without this.
  veg_cover?: string | null;
  standdensity_index?: number | null;
  // Plan 1.6.5: short practical note built from podszyt/podrost presence +
  // DRZEW zwarcie (pipeline.searchability) -- presentation only, same
  // optional-field caveat as veg_cover/standdensity_index above (a
  // details_{day}.json written before this field existed has no key for
  // it at all).
  searchability_hint?: string | null;
  // Plan Faza 3.5: odleglosci do punktow dostepu i element o najwiekszym
  // wkladzie w presje; null/brak poza modelem pressure.model: access_points.
  access?: AccessCard | null;
  // Faza 4.3/4.5: skladniki pogody tego wydzielenia (tylko prezentacja, nie wplywaja na F/R);
  // brak/null w plikach sprzed Fazy 4.
  weather?: WeatherCard | null;
  // Faza UI.2/UI.3: skladniki siedliska i nazwa nadlesnictwa (brak w plikach sprzed UI).
  habitat?: HabitatCard | null;
  forest_district?: string | null;
  // Nowy frontend: typ siedliskowy i wiek uzyty w modelu; brak w starszych eksportach.
  site_type?: SiteType | null;
  // Gatunek panujacy z WFS (kod + nazwa): jedyny sklad wydzielenia bez paczki BDL; brak w starszych eksportach.
  dominant_species?: SiteType | null;
  age_years?: number | null;
};

export type HabitatCard = {
  S_host: number | null;
  S_site: number | null;
  S_age: number | null;
  age_mode: string | null;
};

export type WeatherCard = {
  p26_mm: number | null;
  cwb26_mm: number | null;
  cwb26_typical_mm: number | null;
  pct_cwb26: number | null;
  tmean20_c: number | null;
  temp_optimum_c: number | null;
  tmin3_c: number | null;
  frost: "brak" | "slaby" | "silny" | null;
  frost_date: string | null;
  F: number | null;
  // Faza UI.2: skladniki F wprost z modelu (opcjonalne w plikach sprzed UI).
  M?: number | null;
  T?: number | null;
  K_frost?: number | null;
  forecast_days: number | null;
  forecast_window_share: number | null;
};

export type Region = {
  region_id: string;
  rank_score: number;
  stand_count: number;
  stand_ids: string[];
  day: string;
  centroid_lat: number;
  centroid_lon: number;
  // Faza UI.3: najblizsza nazwana miejscowosc (OSM); brak w plikach sprzed tej zmiany.
  near_place?: { name: string; distance_m: number } | null;
};

export type RegionView = {
  region: Region;
  // The highest-R member stand -- its H/F/confidence/distance/explanation
  // fields stand in for the region's own on a card, same derivation the
  // frontend design spec settled on (regions.json carries no such fields
  // of its own).
  top: StandView;
  // Only the members actually present in `entries` (already mask+finite-R
  // filtered by joinData) -- a region can legitimately reference a member
  // that didn't make it through that filter; it's shown with what remains,
  // not dropped outright unless nothing does.
  members: StandView[];
};

export type ConditionsComponents = {
  cwb26_mm: number | null;
  cwb26_typical_mm: number | null;
  pct_cwb26: number | null;
  tmean20_c: number | null;
  temp_optimum_c: number | null;
  tmin3_c: number | null;
};

export type ForecastUncertainty = "ok" | "uncertain" | "indicative";

export type ConditionsDay = {
  date: string;
  F: number;
  level: 0 | 1 | 2 | 3;
  forecast: boolean;
  // Faza 4.3-4.5 (opcjonalne: conditions_{day}.json sprzed Fazy 4 ich nie ma)
  days_ahead?: number;
  uncertainty?: ForecastUncertainty;
  components?: ConditionsComponents;
  frost_area_share?: number;
  heavy_rain_area_share?: number;
};

export type ConditionsRain = { start: string; end: string; rain_mm: number; days_ago: number };

export type ConditionsTimeline = {
  day: string;
  generated_for: string;
  horizon_days: number;
  pulse_min_mm: number;
  rains: ConditionsRain[];
  summary: string;
  days: ConditionsDay[];
  // Nowy frontend (panel pogody); brak w starszych eksportach.
  lookback_days?: number;
  daily?: DailyWeather[];
  rain26?: Rain26 | null;
  warnings?: WeatherWarning[];
};

export type TripMeta = {
  id: string;
  name: string;
  radius_km: number;
  day: string;
  lat: number;
  lon: number;
  saved_at: string;
};

export type SiteType = { code: string; label: string };
export type DailyWeather = {
  date: string;
  precip_mm: number | null;
  radar_share: number;
  tmin_c: number | null;
  tmax_c: number | null;
  forecast: boolean;
};
export type Rain26 = {
  sum_mm: number;
  window_start: string;
  window_end: string;
  normal_mm: number | null;
  pct: number | null;
  normal_source: string | null;
  normal_cells: number;
};
export type WeatherWarning = { type: string; dates: string[] };
export type Manifest = {
  lat: number | null;
  lon: number | null;
  radius_km: number | null;
  day: string | null;
  pressure_alpha: number | null;
};
export type Analysis = {
  basePath: string;
  day: string;
  scores: Score[];
  scoreById: Map<string, Score>;
  features: Map<string, StandFeature>;
  // Wydzielenia w masce z wynikiem, uszeregowane jak dotad (presja wlaczona).
  entries: StandView[];
  regions: Region[];
  regionsNoPressure: Region[] | null;
  conditions: ConditionsTimeline | null;
  manifest: Manifest;
};
