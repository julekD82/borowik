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
  // Faza UI.1: wynik bez presji grzybiarzy, 100 * H * F_loc (alpha = 0) -- brak w
  // eksportach sprzed tej zmiany (przelacznik presji jest wtedy nieaktywny).
  R_bez_presji?: number | null;
  // Tryb mapy "Wilgotnosc": skladowa M (0-1) i percentyl bilansu wodnego z 26 dni, dla
  // wszystkich wydzielen (rowniez poza maska); brak w migawkach sprzed tej zmiany.
  M?: number | null;
  pct_CWB26?: number | null;
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
// Wynik rankingowy wydzielenia w wybranym trybie presji (Faza UI.1).
export function effectiveR(score: Score, pressure: boolean): number | null {
  const value = pressure ? score.R : score.R_bez_presji;
  return finite(value) ? value : null;
}
// Plan 2.1 "Zmiana 4": R rounded to 2 decimal places is the primary key (same
// precision pipeline.regions._summarize_cluster uses for region member
// ordering, chosen against a real Będziemyśl export -- see that function's own
// docstring), tie_break the secondary key among stands tied at that
// precision, stand_id the final deterministic tiebreaker.
function compareViews(a: StandView, b: StandView): number {
  const ra = Math.round(a.r * 100);
  const rb = Math.round(b.r * 100);
  if (rb !== ra) return rb - ra;
  const ta = a.score.tie_break ?? -1;
  const tb = b.score.tie_break ?? -1;
  if (tb !== ta) return tb - ta;
  return a.score.stand_id.localeCompare(b.score.stand_id);
}
// Ponowne uszeregowanie wydzielen wg wybranego trybu presji; przy `pressure = true`
// wynik jest identyczny z joinData (test). Geometria i punkt sa wspoldzielone.
export function rankEntries(entries: StandView[], pressure: boolean): StandView[] {
  const ranked: StandView[] = [];
  for (const e of entries) {
    const r = effectiveR(e.score, pressure);
    if (e.score.mask && r !== null) ranked.push({ ...e, r });
  }
  return ranked.sort(compareViews);
}
export function joinData(scores: Score[], stands: Stands, pressure = true): StandView[] {
  const byGeometry = new Map(
    stands.features.map((f) => [f.properties.stand_id, f]),
  );
  const ids = new Set(scores.map((s) => s.stand_id));
  if (
    ids.size !== byGeometry.size ||
    [...ids].some((id) => !byGeometry.has(id))
  )
    throw new Error("Wyniki i geometrie dotyczą różnych zestawów wydzieleń.");
  const views: StandView[] = [];
  for (const score of scores) {
    const r = effectiveR(score, pressure);
    if (!score.mask || r === null) continue;
    const feature = byGeometry.get(score.stand_id)!;
    views.push({ score, feature, point: standCentroid(feature), r });
  }
  return views.sort(compareViews);
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
// Karta REJONU: zamiast odleglosci jednego (najlepszego) wydzielenia -- zakres po
// wszystkich wydzieleniach rejonu: od najblizszego do najdalszego i mediana.
function distanceRange(values: (number | null | undefined)[]): string {
  const nums = values
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v))
    .sort((a, b) => a - b);
  if (!nums.length) return "brak w pobliżu";
  const round = (v: number) => `${Math.round(v / 10) * 10} m`;
  const median =
    nums.length % 2 ? nums[(nums.length - 1) / 2] : (nums[nums.length / 2 - 1] + nums[nums.length / 2]) / 2;
  return nums[0] === nums[nums.length - 1]
    ? round(nums[0])
    : `od ${round(nums[0])} do ${round(nums[nums.length - 1])} (mediana ${round(median)})`;
}
export function regionAccessSummary(
  cards: AccessCard[],
): { distances: string; top: string } | null {
  if (!cards.length) return null;
  const distances = `najbliższy parking ${distanceRange(cards.map((c) => c.d_parking_m))} · wjazd lub szlaban ${distanceRange(cards.map((c) => c.d_entrance_m))} · utwardzony dukt ${distanceRange(cards.map((c) => c.d_hard_forest_road_m))}`;
  const counts = new Map<string, { n: number; card: AccessCard }>();
  for (const c of cards)
    if (c.top_point_id) {
      const e = counts.get(c.top_point_id);
      if (e) e.n += 1;
      else counts.set(c.top_point_id, { n: 1, card: c });
    }
  if (!counts.size) return { distances, top: "Żaden punkt dostępu nie sięga wydzieleń tego rejonu (P = 0)." };
  const best = [...counts.values()].sort((a, b) => b.n - a.n)[0];
  const name = best.card.top_point_name ? ` „${best.card.top_point_name}”` : "";
  const source = best.card.top_point_source ? ` (${sourceLabel(best.card.top_point_source)})` : "";
  return {
    distances,
    top: `Najczęściej największy wpływ na presję: ${pointTypeLabel(best.card.top_point_type).toLocaleLowerCase("pl")}${name}${source} — w ${best.n} z ${cards.length} wydzieleń rejonu.`,
  };
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
  // Faza 4.3/4.5: skladniki pogody tego wydzielenia (tylko prezentacja, nie wplywaja na F/R);
  // brak/null w plikach sprzed Fazy 4.
  weather?: WeatherCard | null;
  // Faza UI.2/UI.3: skladniki siedliska i nazwa nadlesnictwa (brak w plikach sprzed UI).
  habitat?: HabitatCard | null;
  forest_district?: string | null;
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
    const top = members.reduce((best, e) => (e.r > best.r ? e : best));
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
          date(r.day) &&
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
  const regionsNoPressureRaw = await optionalJson("regions_bez_presji.json");
  const manifest = (await optionalJson("manifest.json")) as
    | { wfs_only_share_of_masked?: unknown; lat?: unknown; lon?: unknown; pressure_alpha?: unknown }
    | undefined;
  const parsed = parseData(scoresRaw, standsRaw, regionsRaw, detailsRaw, regionsNoPressureRaw);
  return {
    ...parsed,
    wfsOnlyShare: finiteNumber(manifest?.wfs_only_share_of_masked) ? manifest.wfs_only_share_of_masked : null,
    // Faza UI.3: punkt startu analizy (odleglosc na liscie) i waga presji (Szczegoly).
    start:
      finiteNumber(manifest?.lat) && finiteNumber(manifest?.lon)
        ? ([manifest.lon, manifest.lat] as [number, number])
        : null,
    pressureAlpha: finiteNumber(manifest?.pressure_alpha) ? manifest.pressure_alpha : null,
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

// ---- Faza 4.3-4.5: skladniki pogody, niepewnosc prognozy (czyste funkcje, testowane) ----

export const WEATHER_DISCLAIMER =
  "Ocena pogody nie została potwierdzona na danych o znaleziskach; traktuj ją jako orientację, nie prognozę wysypu.";

const pl = (value: number, digits = 0) =>
  value.toLocaleString("pl-PL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** Oznaczenie dnia prognozy: "prognoza niepewna" (od progu 1) i "orientacyjnie" (od progu 2). */
export function uncertaintyLabel(level: ForecastUncertainty | undefined): string | null {
  if (level === "uncertain") return "prognoza niepewna";
  if (level === "indicative") return "orientacyjnie";
  return null;
}

export function uncertaintyNote(level: ForecastUncertainty | undefined): string | null {
  if (level === "uncertain")
    return "Prognoza pogody na kilka dni naprzód bywa niedokładna; ocena tego dnia może się zmienić.";
  if (level === "indicative")
    return "Prognoza odległa o tydzień lub więcej — wartość tylko orientacyjna.";
  return null;
}

const finiteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Linie skladnikow pogody dla panelu (mediana obszaru) lub karty wydzielenia. */
export function weatherComponentLines(c: {
  cwb26_mm: number | null;
  cwb26_typical_mm: number | null;
  pct_cwb26: number | null;
  tmean20_c: number | null;
  temp_optimum_c: number | null;
}): string[] {
  const lines: string[] = [];
  if (finiteNumber(c.cwb26_mm) && finiteNumber(c.cwb26_typical_mm) && finiteNumber(c.pct_cwb26))
    lines.push(
      `Bilans wodny z 26 dni (opad minus parowanie): ${pl(c.cwb26_mm)} mm, typowo o tej porze ${pl(c.cwb26_typical_mm)} mm (percentyl ${pl(Math.round(c.pct_cwb26 * 100))})`,
    );
  if (finiteNumber(c.tmean20_c))
    lines.push(
      `Średnia temperatura 20 dni: ${pl(c.tmean20_c, 1)} °C${finiteNumber(c.temp_optimum_c) ? ` (optimum ok. ${pl(c.temp_optimum_c)} °C)` : ""}`,
    );
  return lines;
}

const dayMonth = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
};

/** Pelne linie karty wydzielenia: skladniki, przymrozek (tak/nie, kiedy), F jako liczba, udzial prognozy. */
export function weatherCardLines(w: WeatherCard): string[] {
  const daysAhead = finiteNumber(w.forecast_days) ? w.forecast_days - 1 : null;
  const lines = weatherComponentLines(w);
  if (w.p26_mm !== null && finiteNumber(w.p26_mm)) lines.unshift(`Opad z ostatnich 26 dni: ${pl(w.p26_mm)} mm`);
  if (w.frost === "brak") lines.push("Przymrozek w ostatnich 3 dobach: nie");
  else if (w.frost === "slaby" || w.frost === "silny")
    lines.push(
      `Przymrozek w ostatnich 3 dobach: tak (${w.frost === "silny" ? "silny" : "słaby"}, min ${finiteNumber(w.tmin3_c) ? pl(w.tmin3_c, 1) : "?"} °C${w.frost_date ? `, ${dayMonth(w.frost_date)}` : ""})`,
    );
  if (finiteNumber(w.F)) lines.push(`Ocena pogody F: ${pl(w.F, 2)}`);
  if (daysAhead !== null && daysAhead >= 4 && finiteNumber(w.forecast_window_share))
    lines.push(
      `Wyjazd za ${daysAhead} dni: ok. ${pl(Math.round(w.forecast_window_share * 100))}% oceny opadu pochodzi z prognozy, nie z obserwacji`,
    );
  return lines;
}

/** Udzial powierzchni z przymrozkiem / silnym opadem w panelu (tylko gdy niezerowy). */
export function localPhenomenaNote(d: ConditionsDay): string | null {
  const parts: string[] = [];
  if (finiteNumber(d.frost_area_share) && d.frost_area_share > 0)
    parts.push(`przymrozek na ${pl(Math.round(d.frost_area_share * 100))}% lasu`);
  if (finiteNumber(d.heavy_rain_area_share) && d.heavy_rain_area_share > 0)
    parts.push(`silny opad na ${pl(Math.round(d.heavy_rain_area_share * 100))}% lasu`);
  return parts.length ? parts.join(", ") : null;
}

/** Plan 1.3: ostrzezenie, gdy > 20% wydzielen w masce ma sklad tylko z WFS (brak paczki BDL). */
export const WFS_ONLY_BANNER_THRESHOLD = 0.2;
export function wfsOnlyBanner(share: number | null | undefined): string | null {
  if (!finiteNumber(share) || share <= WFS_ONLY_BANNER_THRESHOLD) return null;
  return `Skład drzewostanu tylko z opisu WFS (bez paczki BDL) dla ${pl(Math.round(share * 100))}% wydzieleń w masce — ocena siedliska H jest tu mniej dokładna.`;
}

// ---- Faza UI: przelacznik presji, paski wyniku, nazwy, fakty karty (czyste funkcje, testowane) ----

/** Przelacznik presji dziala tylko, gdy migawka ma R_bez_presji i drugi zestaw rejonow. */
export function pressureSwitchAvailable(
  scores: Score[],
  regionsNoPressure: Region[] | null,
): boolean {
  return (
    regionsNoPressure !== null &&
    scores.some((s) => s.mask && finite(s.R_bez_presji))
  );
}

export type BarKey = "habitat" | "weather" | "calm";
export type Bar = {
  key: BarKey;
  label: string;
  // Wartosc modelu 0-1 w konwencji "wiecej = lepiej" (Siedlisko = H, Pogoda = F_loc, Spokoj = 1 - P).
  value: number | null;
  // Ocena slowna przy pasku; przy wylaczonej presji Spokoj ma opis "nie uwzgledniony".
  word: string;
  muted: boolean;
};
const threeWords = (
  value: number | null | undefined,
  low: number,
  high: number,
  words: [string, string, string],
) =>
  !finite(value) ? "brak danych" : value < low ? words[0] : value < high ? words[1] : words[2];
/** Trzy paski: Siedlisko (H), Pogoda (F_loc), Spokoj (1 - P). Tylko wartosci z eksportu. */
export function scoreBars(
  v: { H: number | null; F_loc: number | null; P: number | null },
  pressure: boolean,
): Bar[] {
  const calm = finite(v.P) ? 1 - v.P : null;
  return [
    {
      key: "habitat",
      label: "Siedlisko",
      value: finite(v.H) ? v.H : null,
      word: threeWords(v.H, 0.4, 0.7, ["niskie", "średnie", "wysokie"]),
      muted: false,
    },
    {
      key: "weather",
      label: "Pogoda",
      value: finite(v.F_loc) ? v.F_loc : null,
      word: fruitingClass(v.F_loc).toLocaleLowerCase("pl"),
      muted: false,
    },
    {
      key: "calm",
      label: "Spokój",
      value: calm,
      word: pressure ? threeWords(calm, 0.4, 0.7, ["niski", "średni", "wysoki"]) : "nie uwzględniony",
      muted: !pressure,
    },
  ];
}

const pln = (value: number, digits = 2) =>
  value.toLocaleString("pl-PL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const formatValue = (value: number | null | undefined, digits = 2) =>
  finite(value) ? pln(value, digits) : "—";

export type ComponentRow = { label: string; value: string; note?: string };
/** Skladniki paska Siedlisko: sklad drzewostanu, typ siedliska, wiek (S_age). */
export function habitatComponents(h: HabitatCard | null | undefined): ComponentRow[] {
  if (!h) return [];
  const neutral = h.age_mode === "neutral";
  return [
    { label: "Skład drzewostanu", value: formatValue(h.S_host) },
    { label: "Typ siedliska", value: formatValue(h.S_site) },
    neutral
      ? { label: "Wiek drzewostanu", value: "—", note: "nie wpływa na wynik" }
      : { label: "Wiek drzewostanu", value: formatValue(h.S_age) },
  ];
}
/** Skladniki paska Pogoda: wilgotnosc (M), temperatura (T), przymrozek (K_frost). */
export function weatherComponents(w: WeatherCard | null | undefined): ComponentRow[] {
  if (!w) return [];
  const rows: ComponentRow[] = [];
  if (w.M !== undefined) rows.push({ label: "Wilgotność", value: formatValue(w.M) });
  if (w.T !== undefined) rows.push({ label: "Temperatura", value: formatValue(w.T) });
  if (w.K_frost !== undefined)
    rows.push({
      label: "Przymrozek",
      value: formatValue(w.K_frost),
      note: w.frost === "brak" ? "brak przymrozku" : w.frost ? "był przymrozek" : undefined,
    });
  return rows;
}

const PRESSURE_TYPE_LABELS: Record<string, string> = {
  parking: "parking",
  entrance: "wjazd lub szlaban",
  gate: "wjazd lub szlaban",
  road_fallback: "dojście od drogi",
  settlement: "osiedle",
  forest_road: "droga leśna",
};
const roundedDistance = (v: number | null | undefined) =>
  finite(v) ? (v < 1000 ? `${Math.round(v / 10) * 10} m` : `${pln(v / 1000, 1)} km`) : null;
/**
 * Skladniki paska Spokoj: do `count` punktow o najwiekszym wkladzie w presje (parking,
 * wjazd/szlaban, osiedle, droga lesna...), z najblizsza odlegloscia tam, gdzie eksport ja ma.
 * Wklad = udzial typu w surowej presji z modelu punktow dostepu (bez nowych wzorow).
 */
export function pressureTop(card: AccessCard | null | undefined, count = 3): ComponentRow[] {
  const contrib = card?.pressure_contrib;
  if (!card || !contrib) return [];
  const merged = new Map<string, number>();
  for (const [type, value] of Object.entries(contrib)) {
    if (!finite(value) || value <= 0) continue;
    const key = PRESSURE_TYPE_LABELS[type] ?? type;
    merged.set(key, (merged.get(key) ?? 0) + value);
  }
  const total = [...merged.values()].reduce((a, b) => a + b, 0);
  if (total <= 0) return [];
  const distanceFor: Record<string, number | null> = {
    parking: card.d_parking_m,
    "wjazd lub szlaban": card.d_entrance_m,
    "droga leśna": card.d_hard_forest_road_m,
  };
  return [...merged.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, count)
    .map(([label, value]) => {
      const named =
        card.top_point_name &&
        card.top_point_type &&
        (PRESSURE_TYPE_LABELS[card.top_point_type] ?? card.top_point_type) === label
          ? ` ${card.top_point_name}`
          : "";
      return {
        label: `${label}${named}`,
        value: roundedDistance(distanceFor[label]) ?? "",
        note: `${Math.round((100 * value) / total)}% presji`,
      };
    });
}

// Kody nadlesnictw RDLP Katowice (paczki BDL dostepne lokalnie) z polskimi znakami; dla innych
// nadlesnictw nazwa idzie z eksportu (forest_district, bez polskich znakow) albo kod.
export const FOREST_DISTRICTS: Record<string, string> = {
  "02-03": "Brynek",
  "02-09": "Katowice",
  "02-10": "Kędzierzyn",
  "02-14": "Zawadzkie",
  "02-16": "Koszęcin",
  "02-19": "Lubliniec",
  "02-21": "Oleśno",
  "02-25": "Rudziniec",
  "02-29": "Strzelce Opolskie",
};
export type ParsedStandId = {
  district: string;
  forestry: string;
  section: string;
  subsection: string;
};
/** "02-14-3-11-96 -a -00@2026" -> nadlesnictwo 02-14, lesnictwo 3, oddzial 96, pododdzial a. */
export function parseStandId(standId: string): ParsedStandId | null {
  const address = standId.split("@")[0];
  const parts = address.split("-").map((p) => p.trim());
  if (parts.length < 6 || parts.slice(0, 5).some((p) => !p)) return null;
  return {
    district: `${parts[0]}-${parts[1]}`,
    forestry: parts[2],
    section: parts[4],
    subsection: parts[5],
  };
}
/** "Oddz. 96a · Nadl. Zawadzkie"; pelny identyfikator zostaje w Szczegolach. */
export function standName(standId: string, detail?: StandDetail | null): string {
  const parsed = parseStandId(standId);
  if (!parsed) return `Wydzielenie ${standId}`;
  const district = FOREST_DISTRICTS[parsed.district] ?? detail?.forest_district;
  return `Oddz. ${parsed.section}${parsed.subsection} · ${district ? `Nadl. ${district}` : `nadl. ${parsed.district}`}`;
}
/** "Rejon 1 · Łaziska" (najblizsza miejscowosc OSM; bez odmiany), inaczej "Rejon 1". */
export function regionName(region: Region, position: number): string {
  const place = region.near_place?.name;
  return place ? `Rejon ${position} · ${place}` : `Rejon ${position}`;
}

/** Odleglosc w linii prostej (km) miedzy punktami [lon, lat]. */
export function haversineKm(a: [number, number], b: [number, number]): number {
  const rad = (x: number) => (x * Math.PI) / 180;
  const dLat = rad(b[1] - a[1]);
  const dLon = rad(b[0] - a[0]);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}
export function startDistanceLabel(
  start: [number, number] | null | undefined,
  point: [number, number],
): string | null {
  if (!start) return null;
  return `${pln(haversineKm(start, point), 1)} km od startu`;
}
export function areaLabel(areaHa: number | null | undefined): string | null {
  return finite(areaHa) ? `${pln(areaHa, areaHa < 10 ? 1 : 0)} ha` : null;
}

/** Do 4 krotkich faktow karty: parking, wjazd, utwardzony dukt, powierzchnia. */
export function keyFacts(
  card: AccessCard | null | undefined,
  areaHa: number | null | undefined,
  fallbackDistanceM?: number | null,
): string[] {
  const facts: string[] = [];
  const parking = roundedDistance(card?.d_parking_m);
  const entrance = roundedDistance(card?.d_entrance_m);
  const road = roundedDistance(card?.d_hard_forest_road_m);
  if (card) {
    if (parking) facts.push(`parking ${parking}`);
    if (entrance) facts.push(`wjazd ${entrance}`);
    if (road) facts.push(`utwardzony dukt ${road}`);
  } else {
    const walk = roundedDistance(fallbackDistanceM);
    if (walk) facts.push(`dojście ok. ${walk}`);
  }
  const area = areaLabel(areaHa);
  if (area) facts.push(area);
  return facts.slice(0, 4);
}

export type ConditionBar = {
  label: string;
  value: number;
  level: number;
  uncertainty: ForecastUncertainty;
  title: string;
};
/** 7 dni panelu jako male slupki F (wysokosc = F), z oznaczeniem niepewnosci z 4.5. */
export function conditionBars(
  days: ConditionsDay[],
  formatDate: (iso: string) => string,
): ConditionBar[] {
  return days.map((d, i) => {
    const uncertain = uncertaintyLabel(d.uncertainty);
    const local = localPhenomenaNote(d);
    return {
      label: dayLabel(d.date, i),
      value: Math.max(0, Math.min(1, d.F)),
      level: d.level,
      uncertainty: d.uncertainty ?? "ok",
      title: `${formatDate(d.date)}: ${Math.round(d.F * 100)}/100${uncertain ? ` · ${uncertain}` : ""}${local ? ` · ${local}` : ""}`,
    };
  });
}

// ---- Tryby kolorowania mapy: Wynik / Wynik bez presji / Wilgotnosc (czyste funkcje, testowane) ----

export type MapColorMode = "score" | "score_no_pressure" | "moisture";
export type MapControls = { pressure: boolean; colorMode: MapColorMode };
export const MAP_COLOR_KEY = "borowik.map-color.v1";

/** Tryb Wilgotnosc wymaga M w scores.json (starsze migawki go nie maja). */
export function moistureAvailable(scores: Score[]): boolean {
  return scores.some((s) => finite(s.M));
}
export const colorModeForPressure = (pressure: boolean): MapColorMode =>
  pressure ? "score" : "score_no_pressure";

/**
 * Wybor jednego z trzech przyciskow mapy. "Wynik" i "Wynik bez presji" ustawiaja tez przelacznik
 * presji (jedna prawda, bez sprzecznych kontrolek); "Wilgotnosc" zmienia tylko kolory mapy --
 * lista i rejony zostaja w ostatnim trybie wynik/wynik bez presji. Zwraca null, gdy wybor jest
 * niedostepny (brak R_bez_presji albo M w migawce).
 */
export function chooseColorMode(
  state: MapControls,
  mode: MapColorMode,
  available: { pressure: boolean; moisture: boolean },
): MapControls | null {
  if (mode === "moisture") return available.moisture ? { pressure: state.pressure, colorMode: mode } : null;
  if (mode === "score_no_pressure" && !available.pressure) return null;
  return { pressure: mode === "score", colorMode: mode };
}
/** Przelacznik presji zawsze wraca mapie kolor zgodny z rankingiem (wynik / wynik bez presji). */
export function togglePressureControls(
  on: boolean,
  available: { pressure: boolean },
): MapControls {
  const pressure = on || !available.pressure;
  return { pressure, colorMode: colorModeForPressure(pressure) };
}
/** Stan poczatkowy: presja z przelacznika, a zapamietany tryb Wilgotnosc tylko gdy dostepny. */
export function resolveColorMode(
  stored: string | null,
  pressure: boolean,
  isMoistureAvailable: boolean,
): MapColorMode {
  return stored === "moisture" && isMoistureAvailable ? "moisture" : colorModeForPressure(pressure);
}

// Skala BEZWZGLEDNA 0-1 (nie percentyle w obrebie mapy): ta sama wilgotnosc ma ten sam kolor
// w kazdej analizie. Od piaskowego (sucho) przez jasnozielony do niebieskozielonego (wilgotno).
export const MOISTURE_STOPS: [number, string][] = [
  [0, "#e8d5a0"],
  [0.25, "#c8dd92"],
  [0.5, "#7cc8a0"],
  [0.75, "#2fa6a6"],
  [1, "#1f7fa6"],
];
export const MOISTURE_NO_DATA_COLOR = "#cfd2c6";
export const MOISTURE_NOTE =
  "Bilans opad − parowanie z 26 dni względem typowego dla tej pory roku. To nie pomiar wilgotności gleby.";
const hexToRgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
];
/** Kolor skali bezwzglednej dla M (interpolacja liniowa; spoza 0-1 przycinane, brak = szary). */
export function moistureColor(value: number | null | undefined): string {
  if (!finite(value)) return MOISTURE_NO_DATA_COLOR;
  const v = Math.max(0, Math.min(1, value));
  for (let i = 1; i < MOISTURE_STOPS.length; i++) {
    const [hi, hiColor] = MOISTURE_STOPS[i];
    const [lo, loColor] = MOISTURE_STOPS[i - 1];
    if (v <= hi) {
      const t = (v - lo) / (hi - lo);
      const a = hexToRgb(loColor);
      const b = hexToRgb(hiColor);
      const c = a.map((x, k) => Math.round(x + (b[k] - x) * t));
      return `#${c.map((x) => x.toString(16).padStart(2, "0")).join("")}`;
    }
  }
  return MOISTURE_STOPS[MOISTURE_STOPS.length - 1][1];
}
export const MOISTURE_LEGEND_TICKS = [0, 0.25, 0.5, 0.75, 1];
/** Etykiety progow legendy (0,0 · 0,25 …). */
export const moistureTickLabel = (v: number) => v.toLocaleString("pl-PL", { minimumFractionDigits: v === 0 || v === 1 ? 0 : 2 });
