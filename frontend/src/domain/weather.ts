import type { ForecastUncertainty } from "../data/types";

const WEEKDAYS = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];

export function dayLabel(dateIso: string, position: number): string {
  if (position === 0) return "dziś";
  return WEEKDAYS[new Date(`${dateIso}T12:00:00`).getDay()];
}

/** Oznaczenie dnia prognozy: "prognoza niepewna" (od progu 1) i "orientacyjnie" (od progu 2). */
export function uncertaintyLabel(level: ForecastUncertainty | undefined): string | null {
  if (level === "uncertain") return "prognoza niepewna";
  if (level === "indicative") return "orientacyjnie";
  return null;
}
