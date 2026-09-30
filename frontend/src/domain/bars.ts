import { finite } from "./format";
import { fruitingClass } from "./labels";

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
