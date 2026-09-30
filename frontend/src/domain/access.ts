import type { AccessCard, AccessLayerId } from "../data/types";
import { areaLabel, finite, roundedDistance } from "./format";

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

export type ComponentRow = { label: string; value: string; note?: string };

const PRESSURE_TYPE_LABELS: Record<string, string> = {
  parking: "parking",
  entrance: "wjazd lub szlaban",
  gate: "wjazd lub szlaban",
  road_fallback: "dojście od drogi",
  settlement: "osiedle",
  forest_road: "droga leśna",
};

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
