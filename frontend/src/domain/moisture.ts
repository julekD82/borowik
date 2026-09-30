import type { Score } from "../data/types";
import { finite } from "./format";

/** Tryb Wilgotnosc wymaga M w scores.json (starsze migawki go nie maja). */
export function moistureAvailable(scores: Score[]): boolean {
  return scores.some((s) => finite(s.M));
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
