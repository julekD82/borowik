import type {
  Feature,
  FeatureCollection,
  Geometry,
  Polygon,
  MultiPolygon,
  Position,
} from "geojson";

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
};
export const finite = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

// Same strict upper bounds as profiles/boletus_edulis.yaml::fruiting_classes.
export function fruitingClass(value: number | null | undefined): string {
  if (!finite(value) || value < 0 || value > 1) return "Brak danych";
  return value < 0.2
    ? "Słabe warunki"
    : value < 0.45
      ? "Umiarkowane"
      : value < 0.7
        ? "Dobre"
        : "Bardzo dobre";
}
export function habitatClass(value: number | null | undefined): string {
  if (!finite(value)) return "Brak danych";
  return value < 0.4
    ? "Niski potencjał"
    : value < 0.7
      ? "Średni potencjał"
      : "Wysoki potencjał";
}
// Plan 2.1 step A4 (docs/projekt-borowik.md §5.2/§13.1): a stand this small
// isn't worth a dedicated trip as a standalone destination -- presentation
// filter only, never a mask (pipeline.habitat.passes_mask is unaffected):
// small stands still count toward their region's area (pipeline/regions.py,
// A2) and stay in scores/stands exports (pipeline/export.py). Kept here,
// not in profiles/*.yaml: this number never feeds Python scoring/H/F/R --
// putting it in the profile would misleadingly imply it does, and would
// need a new export field wired through just to carry a value the backend
// itself never uses. This is the one place it's defined; isStandaloneTarget
// is the one place it's applied (main.ts's visibleEntries).
export const MIN_STANDALONE_AREA_HA = 0.5;
export function isStandaloneTarget(score: Score): boolean {
  // area_ha absent (older export, before this field existed) or null
  // (should not happen post-A4, but geometry could theoretically be empty)
  // means "unknown area" -- don't hide it, rather than treating unknown as
  // "too small".
  return !finite(score.area_ha) || score.area_ha >= MIN_STANDALONE_AREA_HA;
}
// BDL stand_stru codes (WFS). The data packages carry no dictionary for this
// field, so the few codes seen in real data are expanded here; KO/KDO are
// regeneration classes, not a storey count, hence the code kept in brackets.
const STAND_STRUCTURE: Record<string, string> = {
  DRZEW: "jednopiętrowy",
  "2 PIET": "dwupiętrowy",
  "W PIET": "wielopiętrowy",
  KO: "klasa odnowienia (KO)",
  KDO: "klasa do odnowienia (KDO)",
};
export function standStructureLabel(code: string): string {
  const key = code.trim().toUpperCase().replace("Ę", "E");
  return STAND_STRUCTURE[key] ?? code;
}
// f_density_dic mixes descriptive entries (pełne, umiarkowane...) with plain
// numbers 0.0-1.0; a bare "0.9" on the card needs its scale spelled out.
export function densityLabel(value: string | null): string {
  if (!value) return "brak danych";
  return /^\d(\.\d+)?$/.test(value.trim()) ? `${value.trim()} (skala 0–1)` : value;
}
// pipeline/neighbors.py lists only distinguishing neighbours (non-stand
// areas, other dominant species, stands < 20 years). An empty list therefore
// means "nothing different next door", not missing data; land outside the
// state-forest BDL layer is never listed either.
export function neighborsSummary(neighbors: string[] | undefined): string | null {
  if (!neighbors) return "brak danych o sąsiedztwie";
  if (!neighbors.length)
    return "tylko podobne drzewostany (ten sam gatunek panujący, wiek ≥ 20 lat) lub teren spoza lasów państwowych";
  return null;
}
export function confidenceLabel(value?: string): string {
  return (
    (
      { NISKA: "Niska", SREDNIA: "Średnia", WYSOKA: "Wysoka" } as Record<
        string,
        string
      >
    )[value ?? ""] ?? "Brak danych"
  );
}
export function entranceLabel(value?: string): string {
  return (
    (
      {
        confirmed: "Wejście potwierdzone w danych",
        potential: "Wejście potencjalne",
        not_evaluated: "Wejście niesprawdzone",
      } as Record<string, string>
    )[value ?? ""] ?? "Brak danych o wejściu"
  );
}
export function distanceLabel(value?: number | null): string {
  if (!finite(value) || value < 0) return "Brak danych";
  return value < 1000
    ? `${Math.round(value)} m`
    : `${(value / 1000).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} km`;
}
export function distanceMethod(value?: string): string {
  return value === "network"
    ? "po sieci dróg, z odcinkami dojścia"
    : value === "euclidean"
      ? "oszacowanie: linia prosta × 1,3"
      : value === "access_points"
        ? "model punktów dostępu: parkingi, wjazdy, osiedla, drogi leśne"
        : "metoda nieznana";
}
// Plan wdrozenia 1.6: discrete "zakazow nie sprawdzono"/"zrodlo zawiodlo"
// notice, plus the as-of-preparation-date caveat -- shown only when it
// actually applies (checked-and-clear or a missing field say nothing extra),
// same optional/undefined-tolerant shape as the other score fields above.
export function zakazNote(value?: string): string {
  switch (value) {
    case "nie_sprawdzono":
      return "Zakazów wstępu do lasu nie sprawdzono dla tego wydzielenia.";
    case "blad":
      return "Sprawdzenie zakazu wstępu nie powiodło się (źródło niedostępne).";
    case "zakaz":
      return "Wykryto zakaz wstępu okresowy (stan na dzień przygotowania analizy).";
    default:
      return "";
  }
}
export function topExplanations(
  items: Explanation[],
  count = 2,
): Explanation[] {
  return [...items]
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, count);
}
export function navigationUrl([lon, lat]: [number, number]): string {
  if (!finite(lon) || !finite(lat) || Math.abs(lon) > 180 || Math.abs(lat) > 90)
    throw new Error("Niepoprawne współrzędne");
  return `https://www.google.com/maps?q=${lat},${lon}`;
}
export function vertices(feature: StandFeature): Position[] {
  return feature.geometry.type === "Polygon"
    ? feature.geometry.coordinates.flat()
    : feature.geometry.coordinates.flat(2);
}
// Polygon area-weighted centroid. This is an approximate geographic centroid,
// deliberately never described as an entrance or a car-accessible destination.
export function standCentroid(feature: StandFeature): [number, number] {
  const polygons =
    feature.geometry.type === "Polygon"
      ? [feature.geometry.coordinates]
      : feature.geometry.coordinates;
  let sumX = 0,
    sumY = 0,
    totalArea = 0;
  for (const polygon of polygons)
    for (const [ringIndex, ring] of polygon.entries()) {
      let crossSum = 0,
        x = 0,
        y = 0;
      for (let i = 0; i < ring.length - 1; i++) {
        const [ax, ay] = ring[i],
          [bx, by] = ring[i + 1];
        const cross = ax * by - bx * ay;
        crossSum += cross;
        x += (ax + bx) * cross;
        y += (ay + by) * cross;
      }
      if (Math.abs(crossSum) < 1e-14) continue;
      const weight = Math.abs(crossSum) * (ringIndex === 0 ? 1 : -1);
      sumX += (x / (3 * crossSum)) * weight;
      sumY += (y / (3 * crossSum)) * weight;
      totalArea += weight;
    }
  if (totalArea > 0) return [sumX / totalArea, sumY / totalArea];
  const points = vertices(feature);
  return [
    points.reduce((s, p) => s + p[0], 0) / points.length,
    points.reduce((s, p) => s + p[1], 0) / points.length,
  ];
}
export function joinData(scores: Score[], stands: Stands): StandView[] {
  const byGeometry = new Map(
    stands.features.map((f) => [f.properties.stand_id, f]),
  );
  const ids = new Set(scores.map((s) => s.stand_id));
  if (
    ids.size !== byGeometry.size ||
    [...ids].some((id) => !byGeometry.has(id))
  )
    throw new Error("Wyniki i geometrie dotyczą różnych zestawów wydzieleń.");
  return scores
    .filter((s) => s.mask && finite(s.R))
    .sort((a, b) => {
      // Plan 2.1 "Zmiana 4": R rounded to 2 decimal places is the primary
      // key (same precision pipeline.regions._summarize_cluster uses for
      // region member ordering, chosen against a real Będziemyśl export --
      // see that function's own docstring), tie_break the secondary key
      // among stands tied at that precision, stand_id the final
      // deterministic tiebreaker.
      const ra = Math.round(a.R! * 100);
      const rb = Math.round(b.R! * 100);
      if (rb !== ra) return rb - ra;
      const ta = a.tie_break ?? -1;
      const tb = b.tie_break ?? -1;
      if (tb !== ta) return tb - ta;
      return a.stand_id.localeCompare(b.stand_id);
    })
    .map((score) => {
      const feature = byGeometry.get(score.stand_id)!;
      return { score, feature, point: standCentroid(feature) };
    });
}

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
// Kolorowanie wydzielen wg rankingu R: 6 kolorow od jasnego zolto-zielonego do
// ciemnego granatu, przypietych do PERCENTYLI R w tej analizie (a nie do stalej
// skali 0-100, na ktorej prawie wszystkie wydzielenia wpadaly w ten sam zielony).
export const RANK_COLORS = [
  "#efe9b5",
  "#c5df8f",
  "#7fc47a",
  "#2f9a72",
  "#1c6a80",
  "#24356b",
];
export const RANK_QUANTILES = [0.02, 0.25, 0.5, 0.75, 0.9, 0.98];
export const RANK_ZERO_COLOR = "#d5d5b8"; // wydzielenia odrzucone przez maske (R = 0)
export function rankColorStops(values: (number | null | undefined)[]): [number, string][] {
  const sorted = values
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v) && v > 0)
    .sort((a, b) => a - b);
  const fallback = (): [number, string][] =>
    RANK_COLORS.map((c, i) => [(100 * i) / (RANK_COLORS.length - 1), c]);
  if (sorted.length < 2) return fallback();
  const at = (q: number) => {
    const pos = q * (sorted.length - 1);
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  };
  const stops: [number, string][] = [];
  RANK_QUANTILES.forEach((q, i) => {
    let v = at(q);
    // MapLibre wymaga scisle rosnacych progow
    if (stops.length && v <= stops[stops.length - 1][0]) v = stops[stops.length - 1][0] + 1e-6;
    stops.push([v, RANK_COLORS[i]]);
  });
  return stops.length === RANK_COLORS.length && sorted[sorted.length - 1] > sorted[0] ? stops : fallback();
}
export type AccessCard = {
  d_parking_m: number | null;
  d_entrance_m: number | null;
  d_hard_forest_road_m: number | null;
  top_point_id: string | null;
  top_point_type: string | null;
  top_point_source: string | null;
  top_point_name: string | null;
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
export const ACCESS_LAYERS: {
  id: AccessLayerId;
  label: string;
  defaultOn: boolean;
  needs: "points" | "roads" | "stands";
}[] = [
  { id: "parkings", label: "Parkingi", defaultOn: true, needs: "points" },
  { id: "entrances", label: "Wjazdy i szlabany", defaultOn: true, needs: "points" },
  { id: "roads", label: "Drogi leśne", defaultOn: true, needs: "roads" },
  { id: "fire", label: "Dojazdy pożarowe BDL", defaultOn: false, needs: "roads" },
  { id: "settlements", label: "Osiedla przy lesie", defaultOn: false, needs: "points" },
  { id: "pressure", label: "Presja P", defaultOn: false, needs: "stands" },
];
export const SURFACE_COLORS: Record<string, string> = {
  hard: "#2f4f6f",
  gravel: "#b8862f",
  compacted: "#8f7a4a",
  unknown: "#8b8b8b",
  dirt: "#7a5b3a",
};
export const SURFACE_LABELS: Record<string, string> = {
  hard: "twarda",
  gravel: "kruszywo",
  compacted: "ubita",
  unknown: "nieznana",
  dirt: "gruntowa",
};
export function surfaceLabel(value: unknown): string {
  return SURFACE_LABELS[String(value)] ?? "nieznana";
}
const POINT_TYPE_LABELS: Record<string, string> = {
  parking: "Parking",
  entrance: "Wjazd do lasu",
  gate: "Szlaban",
  road_fallback: "Droga asfaltowa przy lesie",
  settlement: "Osiedle przy lesie",
  forest_road: "Droga leśna",
};
export function pointTypeLabel(value: unknown): string {
  return POINT_TYPE_LABELS[String(value)] ?? "Punkt dostępu";
}
const SOURCE_LABELS: Record<string, string> = {
  bdl: "BDL",
  osm: "OpenStreetMap",
  gus: "GUS",
  bdl_ppoz: "BDL, dojazd pożarowy",
  wlasciciel: "korekta właściciela",
};
export function sourceLabel(value: unknown): string {
  return SOURCE_LABELS[String(value)] ?? String(value ?? "");
}
// Progi jak w pipeline.access_pressure.ATTRACTIVENESS_CLASS_EDGES.
export function attractivenessClass(value: unknown): string | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value < 0.1 ? "niska" : value < 0.3 ? "średnia" : "wysoka";
}
export function roadKindLabel(kind: unknown): string {
  return kind === "public"
    ? "droga publiczna"
    : kind === "fire"
      ? "dojazd pożarowy BDL"
      : "zamknięta droga leśna";
}
// Karta wydzielenia: "najbliższy parking X m, wjazd Y m, utwardzony dukt Z m".
export function accessCardSummary(card?: AccessCard | null): string {
  if (!card) return "";
  const m = (v: number | null) =>
    typeof v === "number" && Number.isFinite(v)
      ? `${Math.round(v / 10) * 10} m`
      : "brak w pobliżu";
  return `najbliższy parking ${m(card.d_parking_m)} · wjazd lub szlaban ${m(card.d_entrance_m)} · utwardzony dukt ${m(card.d_hard_forest_road_m)}`;
}
export function topPointSummary(card?: AccessCard | null): string {
  if (!card?.top_point_id) return "Żaden punkt dostępu nie sięga tego wydzielenia (P = 0).";
  const name = card.top_point_name ? ` „${card.top_point_name}”` : "";
  const source = card.top_point_source ? ` (${sourceLabel(card.top_point_source)})` : "";
  return `Największy wpływ na presję: ${pointTypeLabel(card.top_point_type).toLocaleLowerCase("pl")}${name}${source}.`;
}
// Zwraca kolekcje albo null, gdy plik jest nieobecny; zle uksztaltowany to blad.
export function parseAccessCollection(raw: unknown, file: string): AccessCollection | null {
  if (raw === undefined) return null;
  if (!object(raw) || raw.type !== "FeatureCollection" || !Array.isArray(raw.features))
    throw new Error(`Plik ${file} jest niepoprawny. Uruchom synchronizację danych.`);
  return raw as unknown as AccessCollection;
}
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
};

export type Region = {
  region_id: string;
  rank_score: number;
  stand_count: number;
  stand_ids: string[];
  day: string;
  centroid_lat: number;
  centroid_lon: number;
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
export function joinRegions(
  regions: Region[],
  entries: StandView[],
): RegionView[] {
  const byId = new Map(entries.map((e) => [e.score.stand_id, e]));
  const views: RegionView[] = [];
  for (const region of regions) {
    const members = region.stand_ids
      .map((id) => byId.get(id))
      .filter((e): e is StandView => e !== undefined);
    if (!members.length) continue;
    const top = members.reduce((best, e) =>
      (e.score.R ?? -Infinity) > (best.score.R ?? -Infinity) ? e : best,
    );
    views.push({ region, top, members });
  }
  return views.sort((a, b) => b.region.rank_score - a.region.rank_score);
}

const object = (x: unknown): x is Record<string, unknown> =>
  !!x && typeof x === "object" && !Array.isArray(x);
const strings = (x: unknown): x is string[] =>
  Array.isArray(x) && x.every((v) => typeof v === "string");
const numeric = (x: unknown) => x === null || finite(x);
const date = (x: unknown) =>
  typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x);
const nullableString = (x: unknown) => x === null || typeof x === "string";
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
): {
  entries: StandView[];
  scores: Score[];
  stands: Stands;
  regions: Region[];
  details: StandDetail[];
} {
  if (
    !Array.isArray(rawScores) ||
    !rawScores.every(
      (s) =>
        object(s) &&
        typeof s.stand_id === "string" &&
        date(s.day) &&
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
  let regions: Region[] = [];
  if (rawRegions !== undefined) {
    const knownStandIds = new Set(standIds);
    if (
      !Array.isArray(rawRegions) ||
      !rawRegions.every(
        (r) =>
          object(r) &&
          typeof r.region_id === "string" &&
          finite(r.rank_score) &&
          finite(r.stand_count) &&
          date(r.day) &&
          finite(r.centroid_lat) &&
          finite(r.centroid_lon) &&
          strings(r.stand_ids) &&
          r.stand_ids.length > 0,
      )
    )
      throw new Error("Niepoprawny plik rejonów.");
    regions = rawRegions as Region[];
    if (regions.some((r) => r.day !== scores[0]?.day))
      throw new Error(
        "Plik rejonów pochodzi z innej daty. Zsynchronizuj dane ponownie.",
      );
    if (regions.some((r) => r.stand_ids.some((id) => !knownStandIds.has(id))))
      throw new Error(
        "Rejon odwołuje się do wydzielenia spoza zsynchronizowanego zestawu.",
      );
  }
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
          date(d.day) &&
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
          (d.access === undefined || d.access === null || object(d.access)),
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

  return { entries: joinData(scores, stands), scores, stands, regions, details };
}

export type ConditionsDay = { date: string; F: number; level: 0 | 1 | 2 | 3; forecast: boolean };
export type ConditionsRain = { start: string; end: string; rain_mm: number; days_ago: number };
export type ConditionsTimeline = {
  day: string;
  generated_for: string;
  horizon_days: number;
  pulse_min_mm: number;
  rains: ConditionsRain[];
  summary: string;
  days: ConditionsDay[];
};

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

const WEEKDAYS = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];
export function dayLabel(dateIso: string, position: number): string {
  if (position === 0) return "dziś";
  return WEEKDAYS[new Date(`${dateIso}T12:00:00`).getDay()];
}
export async function loadData(basePath: string = "data/") {
  const [scoresRaw, standsRaw] = await Promise.all(
    ["scores.json", "stands.geojson"].map(async (file) => {
      const response = await fetch(`${import.meta.env.BASE_URL}${basePath}${file}`, {
        cache: "no-cache",
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok)
        throw new Error(
          `Nie udało się wczytać ${file}. Przygotuj i zsynchronizuj dane przed otwarciem mapy.`,
        );
      try {
        return await response.json();
      } catch {
        throw new Error(
          `Plik ${file} jest niedostępny lub niepoprawny. Uruchom synchronizację danych.`,
        );
      }
    }),
  );
  // regions.json is optional -- a missing file (404, or sync-data never
  // wrote one) just means no region view is offered, not a load failure.
  // A file that DOES exist but fails to fetch/parse is a real error,
  // though (same as scores/stands above) -- not silently treated as "no
  // regions" just because something went wrong reading it.
  //
  // `response.ok` alone is not enough: `npm run dev`'s dev server answers
  // a GET for a genuinely missing file with 200 text/html (its SPA
  // fallback to index.html), not 404 -- this is common (any saved trip or
  // run predating an optional file, e.g. this plan's own conditions.json).
  // Without the content-type check below, that 200 is trusted as "the
  // file exists", `.json()` throws on the HTML body, and an optional
  // file's ABSENCE turns into a fatal error for the whole map.
  const isJsonResponse = (response: Response) =>
    response.headers.get("content-type")?.includes("json") ?? false;
  let regionsRaw: unknown = undefined;
  const regionsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}regions.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (regionsResponse?.ok && isJsonResponse(regionsResponse)) {
    try {
      regionsRaw = await regionsResponse.json();
    } catch {
      throw new Error(
        "Plik regions.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.",
      );
    }
  }
  // details.json is optional too, same reasoning as regions.json above --
  // plan 2.1 step B3.
  let detailsRaw: unknown = undefined;
  const detailsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}details.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (detailsResponse?.ok && isJsonResponse(detailsResponse)) {
    try {
      detailsRaw = await detailsResponse.json();
    } catch {
      throw new Error(
        "Plik details.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.",
      );
    }
  }
  // conditions.json is optional too, same reasoning as regions/details
  // above -- plan A2 Plan-B.
  let conditionsRaw: unknown = undefined;
  const conditionsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}conditions.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (conditionsResponse?.ok && isJsonResponse(conditionsResponse)) {
    try {
      conditionsRaw = await conditionsResponse.json();
    } catch {
      throw new Error(
        "Plik conditions.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.",
      );
    }
  }
  // access_points.json / forest_roads.json: optional layers (Faza 3.5), same
  // tolerance for a missing file as the optional files above.
  const optionalJson = async (file: string): Promise<unknown> => {
    const response = await fetch(
      `${import.meta.env.BASE_URL}${basePath}${file}`,
      { cache: "no-cache", signal: AbortSignal.timeout(20000) },
    ).catch(() => undefined);
    if (!response?.ok || !isJsonResponse(response)) return undefined;
    try {
      return await response.json();
    } catch {
      throw new Error(`Plik ${file} jest niedostępny lub niepoprawny. Uruchom synchronizację danych.`);
    }
  };
  const accessPoints = parseAccessCollection(await optionalJson("access_points.json"), "access_points.json");
  const forestRoads = parseAccessCollection(await optionalJson("forest_roads.json"), "forest_roads.json");
  const parsed = parseData(scoresRaw, standsRaw, regionsRaw, detailsRaw);
  return {
    ...parsed,
    conditions: parseConditions(conditionsRaw, parsed.scores[0]?.day),
    accessPoints,
    forestRoads,
  };
}
export type TripMeta = {
  id: string;
  name: string;
  radius_km: number;
  day: string;
  lat: number;
  lon: number;
  saved_at: string;
};
export function formatTripLabel(trip: TripMeta): string {
  const [, month, day] = trip.day.split("-");
  return `${trip.name} - ${trip.radius_km}km - ${day}.${month}`;
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
      date(t.day) &&
      finite(t.lat) &&
      finite(t.lon) &&
      typeof t.saved_at === "string",
  );
}
// index.json is optional and, unlike scores/stands/regions/details, is
// appended to incrementally by the launcher over time -- a single bad
// entry (or a missing/corrupted file) means "fewer saved trips to show",
// never a load failure for the live analysis. Same tolerant pattern as
// storage.ts's readSaved, not parseData's throw-on-invalid pattern.
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
