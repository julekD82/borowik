import { batch } from "@preact/signals";
import { loadBackground, loadCore, loadTrips } from "../data/load";
import type { Analysis } from "../data/types";
import {
  access, analysis, details, load, notify, regionViews, requestFitAll, resetView, tab, tripId, trips,
} from "./store";

let token = 0;

export const basePathFor = (id: string | null) => (id ? `data/trips/${id}/` : "data/");

// Kazde otwarcie dostaje wlasny numer; wynik starszego wczytywania (np. szczegoly w tle)
// jest ignorowany, jesli w miedzyczasie otwarto inna analize.
export async function openAnalysis(basePath: string, id: string | null): Promise<void> {
  const mine = ++token;
  batch(() => {
    load.value = { status: "loading" };
    tripId.value = id;
    details.value = null;
    access.value = { loaded: false, points: null, roads: null };
    resetView();
  });
  let core: Analysis;
  try {
    core = await loadCore(basePath);
  } catch (error) {
    if (mine === token) load.value = { status: "error", message: error instanceof Error ? error.message : String(error) };
    return;
  }
  if (mine !== token) return;
  batch(() => {
    analysis.value = core;
    load.value = { status: "ready" };
    if (tab.value === "regions" && regionViews.value.length === 0) tab.value = "stands";
  });
  requestFitAll();
  loadBackground(core).then(
    (bg) => {
      if (mine !== token) return;
      batch(() => {
        details.value = bg.details;
        access.value = { loaded: true, points: bg.accessPoints, roads: bg.forestRoads };
      });
    },
    (error) => {
      if (mine !== token) return;
      batch(() => {
        details.value = new Map();
        access.value = { loaded: true, points: null, roads: null };
      });
      notify(error instanceof Error ? error.message : "Nie udało się wczytać szczegółów wydzieleń.");
    },
  );
}

export function retry(): Promise<void> {
  return openAnalysis(basePathFor(tripId.value), tripId.value);
}

export async function startApp(): Promise<void> {
  trips.value = await loadTrips();
  await openAnalysis("data/", null);
}
