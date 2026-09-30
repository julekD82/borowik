// Nakladka przejsciowa (nowy frontend, plan 2026-10-01): kod przeniesiony do src/data i
// src/domain; ponizej zostaja tylko funkcje starego interfejsu (usuwane w Task 17).
export * from "./data/types";
export * from "./data/parse";
export * from "./data/load";
export * from "./domain/format";
export * from "./domain/geometry";
export * from "./domain/ranking";
export * from "./domain/labels";
export * from "./domain/access";
export * from "./domain/bars";
export * from "./domain/moisture";
export * from "./domain/weather";
import type {
  AccessCard, ConditionsDay, Explanation, ForecastUncertainty, HabitatCard, Region, Score, WeatherCard,
} from "./data/types";
import { dayMonth, finiteNumber, formatValue, pl } from "./domain/format";
import { parseAccessCollection, parseConditions, parseData } from "./data/parse";
import { dayLabel, uncertaintyLabel } from "./domain/weather";
import type { ComponentRow } from "./domain/access";

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

export function topExplanations(
  items: Explanation[],
  count = 2,
): Explanation[] {
  return [...items]
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, count);
}

// Kolorowanie wydzielen wg rankingu R: 6 kolorow od jasnego zolto-zielonego do
// ciemnego granatu, przypietych do PERCENTYLI R w tej analizie (a nie do stalej
// skali 0-100, na ktorej prawie wszystkie wydzielenia wpadaly w ten sam zielony).
export const RANK_COLORS = [
  "#efe9b5",
  "#c5df8f",
  "#7fc47a",
  "#2f9a72",
  "#1c6a80",
  "#24356b",
];

export const RANK_QUANTILES = [0.02, 0.25, 0.5, 0.75, 0.9, 0.98];

export const RANK_ZERO_COLOR = "#d5d5b8"; // wydzielenia odrzucone przez maske (R = 0)

export function rankColorStops(values: (number | null | undefined)[]): [number, string][] {
  const sorted = values
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v) && v > 0)
    .sort((a, b) => a - b);
  const fallback = (): [number, string][] =>
    RANK_COLORS.map((c, i) => [(100 * i) / (RANK_COLORS.length - 1), c]);
  if (sorted.length < 2) return fallback();
  const at = (q: number) => {
    const pos = q * (sorted.length - 1);
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  };
  const stops: [number, string][] = [];
  RANK_QUANTILES.forEach((q, i) => {
    let v = at(q);
    // MapLibre wymaga scisle rosnacych progow
    if (stops.length && v <= stops[stops.length - 1][0]) v = stops[stops.length - 1][0] + 1e-6;
    stops.push([v, RANK_COLORS[i]]);
  });
  return stops.length === RANK_COLORS.length && sorted[sorted.length - 1] > sorted[0] ? stops : fallback();
}

// Karta wydzielenia: "najbliższy parking X m, wjazd Y m, utwardzony dukt Z m".
export function accessCardSummary(card?: AccessCard | null): string {
  if (!card) return "";
  const m = (v: number | null) =>
    typeof v === "number" && Number.isFinite(v)
      ? `${Math.round(v / 10) * 10} m`
      : "brak w pobliżu";
  return `najbliższy parking ${m(card.d_parking_m)} · wjazd lub szlaban ${m(card.d_entrance_m)} · utwardzony dukt ${m(card.d_hard_forest_road_m)}`;
}

export async function loadData(basePath: string = "data/") {
  const [scoresRaw, standsRaw] = await Promise.all(
    ["scores.json", "stands.geojson"].map(async (file) => {
      const response = await fetch(`${import.meta.env.BASE_URL}${basePath}${file}`, {
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
  //
  // `response.ok` alone is not enough: `npm run dev`'s dev server answers
  // a GET for a genuinely missing file with 200 text/html (its SPA
  // fallback to index.html), not 404 -- this is common (any saved trip or
  // run predating an optional file, e.g. this plan's own conditions.json).
  // Without the content-type check below, that 200 is trusted as "the
  // file exists", `.json()` throws on the HTML body, and an optional
  // file's ABSENCE turns into a fatal error for the whole map.
  const isJsonResponse = (response: Response) =>
    response.headers.get("content-type")?.includes("json") ?? false;
  let regionsRaw: unknown = undefined;
  const regionsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}regions.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (regionsResponse?.ok && isJsonResponse(regionsResponse)) {
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
    `${import.meta.env.BASE_URL}${basePath}details.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (detailsResponse?.ok && isJsonResponse(detailsResponse)) {
    try {
      detailsRaw = await detailsResponse.json();
    } catch {
      throw new Error(
        "Plik details.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.",
      );
    }
  }
  // conditions.json is optional too, same reasoning as regions/details
  // above -- plan A2 Plan-B.
  let conditionsRaw: unknown = undefined;
  const conditionsResponse = await fetch(
    `${import.meta.env.BASE_URL}${basePath}conditions.json`,
    { cache: "no-cache", signal: AbortSignal.timeout(20000) },
  ).catch(() => undefined);
  if (conditionsResponse?.ok && isJsonResponse(conditionsResponse)) {
    try {
      conditionsRaw = await conditionsResponse.json();
    } catch {
      throw new Error(
        "Plik conditions.json jest niedostępny lub niepoprawny. Uruchom synchronizację danych.",
      );
    }
  }
  // access_points.json / forest_roads.json: optional layers (Faza 3.5), same
  // tolerance for a missing file as the optional files above.
  const optionalJson = async (file: string): Promise<unknown> => {
    const response = await fetch(
      `${import.meta.env.BASE_URL}${basePath}${file}`,
      { cache: "no-cache", signal: AbortSignal.timeout(20000) },
    ).catch(() => undefined);
    if (!response?.ok || !isJsonResponse(response)) return undefined;
    try {
      return await response.json();
    } catch {
      throw new Error(`Plik ${file} jest niedostępny lub niepoprawny. Uruchom synchronizację danych.`);
    }
  };
  const accessPoints = parseAccessCollection(await optionalJson("access_points.json"), "access_points.json");
  const forestRoads = parseAccessCollection(await optionalJson("forest_roads.json"), "forest_roads.json");
  const regionsNoPressureRaw = await optionalJson("regions_bez_presji.json");
  const manifest = (await optionalJson("manifest.json")) as
    | { wfs_only_share_of_masked?: unknown; lat?: unknown; lon?: unknown; pressure_alpha?: unknown }
    | undefined;
  const parsed = parseData(scoresRaw, standsRaw, regionsRaw, detailsRaw, regionsNoPressureRaw);
  return {
    ...parsed,
    wfsOnlyShare: finiteNumber(manifest?.wfs_only_share_of_masked) ? manifest.wfs_only_share_of_masked : null,
    // Faza UI.3: punkt startu analizy (odleglosc na liscie) i waga presji (Szczegoly).
    start:
      finiteNumber(manifest?.lat) && finiteNumber(manifest?.lon)
        ? ([manifest.lon, manifest.lat] as [number, number])
        : null,
    pressureAlpha: finiteNumber(manifest?.pressure_alpha) ? manifest.pressure_alpha : null,
    conditions: parseConditions(conditionsRaw, parsed.scores[0]?.day),
    accessPoints,
    forestRoads,
  };
}

export const WEATHER_DISCLAIMER =
  "Ocena pogody nie została potwierdzona na danych o znaleziskach; traktuj ją jako orientację, nie prognozę wysypu.";

export function uncertaintyNote(level: ForecastUncertainty | undefined): string | null {
  if (level === "uncertain")
    return "Prognoza pogody na kilka dni naprzód bywa niedokładna; ocena tego dnia może się zmienić.";
  if (level === "indicative")
    return "Prognoza odległa o tydzień lub więcej — wartość tylko orientacyjna.";
  return null;
}

/** Linie skladnikow pogody dla panelu (mediana obszaru) lub karty wydzielenia. */
export function weatherComponentLines(c: {
  cwb26_mm: number | null;
  cwb26_typical_mm: number | null;
  pct_cwb26: number | null;
  tmean20_c: number | null;
  temp_optimum_c: number | null;
}): string[] {
  const lines: string[] = [];
  if (finiteNumber(c.cwb26_mm) && finiteNumber(c.cwb26_typical_mm) && finiteNumber(c.pct_cwb26))
    lines.push(
      `Bilans wodny z 26 dni (opad minus parowanie): ${pl(c.cwb26_mm)} mm, typowo o tej porze ${pl(c.cwb26_typical_mm)} mm (percentyl ${pl(Math.round(c.pct_cwb26 * 100))})`,
    );
  if (finiteNumber(c.tmean20_c))
    lines.push(
      `Średnia temperatura 20 dni: ${pl(c.tmean20_c, 1)} °C${finiteNumber(c.temp_optimum_c) ? ` (optimum ok. ${pl(c.temp_optimum_c)} °C)` : ""}`,
    );
  return lines;
}

/** Pelne linie karty wydzielenia: skladniki, przymrozek (tak/nie, kiedy), F jako liczba, udzial prognozy. */
export function weatherCardLines(w: WeatherCard): string[] {
  const daysAhead = finiteNumber(w.forecast_days) ? w.forecast_days - 1 : null;
  const lines = weatherComponentLines(w);
  if (w.p26_mm !== null && finiteNumber(w.p26_mm)) lines.unshift(`Opad z ostatnich 26 dni: ${pl(w.p26_mm)} mm`);
  if (w.frost === "brak") lines.push("Przymrozek w ostatnich 3 dobach: nie");
  else if (w.frost === "slaby" || w.frost === "silny")
    lines.push(
      `Przymrozek w ostatnich 3 dobach: tak (${w.frost === "silny" ? "silny" : "słaby"}, min ${finiteNumber(w.tmin3_c) ? pl(w.tmin3_c, 1) : "?"} °C${w.frost_date ? `, ${dayMonth(w.frost_date)}` : ""})`,
    );
  if (finiteNumber(w.F)) lines.push(`Ocena pogody F: ${pl(w.F, 2)}`);
  if (daysAhead !== null && daysAhead >= 4 && finiteNumber(w.forecast_window_share))
    lines.push(
      `Wyjazd za ${daysAhead} dni: ok. ${pl(Math.round(w.forecast_window_share * 100))}% oceny opadu pochodzi z prognozy, nie z obserwacji`,
    );
  return lines;
}

/** Udzial powierzchni z przymrozkiem / silnym opadem w panelu (tylko gdy niezerowy). */
export function localPhenomenaNote(d: ConditionsDay): string | null {
  const parts: string[] = [];
  if (finiteNumber(d.frost_area_share) && d.frost_area_share > 0)
    parts.push(`przymrozek na ${pl(Math.round(d.frost_area_share * 100))}% lasu`);
  if (finiteNumber(d.heavy_rain_area_share) && d.heavy_rain_area_share > 0)
    parts.push(`silny opad na ${pl(Math.round(d.heavy_rain_area_share * 100))}% lasu`);
  return parts.length ? parts.join(", ") : null;
}

/** Plan 1.3: ostrzezenie, gdy > 20% wydzielen w masce ma sklad tylko z WFS (brak paczki BDL). */
export const WFS_ONLY_BANNER_THRESHOLD = 0.2;

export function wfsOnlyBanner(share: number | null | undefined): string | null {
  if (!finiteNumber(share) || share <= WFS_ONLY_BANNER_THRESHOLD) return null;
  return `Skład drzewostanu tylko z opisu WFS (bez paczki BDL) dla ${pl(Math.round(share * 100))}% wydzieleń w masce — ocena siedliska H jest tu mniej dokładna.`;
}

// ---- Faza UI: przelacznik presji, paski wyniku, nazwy, fakty karty (czyste funkcje, testowane) ----

/** Skladniki paska Siedlisko: sklad drzewostanu, typ siedliska, wiek (S_age). */
export function habitatComponents(h: HabitatCard | null | undefined): ComponentRow[] {
  if (!h) return [];
  const neutral = h.age_mode === "neutral";
  return [
    { label: "Skład drzewostanu", value: formatValue(h.S_host) },
    { label: "Typ siedliska", value: formatValue(h.S_site) },
    neutral
      ? { label: "Wiek drzewostanu", value: "—", note: "nie wpływa na wynik" }
      : { label: "Wiek drzewostanu", value: formatValue(h.S_age) },
  ];
}

/** Skladniki paska Pogoda: wilgotnosc (M), temperatura (T), przymrozek (K_frost). */
export function weatherComponents(w: WeatherCard | null | undefined): ComponentRow[] {
  if (!w) return [];
  const rows: ComponentRow[] = [];
  if (w.M !== undefined) rows.push({ label: "Wilgotność", value: formatValue(w.M) });
  if (w.T !== undefined) rows.push({ label: "Temperatura", value: formatValue(w.T) });
  if (w.K_frost !== undefined)
    rows.push({
      label: "Przymrozek",
      value: formatValue(w.K_frost),
      note: w.frost === "brak" ? "brak przymrozku" : w.frost ? "był przymrozek" : undefined,
    });
  return rows;
}

export type ConditionBar = {
  label: string;
  value: number;
  level: number;
  uncertainty: ForecastUncertainty;
  title: string;
};

/** 7 dni panelu jako male slupki F (wysokosc = F), z oznaczeniem niepewnosci z 4.5. */
export function conditionBars(
  days: ConditionsDay[],
  formatDate: (iso: string) => string,
): ConditionBar[] {
  return days.map((d, i) => {
    const uncertain = uncertaintyLabel(d.uncertainty);
    const local = localPhenomenaNote(d);
    return {
      label: dayLabel(d.date, i),
      value: Math.max(0, Math.min(1, d.F)),
      level: d.level,
      uncertainty: d.uncertainty ?? "ok",
      title: `${formatDate(d.date)}: ${Math.round(d.F * 100)}/100${uncertain ? ` · ${uncertain}` : ""}${local ? ` · ${local}` : ""}`,
    };
  });
}

// ---- Tryby kolorowania mapy: Wynik / Wynik bez presji / Wilgotnosc (czyste funkcje, testowane) ----

export type MapColorMode = "score" | "score_no_pressure" | "moisture";

export type MapControls = { pressure: boolean; colorMode: MapColorMode };

export const MAP_COLOR_KEY = "borowik.map-color.v1";

export const colorModeForPressure = (pressure: boolean): MapColorMode =>
  pressure ? "score" : "score_no_pressure";

/**
 * Wybor jednego z trzech przyciskow mapy. "Wynik" i "Wynik bez presji" ustawiaja tez przelacznik
 * presji (jedna prawda, bez sprzecznych kontrolek); "Wilgotnosc" zmienia tylko kolory mapy --
 * lista i rejony zostaja w ostatnim trybie wynik/wynik bez presji. Zwraca null, gdy wybor jest
 * niedostepny (brak R_bez_presji albo M w migawce).
 */
export function chooseColorMode(
  state: MapControls,
  mode: MapColorMode,
  available: { pressure: boolean; moisture: boolean },
): MapControls | null {
  if (mode === "moisture") return available.moisture ? { pressure: state.pressure, colorMode: mode } : null;
  if (mode === "score_no_pressure" && !available.pressure) return null;
  return { pressure: mode === "score", colorMode: mode };
}

/** Przelacznik presji zawsze wraca mapie kolor zgodny z rankingiem (wynik / wynik bez presji). */
export function togglePressureControls(
  on: boolean,
  available: { pressure: boolean },
): MapControls {
  const pressure = on || !available.pressure;
  return { pressure, colorMode: colorModeForPressure(pressure) };
}

/** Stan poczatkowy: presja z przelacznika, a zapamietany tryb Wilgotnosc tylko gdy dostepny. */
export function resolveColorMode(
  stored: string | null,
  pressure: boolean,
  isMoistureAvailable: boolean,
): MapColorMode {
  return stored === "moisture" && isMoistureAvailable ? "moisture" : colorModeForPressure(pressure);
}

export const MOISTURE_NOTE =
  "Bilans opad − parowanie z 26 dni względem typowego dla tej pory roku. To nie pomiar wilgotności gleby.";
