import type { Score, StandDetail, StandView } from "../data/types";
import { pressureTop } from "./access";
import { finite, formatValue, pl } from "./format";
import { dominantSpeciesShort, fruitingClass, speciesShort, yearsLabel } from "./labels";

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

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Paski rejonu: mediana 5 najlepszych wydzielen (ta sama podstawa co rank_score rejonu). */
export function regionBars(members: StandView[], pressure: boolean): Bar[] {
  const top = [...members].sort((a, b) => b.r - a.r).slice(0, 5);
  const pick = (value: (s: Score) => number | null) => median(top.map((m) => value(m.score)).filter(finite));
  return scoreBars({ H: pick((s) => s.H), F_loc: pick((s) => s.F_loc), P: pick((s) => s.P) }, pressure);
}

export type BarNotes = Partial<Record<BarKey, string>>;

/** Krotkie opisy pod paskami karty wydzielenia (tylko to, co jest w eksporcie). */
export function barNotes(score: Score, detail: StandDetail | null | undefined, pressure: boolean): BarNotes {
  const notes: BarNotes = {};
  const age = detail?.age_years;
  const habitat = [
    speciesShort(detail?.drzew_species ?? []) ?? dominantSpeciesShort(detail?.dominant_species),
    detail?.site_type?.label ?? null,
    finite(age) ? yearsLabel(age) : null,
  ].filter((x): x is string => !!x);
  if (habitat.length) notes.habitat = habitat.join(" · ");
  const p26 = detail?.weather?.p26_mm;
  const t20 = detail?.weather?.tmean20_c;
  const moisture = score.M;
  const weather = [
    finite(p26) ? `opad ${pl(p26)} mm / 26 dni` : null,
    finite(moisture) ? `wilgotność ${formatValue(moisture)}` : null,
    finite(t20) ? `${pl(t20, 1)} °C średnio 20 dni` : null,
  ].filter((x): x is string => !!x);
  if (weather.length) notes.weather = weather.join(" · ");
  if (pressure) {
    const top = pressureTop(detail?.access, 1)[0];
    if (top) notes.calm = `najwięcej presji: ${top.label}${top.value ? ` (${top.value})` : ""}`;
  }
  return notes;
}
