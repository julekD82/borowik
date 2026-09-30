import type {
  AccessCollection, ConditionsDay, ConditionsTimeline, Region, Score, SpeciesShare, StandDetail, StandFeature,
  StandView, Stands, TripMeta,
} from "./types";
import { finite } from "../domain/format";
import { vertices } from "../domain/geometry";
import { joinData } from "../domain/ranking";

// Zwraca kolekcje albo null, gdy plik jest nieobecny; zle uksztaltowany to blad.
export function parseAccessCollection(raw: unknown, file: string): AccessCollection | null {
  if (raw === undefined) return null;
  if (!object(raw) || raw.type !== "FeatureCollection" || !Array.isArray(raw.features))
    throw new Error(`Plik ${file} jest niepoprawny. Uruchom synchronizację danych.`);
  return raw as unknown as AccessCollection;
}

export const object = (x: unknown): x is Record<string, unknown> =>
  !!x && typeof x === "object" && !Array.isArray(x);

export const strings = (x: unknown): x is string[] =>
  Array.isArray(x) && x.every((v) => typeof v === "string");

export const numeric = (x: unknown) => x === null || finite(x);

export const isoDate = (x: unknown) =>
  typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x);

export const nullableString = (x: unknown) => x === null || typeof x === "string";

const speciesShare = (x: unknown): x is SpeciesShare =>
  object(x) &&
  typeof x.species_cd === "string" &&
  typeof x.name === "string" &&
  typeof x.share === "string";

export function parseData(
  rawScores: unknown,
  rawStands: unknown,
  rawRegions?: unknown,
  rawDetails?: unknown,
  rawRegionsNoPressure?: unknown,
): {
  entries: StandView[];
  scores: Score[];
  stands: Stands;
  regions: Region[];
  // Faza UI.1: rejony liczone bez presji grzybiarzy; null = brak pliku (starsza migawka).
  regionsNoPressure: Region[] | null;
  details: StandDetail[];
} {
  if (
    !Array.isArray(rawScores) ||
    !rawScores.every(
      (s) =>
        object(s) &&
        typeof s.stand_id === "string" &&
        isoDate(s.day) &&
        typeof s.mask === "boolean" &&
        ["R", "H", "F", "F_loc", "P"].every((k) => numeric(s[k])) &&
        typeof s.confidence === "string" &&
        strings(s.confidence_reasons) &&
        typeof s.distance_method === "string" &&
        typeof s.entrance_status === "string" &&
        (s.d_park_m === undefined || numeric(s.d_park_m)) &&
        (s.area_ha === undefined || numeric(s.area_ha)) &&
        (s.G_season === undefined || numeric(s.G_season)) &&
        (s.tie_break === undefined || numeric(s.tie_break)) &&
        (s.R_bez_presji === undefined || numeric(s.R_bez_presji)) &&
        (s.M === undefined || numeric(s.M)) &&
        (s.pct_CWB26 === undefined || numeric(s.pct_CWB26)) &&
        (s.rain_radar_coverage === undefined || numeric(s.rain_radar_coverage)) &&
        (s.zakaz_status === undefined || typeof s.zakaz_status === "string") &&
        (s.gdos_status === undefined || typeof s.gdos_status === "string") &&
        Array.isArray(s.explanation) &&
        s.explanation.every(
          (e) =>
            object(e) &&
            typeof e.text === "string" &&
            typeof e.factor === "string" &&
            finite(e.contribution),
        ),
    )
  )
    throw new Error("Niepoprawny plik wyników wydzieleń.");
  if (
    !object(rawStands) ||
    rawStands.type !== "FeatureCollection" ||
    !Array.isArray(rawStands.features)
  )
    throw new Error("Niepoprawny plik geometrii.");
  for (const f of rawStands.features) {
    if (
      !object(f) ||
      f.type !== "Feature" ||
      !object(f.properties) ||
      typeof f.properties.stand_id !== "string" ||
      !object(f.geometry) ||
      !["Polygon", "MultiPolygon"].includes(String(f.geometry.type)) ||
      !Array.isArray(f.geometry.coordinates)
    )
      throw new Error("Niepoprawna geometria wydzielenia.");
    try {
      const points = vertices(f as unknown as StandFeature);
      if (
        !points.length ||
        !points.every(
          (p) =>
            Array.isArray(p) &&
            finite(p[0]) &&
            finite(p[1]) &&
            Math.abs(p[0]) <= 180 &&
            Math.abs(p[1]) <= 90,
        )
      )
        throw new Error();
    } catch {
      throw new Error("Geometria musi używać współrzędnych WGS84.");
    }
  }
  const scores = rawScores as Score[],
    stands = rawStands as unknown as Stands;
  if (new Set(scores.map((s) => s.day)).size > 1)
    throw new Error(
      "Pliki pochodzą z różnych dat. Zsynchronizuj dane ponownie.",
    );
  const standIds = stands.features.map((f) => f.properties.stand_id);
  for (const ids of [scores.map((s) => s.stand_id), standIds])
    if (new Set(ids).size !== ids.length)
      throw new Error("Powtórzone identyfikatory w danych.");

  // Regions are optional: absent (undefined) means "no region export for
  // this bundle" -- an empty list, not an error, so the per-stand view
  // still loads. If a value IS provided, it must be well-formed and
  // consistent, same as scores/stands above.
  const knownIds = new Set(standIds);
  const parseRegions = (raw: unknown, label: string): Region[] => {
    if (
      !Array.isArray(raw) ||
      !raw.every(
        (r) =>
          object(r) &&
          typeof r.region_id === "string" &&
          finite(r.rank_score) &&
          finite(r.stand_count) &&
          isoDate(r.day) &&
          finite(r.centroid_lat) &&
          finite(r.centroid_lon) &&
          strings(r.stand_ids) &&
          r.stand_ids.length > 0 &&
          (r.near_place === undefined ||
            r.near_place === null ||
            (object(r.near_place) &&
              typeof r.near_place.name === "string" &&
              finite(r.near_place.distance_m))),
      )
    )
      throw new Error(`Niepoprawny plik rejonów${label}.`);
    const parsed = raw as Region[];
    if (parsed.some((r) => r.day !== scores[0]?.day))
      throw new Error(
        `Plik rejonów${label} pochodzi z innej daty. Zsynchronizuj dane ponownie.`,
      );
    if (parsed.some((r) => r.stand_ids.some((id) => !knownIds.has(id))))
      throw new Error(
        `Rejon${label} odwołuje się do wydzielenia spoza zsynchronizowanego zestawu.`,
      );
    return parsed;
  };
  const regions: Region[] = rawRegions !== undefined ? parseRegions(rawRegions, "") : [];
  const regionsNoPressure: Region[] | null =
    rawRegionsNoPressure !== undefined ? parseRegions(rawRegionsNoPressure, " bez presji") : null;
  // Details are optional, same pattern as regions above: absent means no
  // B3 section on a stand's card, not an error. When present, one entry per
  // wydzielenie is expected but not required -- a stand missing from
  // `details` just has no B3 section either.
  let details: StandDetail[] = [];
  if (rawDetails !== undefined) {
    const knownStandIds = new Set(standIds);
    if (
      !Array.isArray(rawDetails) ||
      !rawDetails.every(
        (d) =>
          object(d) &&
          typeof d.stand_id === "string" &&
          isoDate(d.day) &&
          Array.isArray(d.drzew_species) &&
          d.drzew_species.every(speciesShare) &&
          nullableString(d.density) &&
          Array.isArray(d.podszyt_species) &&
          d.podszyt_species.every(speciesShare) &&
          nullableString(d.soil_type) &&
          nullableString(d.package_date) &&
          strings(d.neighbors) &&
          nullableString(d.stand_stru) &&
          nullableString(d.prot_categ) &&
          (d.veg_cover === undefined || nullableString(d.veg_cover)) &&
          (d.standdensity_index === undefined || d.standdensity_index === null || finite(d.standdensity_index)) &&
          (d.searchability_hint === undefined || nullableString(d.searchability_hint)) &&
          (d.access === undefined || d.access === null || object(d.access)) &&
          (d.habitat === undefined || d.habitat === null || object(d.habitat)) &&
          (d.forest_district === undefined || nullableString(d.forest_district)),
      )
    )
      throw new Error("Niepoprawny plik szczegółów wydzieleń.");
    details = rawDetails as StandDetail[];
    if (details.some((d) => d.day !== scores[0]?.day))
      throw new Error(
        "Plik szczegółów pochodzi z innej daty. Zsynchronizuj dane ponownie.",
      );
    if (details.some((d) => !knownStandIds.has(d.stand_id)))
      throw new Error(
        "Szczegóły odwołują się do wydzielenia spoza zsynchronizowanego zestawu.",
      );
  }

  return { entries: joinData(scores, stands), scores, stands, regions, regionsNoPressure, details };
}

function isConditionsDay(value: unknown): value is ConditionsDay {
  const d = value as Record<string, unknown> | null;
  return (
    !!d &&
    typeof d.date === "string" &&
    typeof d.F === "number" &&
    Number.isFinite(d.F) &&
    [0, 1, 2, 3].includes(d.level as number) &&
    typeof d.forecast === "boolean"
  );
}

export function parseConditions(raw: unknown, day: string | undefined): ConditionsTimeline | null {
  if (raw === undefined) return null;
  const c = raw as Record<string, unknown> | null;
  if (
    !c ||
    typeof c !== "object" ||
    c.day !== day ||
    typeof c.summary !== "string" ||
    !Array.isArray(c.rains) ||
    !Array.isArray(c.days) ||
    !c.days.every(isConditionsDay)
  )
    throw new Error("Plik conditions.json jest niepoprawny. Uruchom synchronizację danych.");
  return c as unknown as ConditionsTimeline;
}

export function parseTrips(raw: unknown): TripMeta[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (t): t is TripMeta =>
      object(t) &&
      typeof t.id === "string" &&
      t.id.length > 0 &&
      typeof t.name === "string" &&
      t.name.length > 0 &&
      finite(t.radius_km) &&
      isoDate(t.day) &&
      finite(t.lat) &&
      finite(t.lon) &&
      typeof t.saved_at === "string",
  );
}
