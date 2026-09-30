// Budowanie danych do testow (nie jest plikiem testowym). Wartosci jak w prawdziwym eksporcie
// z Zawadzkiego 30.09.2026, uproszczone.
import type { Analysis, ConditionsTimeline, DailyWeather, Region, Score, StandDetail, StandFeature, Stands } from "./data/types";
import { buildAnalysis } from "./data/load";

export const DAY = "2026-09-30";

export function addDays(day: string, k: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + k);
  return d.toISOString().slice(0, 10);
}

export function makeScore(id: string, over: Partial<Score> = {}): Score {
  return {
    stand_id: id, H: 0.9, F: 0.7, F_loc: 0.7, P: 0.2, R: 60, R_bez_presji: 63, M: 0.8, mask: true, day: DAY,
    confidence: "SREDNIA", confidence_reasons: [], explanation: [], distance_method: "access_points",
    entrance_status: "not_evaluated", area_ha: 2, tie_break: 0.5, mask_reason: [], ...over,
  };
}

export function squareFeature(id: string, i: number): StandFeature {
  const x = 18.4 + (i % 50) * 0.01;
  const y = 50.6 + Math.floor(i / 50) * 0.01;
  return {
    type: "Feature",
    properties: { stand_id: id },
    geometry: { type: "Polygon", coordinates: [[[x, y], [x + 0.005, y], [x + 0.005, y + 0.005], [x, y + 0.005], [x, y]]] },
  };
}

export function makeStands(ids: string[]): Stands {
  return { type: "FeatureCollection", features: ids.map((id, i) => squareFeature(id, i)) };
}

export function makeRegion(id: string, rank: number, standIds: string[], over: Partial<Region> = {}): Region {
  return {
    region_id: id, rank_score: rank, stand_count: standIds.length, stand_ids: standIds, day: DAY,
    centroid_lat: 50.61, centroid_lon: 18.41, near_place: { name: "Łaziska", distance_m: 1800 }, ...over,
  };
}

export function makeDetail(id: string, over: Partial<StandDetail> = {}): StandDetail {
  return {
    stand_id: id, day: DAY,
    drzew_species: [{ species_cd: "SO", name: "sosna zwyczajna", share: "udział 100 %" }],
    density: "0.9", podszyt_species: [], soil_type: "Gleby bielicowe", package_date: "2026-06-23",
    neighbors: [], stand_stru: "DRZEW", prot_categ: null, veg_cover: "zadarniona", standdensity_index: 0.9,
    searchability_hint: null,
    access: {
      d_parking_m: 2395, d_entrance_m: 2401, d_hard_forest_road_m: 1245, top_point_id: "p1",
      top_point_type: "parking", top_point_source: "bdl", top_point_name: null,
      pressure_contrib: { parking: 92, forest_road: 13 },
    },
    weather: null, habitat: null, forest_district: "Zawadzkie",
    site_type: { code: "BMSW", label: "Bór mieszany świeży" }, age_years: 64, ...over,
  };
}

export function makeConditions(over: Partial<ConditionsTimeline> = {}): ConditionsTimeline {
  const daily: DailyWeather[] = [];
  for (let k = -35; k <= 6; k++)
    daily.push({
      date: addDays(DAY, k), precip_mm: k === -8 ? 11.8 : k === -7 ? 7.1 : 0, radar_share: k <= 0 ? 1 : 0,
      tmin_c: 8, tmax_c: 22, forecast: k > 0,
    });
  return {
    day: DAY, generated_for: DAY, horizon_days: 7, pulse_min_mm: 12.7, lookback_days: 45,
    rains: [{ start: "2026-09-20", end: "2026-09-24", rain_mm: 30.7, days_ago: 6 }],
    summary: "Ostatni większy deszcz: 20–24.09 (30.7 mm), 6 dni temu",
    days: [{
      date: DAY, F: 0.64, level: 2, forecast: false, uncertainty: "ok",
      components: { cwb26_mm: -2, cwb26_typical_mm: -3.8, pct_cwb26: 0.54, tmean20_c: 13.7, temp_optimum_c: 13, tmin3_c: 8.7 },
    }],
    daily,
    rain26: {
      sum_mm: 59.6, window_start: addDays(DAY, -25), window_end: DAY, normal_mm: 48, pct: 0.71,
      normal_source: "E-OBS v33.0e, 1991–2020", normal_cells: 12,
    },
    warnings: [{ type: "frost", dates: [] }, { type: "heat_drought", dates: [] }],
    ...over,
  };
}

// Eksport sprzed nowego frontendu: bez daily, rain26, warnings, lookback_days.
export function legacyConditions(): ConditionsTimeline {
  const c: Partial<ConditionsTimeline> = { ...makeConditions() };
  delete c.daily;
  delete c.rain26;
  delete c.warnings;
  delete c.lookback_days;
  return c as ConditionsTimeline;
}

export function makeAnalysis(opts: {
  scores: Score[];
  regions?: Region[];
  regionsNoPressure?: Region[];
  conditions?: ConditionsTimeline;
  manifest?: unknown;
}): Analysis {
  return buildAnalysis({
    basePath: "data/",
    scoresRaw: opts.scores,
    standsRaw: makeStands(opts.scores.map((s) => s.stand_id)),
    regionsRaw: opts.regions,
    regionsNoPressureRaw: opts.regionsNoPressure,
    conditionsRaw: opts.conditions,
    manifestRaw: opts.manifest ?? { lat: 50.6191, lon: 18.4611, radius_km: 20, day: DAY },
  });
}
