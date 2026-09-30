import { batch, computed, signal } from "@preact/signals";
import type { AccessCollection, AccessLayerId, Analysis, StandDetail, StandFeature, TripMeta } from "../data/types";
import { ACCESS_LAYERS } from "../domain/access";
import { finite } from "../domain/format";
import { standName, tooltipText } from "../domain/labels";
import { moistureAvailable } from "../domain/moisture";
import {
  classifyByPercentile, effectiveR, isStandaloneTarget, joinRegions, pressureSwitchAvailable, rankEntries,
  type ScoreClass,
} from "../domain/ranking";
import { buildWeatherPanel } from "../domain/weather";
import { KEYS, readPref, writePref } from "./prefs";

export type Tab = "regions" | "stands";
export type PanelView = { kind: "list" } | { kind: "region"; regionId: string } | { kind: "stand"; standId: string };
export type MapMode = "score" | "moisture";
export type LoadStatus = { status: "loading" } | { status: "ready" } | { status: "error"; message: string };
export type FitRequest = { target: "stand"; id: string } | { target: "region"; id: string } | { target: "all" };
export type StandMapProps = { cls: ScoreClass | 0; moisture: number | null; pressure: number | null; region: number };
export type RegionMarker = { id: string; number: number; point: [number, number] };
type AccessState = { loaded: boolean; points: AccessCollection | null; roads: AccessCollection | null };

function initialLayers(): Record<AccessLayerId, boolean> {
  const state = Object.fromEntries(ACCESS_LAYERS.map((l) => [l.id, l.defaultOn])) as Record<AccessLayerId, boolean>;
  try {
    const saved = JSON.parse(readPref(KEYS.layers) ?? "null");
    if (saved && typeof saved === "object")
      for (const l of ACCESS_LAYERS) if (typeof saved[l.id] === "boolean") state[l.id] = saved[l.id];
  } catch {
    // Uszkodzony zapis: warstwy domyslne.
  }
  return state;
}

export const analysis = signal<Analysis | null>(null);
// null = szczegoly jeszcze sie wczytuja; pusta mapa = brak pliku szczegolow.
export const details = signal<Map<string, StandDetail> | null>(null);
export const access = signal<AccessState>({ loaded: false, points: null, roads: null });
export const load = signal<LoadStatus>({ status: "loading" });
export const trips = signal<TripMeta[]>([]);
export const tripId = signal<string | null>(null);
export const pressurePref = signal(readPref(KEYS.pressure) !== "off");
export const mapModePref = signal<MapMode>(readPref(KEYS.mapMode) === "moisture" ? "moisture" : "score");
export const layers = signal(initialLayers());
export const tab = signal<Tab>(readPref(KEYS.tab) === "stands" ? "stands" : "regions");
export const stack = signal<PanelView[]>([{ kind: "list" }]);
export const mobilePane = signal<"list" | "map">("list");
export const showSmall = signal(false);
export const standPage = signal(1);
export const fitRequest = signal<{ req: FitRequest; seq: number } | null>(null);
export const toast = signal<string | null>(null);
export const aboutOpen = signal(false);
export const mapStatus = signal<string | null>(null);

export const pressureAvailable = computed(() => {
  const a = analysis.value;
  return !!a && pressureSwitchAvailable(a.scores, a.regionsNoPressure);
});
// Migawka bez wynikow bez presji: ranking zawsze z presja (jedyny, jaki jest).
export const pressure = computed(() => (pressureAvailable.value ? pressurePref.value : true));
export const moistureOk = computed(() => !!analysis.value && moistureAvailable(analysis.value.scores));
export const mapMode = computed<MapMode>(() => (mapModePref.value === "moisture" && moistureOk.value ? "moisture" : "score"));
export const ranked = computed(() => (analysis.value ? rankEntries(analysis.value.entries, pressure.value) : []));
export const rankIndex = computed(() => new Map(ranked.value.map((e, i) => [e.score.stand_id, i])));
export const classById = computed(() => {
  const list = ranked.value;
  const classes = classifyByPercentile(list.map((e) => e.r));
  return new Map(list.map((e, i) => [e.score.stand_id, classes[i]]));
});
export const regionViews = computed(() => {
  const a = analysis.value;
  if (!a) return [];
  return joinRegions(pressure.value ? a.regions : (a.regionsNoPressure ?? []), ranked.value);
});
export const top = computed(() => stack.value[stack.value.length - 1]);
export const selectedStandId = computed(() => (top.value.kind === "stand" ? top.value.standId : null));
export const activeRegionId = computed(() => {
  for (let i = stack.value.length - 1; i >= 0; i--) {
    const view = stack.value[i];
    if (view.kind === "region") return view.regionId;
  }
  return null;
});
export const start = computed<[number, number] | null>(() => {
  const m = analysis.value?.manifest;
  return m && m.lat !== null && m.lon !== null ? [m.lon, m.lat] : null;
});
export const weatherModel = computed(() => buildWeatherPanel(analysis.value?.conditions ?? null));
export const regionMarkers = computed<RegionMarker[]>(() =>
  regionViews.value.map((v, i) => ({ id: v.region.region_id, number: i + 1, point: [v.region.centroid_lon, v.region.centroid_lat] })),
);
const regionNumberById = computed(() => {
  const numbers = new Map<string, number>();
  regionViews.value.forEach((v, i) => v.region.stand_ids.forEach((id) => { if (!numbers.has(id)) numbers.set(id, i + 1); }));
  return numbers;
});
export const standProps = computed(() => {
  const props = new Map<string, StandMapProps>();
  const a = analysis.value;
  if (!a) return props;
  for (const s of a.scores)
    props.set(s.stand_id, {
      cls: s.mask ? (classById.value.get(s.stand_id) ?? 4) : 0,
      moisture: finite(s.M) ? s.M : null,
      pressure: finite(s.P) ? s.P : null,
      region: regionNumberById.value.get(s.stand_id) ?? 0,
    });
  return props;
});
export const selection = computed(() => {
  const regionId = activeRegionId.value;
  const view = regionId ? regionViews.value.find((v) => v.region.region_id === regionId) : undefined;
  return { standId: selectedStandId.value, regionStandIds: view ? view.members.map((m) => m.score.stand_id) : [] };
});
export const visibleStands = computed(() => ranked.value.filter((e) => showSmall.value || isStandaloneTarget(e.score)));

let fitSeq = 0;
function requestFit(req: FitRequest): void {
  fitRequest.value = { req, seq: ++fitSeq };
}
export const requestFitAll = () => requestFit({ target: "all" });

export function setTab(next: Tab): void {
  batch(() => {
    tab.value = next;
    stack.value = [{ kind: "list" }];
    standPage.value = 1;
  });
  writePref(KEYS.tab, next);
}

export function openRegion(regionId: string, source: "list" | "map"): void {
  batch(() => {
    if (source === "map") {
      tab.value = "regions";
      stack.value = [{ kind: "list" }, { kind: "region", regionId }];
      mobilePane.value = "list";
    } else stack.value = [...stack.value, { kind: "region", regionId }];
  });
  if (source === "list") requestFit({ target: "region", id: regionId });
}

export function openStand(standId: string, source: "list" | "map"): void {
  const current = stack.value;
  const base = current[current.length - 1].kind === "stand" ? current.slice(0, -1) : current;
  batch(() => {
    stack.value = [...base, { kind: "stand", standId }];
    if (source === "map") mobilePane.value = "list";
  });
  if (source === "list") requestFit({ target: "stand", id: standId });
}

export function back(): void {
  if (stack.value.length > 1) stack.value = stack.value.slice(0, -1);
}

export function setPressure(on: boolean): void {
  batch(() => {
    pressurePref.value = on;
    // Rejony z presja i bez presji maja te same identyfikatory (region_1...), ale to inne rejony --
    // karta rejonu nie moze po przelaczeniu pokazac innego rejonu pod tym samym id.
    const kept = stack.value.filter((v) => v.kind !== "region");
    stack.value = kept.length ? kept : [{ kind: "list" }];
  });
  writePref(KEYS.pressure, on ? "on" : "off");
}

export function setMapMode(mode: MapMode): void {
  mapModePref.value = mode;
  writePref(KEYS.mapMode, mode);
}

export function setLayer(id: AccessLayerId, on: boolean): void {
  layers.value = { ...layers.value, [id]: on };
  writePref(KEYS.layers, JSON.stringify(layers.value));
}

let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function notify(message: string): void {
  toast.value = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = null;
  }, 4500);
}

export function resetView(): void {
  batch(() => {
    stack.value = [{ kind: "list" }];
    standPage.value = 1;
  });
}

export function featuresFor(req: FitRequest): StandFeature[] {
  const a = analysis.value;
  if (!a) return [];
  if (req.target === "stand") {
    const feature = a.features.get(req.id);
    return feature ? [feature] : [];
  }
  if (req.target === "region") {
    const view = regionViews.value.find((v) => v.region.region_id === req.id);
    return view ? view.members.map((m) => m.feature) : [];
  }
  return ranked.value.length ? ranked.value.map((e) => e.feature) : [...a.features.values()];
}

export function standTooltip(id: string): string | null {
  const a = analysis.value;
  const score = a?.scoreById.get(id);
  if (!a || !score) return null;
  const name = standName(id, details.value?.get(id) ?? null);
  const cls = standProps.value.get(id)?.cls ?? 0;
  return tooltipText(name, cls === 0 ? null : effectiveR(score, pressure.value), cls);
}

// Tylko dla testow: wszystkie sygnaly do stanu poczatkowego (ustawienia z localStorage).
export function resetStore(): void {
  batch(() => {
    analysis.value = null;
    details.value = null;
    access.value = { loaded: false, points: null, roads: null };
    load.value = { status: "loading" };
    trips.value = [];
    tripId.value = null;
    pressurePref.value = readPref(KEYS.pressure) !== "off";
    mapModePref.value = readPref(KEYS.mapMode) === "moisture" ? "moisture" : "score";
    layers.value = initialLayers();
    tab.value = readPref(KEYS.tab) === "stands" ? "stands" : "regions";
    stack.value = [{ kind: "list" }];
    mobilePane.value = "list";
    showSmall.value = false;
    standPage.value = 1;
    fitRequest.value = null;
    toast.value = null;
    aboutOpen.value = false;
    mapStatus.value = null;
  });
}
