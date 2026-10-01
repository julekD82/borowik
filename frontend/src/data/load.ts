import type { AccessCollection, Analysis, StandDetail, TripMeta } from "./types";
import { parseAccessCollection, parseConditions, parseData, parseDetails, parseManifest, parseTrips } from "./parse";

const isJsonResponse = (response: Response) => response.headers.get("content-type")?.includes("json") ?? false;

// Serwer Vite odpowiada na brakujacy plik strona index.html (200, text/html) zamiast 404, wiec
// plik opcjonalny bez naglowka JSON traktujemy jak brak. Plik wymagany sprawdza sam JSON.parse.
export async function fetchJson(basePath: string, file: string, required: boolean): Promise<unknown> {
  const response = await fetch(`${import.meta.env.BASE_URL}${basePath}${file}`, {
    cache: "no-cache",
    signal: AbortSignal.timeout(60000),
  }).catch(() => undefined);
  if (!response?.ok || (!required && !isJsonResponse(response))) {
    if (required)
      throw new Error(`Nie udało się wczytać ${file}. Przygotuj i zsynchronizuj dane przed otwarciem mapy.`);
    return undefined;
  }
  try {
    return await response.json();
  } catch {
    throw new Error(`Plik ${file} jest niedostępny lub niepoprawny. Uruchom synchronizację danych.`);
  }
}

export type AnalysisInput = {
  basePath: string;
  scoresRaw: unknown;
  standsRaw: unknown;
  regionsRaw?: unknown;
  regionsNoPressureRaw?: unknown;
  conditionsRaw?: unknown;
  manifestRaw?: unknown;
};

export function buildAnalysis(input: AnalysisInput): Analysis {
  const parsed = parseData(input.scoresRaw, input.standsRaw, input.regionsRaw, undefined, input.regionsNoPressureRaw);
  const day = parsed.scores[0]?.day ?? "";
  return {
    basePath: input.basePath,
    day,
    scores: parsed.scores,
    scoreById: new Map(parsed.scores.map((s) => [s.stand_id, s])),
    features: new Map(parsed.stands.features.map((f) => [f.properties.stand_id, f])),
    entries: parsed.entries,
    regions: parsed.regions,
    regionsNoPressure: parsed.regionsNoPressure,
    conditions: parseConditions(input.conditionsRaw, day),
    manifest: parseManifest(input.manifestRaw),
  };
}

// Pierwszy widok: wyniki, geometrie, rejony, warunki, manifest.
export async function loadCore(basePath: string): Promise<Analysis> {
  const [scoresRaw, standsRaw] = await Promise.all([
    fetchJson(basePath, "scores.json", true),
    fetchJson(basePath, "stands.geojson", true),
  ]);
  const [regionsRaw, regionsNoPressureRaw, conditionsRaw, manifestRaw] = await Promise.all(
    ["regions.json", "regions_bez_presji.json", "conditions.json", "manifest.json"].map((file) =>
      fetchJson(basePath, file, false),
    ),
  );
  return buildAnalysis({ basePath, scoresRaw, standsRaw, regionsRaw, regionsNoPressureRaw, conditionsRaw, manifestRaw });
}

export type Background = {
  details: Map<string, StandDetail>;
  accessPoints: AccessCollection | null;
  forestRoads: AccessCollection | null;
};

// W tle, po pierwszym widoku: szczegoly (ok. 43 MB) i warstwy dostepu.
export async function loadBackground(analysis: Analysis): Promise<Background> {
  const [detailsRaw, pointsRaw, roadsRaw] = await Promise.all(
    ["details.json", "access_points.json", "forest_roads.json"].map((file) => fetchJson(analysis.basePath, file, false)),
  );
  const list = parseDetails(detailsRaw, analysis.day, new Set(analysis.features.keys()));
  return {
    details: new Map(list.map((d) => [d.stand_id, d])),
    accessPoints: parseAccessCollection(pointsRaw, "access_points.json"),
    forestRoads: parseAccessCollection(roadsRaw, "forest_roads.json"),
  };
}

// index.json is optional and, unlike scores/stands/regions/details, is
// appended to incrementally by the launcher over time -- a single bad
// entry (or a missing/corrupted file) means "fewer saved trips to show",
// never a load failure for the live analysis. Tolerant pattern, not
// parseData's throw-on-invalid pattern.
export async function loadTrips(): Promise<TripMeta[]> {
  try {
    const response = await fetch(
      `${import.meta.env.BASE_URL}data/trips/index.json`,
      { cache: "no-cache", signal: AbortSignal.timeout(20000) },
    );
    if (!response.ok) return [];
    return parseTrips(await response.json());
  } catch {
    return [];
  }
}

// ---- Faza 4.3-4.5: skladniki pogody, niepewnosc prognozy (czyste funkcje, testowane) ----
