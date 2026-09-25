import type {
  Feature,
  FeatureCollection,
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
      : "metoda nieznana";
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
  // fields above.
  veg_cover: string | null;
  standdensity_index: number | null;
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
          nullableString(d.veg_cover) &&
          (d.standdensity_index === null || finite(d.standdensity_index)),
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
export async function loadData() {
  const [scoresRaw, standsRaw] = await Promise.all(
    ["scores.json", "stands.geojson"].map(async (file) => {
      const response = await fetch(`${import.meta.env.BASE_URL}data/${file}`, {
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
  let regionsRaw: unknown = undefined;
  const regionsResponse = await fetch(
    `${import.meta.env.BASE_URL}data/regions.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (regionsResponse?.ok) {
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
    `${import.meta.env.BASE_URL}data/details.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (detailsResponse?.ok) {
    try {
      detailsRaw = await detailsResponse.json();
    } catch {
      throw new Error(
        "Plik details.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.",
      );
    }
  }
  return parseData(scoresRaw, standsRaw, regionsRaw, detailsRaw);
}
