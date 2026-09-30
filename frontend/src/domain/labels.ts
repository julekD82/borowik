import type { Region, SpeciesShare, StandDetail, TripMeta } from "../data/types";
import { finite, joinMeta, pl } from "./format";
import { CLASS_LABELS, type ScoreClass } from "./ranking";

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

export function formatTripLabel(trip: TripMeta): string {
  const [, month, day] = trip.day.split("-");
  return `${trip.name} - ${trip.radius_km}km - ${day}.${month}`;
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

const MASK_REASON_TEXT: Record<string, string> = {
  not_dstan: "to nie drzewostan (np. zrąb, łąka, droga)",
  no_age: "brak wieku drzewostanu w danych",
  too_young: "za młody drzewostan (młodnik)",
  excluded_species: "gatunek wykluczający (np. olsza, jesion) stanowi co najmniej 80%",
  gdos: "rezerwat przyrody lub park narodowy (GDOŚ)",
  zakaz: "okresowy zakaz wstępu do lasu",
};

export function maskReasonTexts(reasons?: string[]): string[] {
  if (!reasons || !reasons.length) return ["powód nieznany w tej analizie"];
  return reasons.map((r) => MASK_REASON_TEXT[r] ?? r);
}

export function yearsLabel(n: number): string {
  const k = Math.round(n);
  if (k === 1) return "1 rok";
  const last = k % 10;
  const lastTwo = k % 100;
  const few = last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14);
  return `${k} ${few ? "lata" : "lat"}`;
}

/** "sosna 70%, świerk 30%": sumuje powtorzone gatunki, pomija udzialy sladowe ("poniżej 5 %"). */
export function speciesShort(species: SpeciesShare[], max = 3): string | null {
  const totals = new Map<string, { name: string; share: number }>();
  for (const s of species) {
    const match = /udział\s+(\d+)\s*%/.exec(s.share);
    if (!match) continue;
    const previous = totals.get(s.species_cd);
    totals.set(s.species_cd, { name: s.name.split(" ")[0], share: (previous?.share ?? 0) + Number(match[1]) });
  }
  const list = [...totals.values()].sort((a, b) => b.share - a.share).slice(0, max);
  return list.length ? list.map((x) => `${x.name} ${x.share}%`).join(", ") : null;
}

export function formatDateLong(day?: string | null): string {
  if (!day || !/^\d{4}-\d{2}-\d{2}$/.test(day)) return "—";
  return new Date(`${day}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
}

export function analysisLabel(o: { tripName: string | null; radiusKm: number | null; day: string | null }): string {
  return joinMeta([o.tripName ?? "Aktualna analiza", o.radiusKm !== null ? `${pl(o.radiusKm)} km` : null, o.day ? formatDateLong(o.day) : null]);
}

export function tooltipText(name: string, r: number | null, cls: ScoreClass | 0): string {
  if (cls === 0) return `${name} · poza filtrami modelu`;
  if (r === null) return `${name} · brak wyniku`;
  return `${name} · wynik ${Math.round(r)} · ${CLASS_LABELS[cls]}`;
}
