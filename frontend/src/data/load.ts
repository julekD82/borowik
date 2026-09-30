import type { TripMeta } from "./types";
import { parseTrips } from "./parse";

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
