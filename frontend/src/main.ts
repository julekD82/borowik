import "maplibre-gl/dist/maplibre-gl.css";
import "./style.css";
import {
  loadData,
  joinRegions,
  rankEntries,
  pressureSwitchAvailable,
  chooseColorMode,
  togglePressureControls,
  resolveColorMode,
  moistureAvailable,
  MAP_COLOR_KEY,
  MOISTURE_STOPS,
  MOISTURE_LEGEND_TICKS,
  MOISTURE_NOTE,
  moistureTickLabel,
  scoreBars,
  habitatComponents,
  weatherComponents,
  pressureTop,
  standName,
  parseStandId,
  regionName,
  keyFacts,
  areaLabel,
  startDistanceLabel,
  conditionBars,
  formatValue,
  fruitingClass,
  habitatClass,
  confidenceLabel,
  entranceLabel,
  distanceLabel,
  distanceMethod,
  zakazNote,
  topExplanations,
  navigationUrl,
  finite,
  isStandaloneTarget,
  standStructureLabel,
  densityLabel,
  neighborsSummary,
  loadTrips,
  formatTripLabel,
  accessCardSummary,
  topPointSummary,
  regionAccessSummary,
  ACCESS_LAYERS,
  SURFACE_COLORS,
  SURFACE_LABELS,
  WEATHER_DISCLAIMER,
  uncertaintyLabel,
  uncertaintyNote,
  weatherComponentLines,
  weatherCardLines,
  localPhenomenaNote,
  wfsOnlyBanner,
  dayLabel,
} from "./model";
import type {
  AccessCard,
  AccessCollection,
  AccessLayerId,
  Bar,
  ComponentRow,
  MapColorMode,
} from "./model";
import type {
  StandView,
  Score,
  Region,
  RegionView,
  StandDetail,
  SpeciesShare,
  TripMeta,
  ConditionsTimeline,
} from "./model";
import { ForestMap } from "./map";
import { readSaved, saveRegion, removeSaved, savedKey } from "./storage";
import type { SavedRegion } from "./storage";

const icon = (name: string) => {
  const paths: Record<string, string> = {
    mushroom:
      '<path d="M3 12a9 9 0 0 1 18 0Z"/><path d="M9 12v7a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-7M8 8h.01M14 6h.01M17 9h.01"/>',
    map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Zm6-3v15m6-12v15"/>',
    bookmark: '<path d="M6 3h12v18l-6-4-6 4Z"/>',
    arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
    location: '<path d="m21 3-7 18-3-8-8-3Z"/>',
    leaf: '<path d="M20 3c-9-1-17 3-17 10a7 7 0 0 0 7 7c7 0 11-8 10-17ZM4 20 15 9"/>',
    calendar:
      '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.01"/>',
    target:
      '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? paths.info}</svg>`;
};
const escape = (value: unknown) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
const formatDate = (day: string) =>
  new Date(`${day}T12:00:00`).toLocaleDateString("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
const coordinates = ([lon, lat]: [number, number]) =>
  `${lat.toFixed(5)}° N, ${lon.toFixed(5)}° E`;

// Faza UI.3: pasek pogody u gory -- jedno zdanie + 7 dni jako male slupki F (wysokosc = F,
// z oznaczeniem niepewnosci z 4.5); reszta dotychczasowego tekstu w zwinietych Szczegolach.
function conditionsHtml(median: number | null, conditions: ConditionsTimeline | null): string {
  const moisture = fruitingClass(median).toLocaleLowerCase("pl");
  if (!conditions)
    return `<span class="condition-symbol">${icon("leaf")}</span><div class="cond-main"><strong>Warunki w obszarze: ${moisture}</strong><details class="cond-details"><summary>Szczegóły pogody</summary><p>Ocena pogody z analizy · mediana dla wydzieleń przechodzących filtry.</p><p class="weather-disclaimer">${escape(WEATHER_DISCLAIMER)}</p></details></div>`;
  const bars = conditionBars(conditions.days, formatDate)
    .map(
      (b) =>
        `<li class="cond-bar level-${b.level}${b.uncertainty !== "ok" ? ` uncertain-${b.uncertainty}` : ""}" title="${escape(b.title)}" aria-label="${escape(b.label + ": " + b.title)}"><span class="cond-col"><i style="height:${Math.max(6, Math.round(b.value * 100))}%"></i></span><span class="cond-day">${escape(b.label)}${b.uncertainty === "uncertain" ? "?" : b.uncertainty === "indicative" ? "~" : ""}</span></li>`,
    )
    .join("");
  const today = conditions.days[0];
  const componentLines = today?.components ? weatherComponentLines(today.components) : [];
  const localLines = conditions.days
    .map((d, i) => ({ label: dayLabel(d.date, i), note: localPhenomenaNote(d) }))
    .filter((x) => x.note)
    .map((x) => `${x.label}: ${x.note}`);
  const firstUncertain = conditions.days.find((d) => d.uncertainty && d.uncertainty !== "ok");
  const uncertainNote = firstUncertain ? uncertaintyNote(firstUncertain.uncertainty) : null;
  const legend = conditions.days
    .map((d) => uncertaintyLabel(d.uncertainty))
    .some((x) => x !== null)
    ? '<p class="weather-local">? prognoza niepewna (od 4. dnia) · ~ orientacyjnie (od 8. dnia)</p>'
    : "";
  const details = [
    `<p>Warunki wilgotności: ${moisture} · prognoza F na kolejne dni z pogody (radar/model), bez przewidywania szczytu wysypu.</p>`,
    componentLines.length ? `<ul class="weather-components" aria-label="Składniki pogody">${componentLines.map((l) => `<li>${escape(l)}</li>`).join("")}</ul>` : "",
    localLines.length ? `<p class="weather-local">Lokalnie: ${escape(localLines.join(" · "))}</p>` : "",
    legend,
    uncertainNote ? `<p class="weather-uncertain">${escape(uncertainNote)}</p>` : "",
    `<p class="weather-disclaimer">${escape(WEATHER_DISCLAIMER)}</p>`,
  ].join("");
  return `<span class="condition-symbol">${icon("mushroom")}</span><div class="cond-main"><strong>${escape(conditions.summary)}</strong><ol class="cond-bars" aria-label="Ocena pogody F na kolejne dni">${bars}</ol><details class="cond-details"><summary>Szczegóły pogody</summary>${details}</details></div>`;
}
let entries: StandView[] = [];
let baseEntries: StandView[] = [];
let allScores: Score[] = [];
let regionsWithPressure: Region[] = [];
let regionsWithoutPressure: Region[] | null = null;
let detailsById = new Map<string, StandDetail>();
let regionViews: RegionView[] = [];
let startPoint: [number, number] | null = null;
let pressureAlpha: number | null = null;
let pressure = true;
let pressureAvailable = false;
// Tryby kolorowania mapy: "Wynik" / "Wynik bez presji" idą za przełącznikiem presji, "Wilgotność"
// (skladowa M, skala bezwzgledna) zmienia tylko kolory mapy.
let colorMode: MapColorMode = "score";
let moistureOk = false;
let selected = "";
const PAGE_SIZE = 30;
let page = 0;
let savedOnly = false;
let map: ForestMap | undefined;
let loaded = false;
let loadError = "";
let noticeTimer: ReturnType<typeof setTimeout>;
let savedTrips: TripMeta[] = [];
let currentTripId: string | null = null;
let currentBasePath = "data/";
// "regions" (grouped) vs "stands" (flat, every wydzielenie individually) --
// two peer views over the same analysis, not one replacing the other.
let viewMode: "regions" | "stands" = "regions";
let selectedRegionId = "";
// Set via a region card's "Zobacz wydzielenia w rejonie": while non-null,
// the stand view (list, map, detail) is scoped to just that region's
// members, with a way back to the region view instead of the full list.
let regionFilterId: string | null = null;
// Faza UI.4: na telefonie lista i mapa to zakladki (jedna widoczna naraz).
let mobilePane: "list" | "map" = "list";
const VIEW_MODE_KEY = "borowik.view-mode.v1";
// Faza UI.1: przelacznik presji grzybiarzy (zapamietywany lokalnie, domyslnie wlaczony).
const PRESSURE_KEY = "borowik.pressure.v1";
// Faza 3.5: ktore warstwy dostepu sa wlaczone (zapamietywane w przegladarce).
const LAYERS_KEY = "borowik.access-layers.v1";
let layerState: Record<AccessLayerId, boolean> = Object.fromEntries(
  ACCESS_LAYERS.map((l) => [l.id, l.defaultOn]),
) as Record<AccessLayerId, boolean>;
try {
  const saved = JSON.parse(localStorage.getItem(LAYERS_KEY) ?? "null");
  if (saved && typeof saved === "object")
    for (const l of ACCESS_LAYERS)
      if (typeof saved[l.id] === "boolean") layerState[l.id] = saved[l.id];
} catch {
  // Best-effort: domyslne ustawienia warstw.
}
function saveLayerState() {
  try {
    localStorage.setItem(LAYERS_KEY, JSON.stringify(layerState));
  } catch {
    // Best-effort.
  }
}
function getPressurePreference(): boolean {
  try {
    return localStorage.getItem(PRESSURE_KEY) !== "off";
  } catch {
    return true;
  }
}
function setPressurePreference(on: boolean) {
  try {
    localStorage.setItem(PRESSURE_KEY, on ? "on" : "off");
  } catch {
    // Best-effort only.
  }
}
function getColorModePreference(): string | null {
  try {
    return localStorage.getItem(MAP_COLOR_KEY);
  } catch {
    return null;
  }
}
function setColorModePreference(mode: MapColorMode) {
  try {
    localStorage.setItem(MAP_COLOR_KEY, mode);
  } catch {
    // Best-effort only.
  }
}
function renderLayerControls(
  points: AccessCollection | null,
  roads: AccessCollection | null,
) {
  const has = (need: string) =>
    need === "points" ? !!points : need === "roads" ? !!roads : true;
  const available = ACCESS_LAYERS.filter((l) => has(l.needs));
  const el = $("#layer-controls");
  // Bez plikow warstw (starsza analiza) sama legenda, bez przelacznikow.
  el.hidden = !points && !roads;
  if (el.hidden) return;
  const surfaces = Object.keys(SURFACE_COLORS)
    .map(
      (k) =>
        `<span class="layer-key"><i style="background:${SURFACE_COLORS[k]}"></i>${SURFACE_LABELS[k]}</span>`,
    )
    .join("");
  el.innerHTML = `<div class="layer-toggles">${available
    .map(
      (l) =>
        `<label class="layer-toggle"><input type="checkbox" data-layer="${l.id}" ${layerState[l.id] ? "checked" : ""}> ${l.label}</label>`,
    )
    .join("")}</div><div class="layer-keys"><span class="layer-key"><i class="key-parking bdl"></i>parking BDL</span><span class="layer-key"><i class="key-parking osm"></i>parking OSM</span><span class="layer-key"><i class="key-entrance"></i>wjazd</span><span class="layer-key"><i class="key-gate"></i>szlaban</span>${surfaces}<span class="layer-key">linia ciągła: publiczna · przerywana: zamknięta droga leśna · grubość: atrakcyjność</span></div>`;
  el.querySelectorAll<HTMLInputElement>("input[data-layer]").forEach((box) =>
    box.addEventListener("change", () => {
      const id = box.dataset.layer as AccessLayerId;
      layerState[id] = box.checked;
      saveLayerState();
      map?.setLayerVisible(id, box.checked);
    }),
  );
}
function getViewModePreference(): "regions" | "stands" | null {
  try {
    const value = localStorage.getItem(VIEW_MODE_KEY);
    return value === "regions" || value === "stands" ? value : null;
  } catch {
    return null;
  }
}
function setViewModePreference(mode: "regions" | "stands") {
  try {
    localStorage.setItem(VIEW_MODE_KEY, mode);
  } catch {
    // Best-effort only -- losing the remembered mode isn't worth surfacing.
  }
}

document.querySelector<HTMLDivElement>("#app")!.innerHTML = `
  <header class="header">
    <a class="brand" href="./" aria-label="Borowik — strona główna"><span class="brand-icon">${icon("mushroom")}</span><span>Borowik<small>TWÓJ KIERUNEK: LAS</small></span></a>
    <nav aria-label="Główna nawigacja"><button id="explore-nav" class="nav-item active">${icon("map")}Odkrywaj</button><button id="saved-nav" class="nav-item">${icon("bookmark")}Zapisane <span id="saved-count">0</span></button></nav>
    <span class="private-label"><span class="status-dot"></span> Prywatny atlas grzybiarza</span>
  </header>
  <main>
    <section class="intro" aria-labelledby="page-title"><div><p class="eyebrow">MNIEJ SZUKANIA. WIĘCEJ LASU.</p><h1 id="page-title">Wybierz swój kawałek lasu.</h1><p class="intro-copy">Obiecujące wydzielenia na prawdziwki, wybrane na podstawie siedliska i pogody.</p></div><div class="trip-date">${icon("calendar")}<div><small>DATA ANALIZY</small><strong id="analysis-date">Wczytywanie…</strong></div></div></section>
    <section id="conditions" class="conditions" aria-live="polite"><span class="condition-symbol">${icon("leaf")}</span><div class="cond-main"><strong>Sprawdzamy warunki w obszarze</strong><p>Wczytujemy przygotowaną analizę lasu.</p></div></section>
    <div id="wfs-banner" class="data-banner" role="note" hidden></div>
    <section id="trips-bar" class="trips-bar" aria-label="Zapisane mapy"><label for="trips-select">${icon("bookmark")}<span>Zapisane mapy</span></label><select id="trips-select"><option value="">Aktualna</option></select></section>
    <section id="workspace" class="workspace" data-pane="list" aria-label="Wydzielenia poszukiwań">
      <div class="mobile-tabs" role="tablist" aria-label="Widok"><button role="tab" data-pane="list" class="mobile-tab active">${icon("list")}Lista</button><button role="tab" data-pane="map" class="mobile-tab">${icon("map")}Mapa</button></div>
      <aside class="sidebar"><div id="panel-heading" class="panel-heading"></div><div id="pressure-switch" class="pressure-switch"></div><div id="view-toggle" class="view-toggle" hidden><button data-view="regions" class="view-toggle-btn">Rejony</button><button data-view="stands" class="view-toggle-btn">Wydzielenia</button></div><div id="cards" class="cards" aria-live="polite"><div class="empty"><span class="loading-ring"></span><h2>Jeszcze chwila…</h2><p>Wczytujemy oceny i granice wydzieleń.</p></div></div><div class="panel-footer">${icon("info")} Model ekspercki, nieskalibrowany. Ranking porównuje miejsca w tej analizie, nie jest prawdopodobieństwem znalezienia grzybów.</div></aside>
      <div class="map-area"><div class="map-stage"><div id="map" aria-label="Mapa wydzieleń poszukiwań"></div><div class="map-heading"><span class="status-dot"></span><span id="map-title">Mapa poszukiwań</span></div><button id="fit-map" class="map-fit" aria-label="Pokaż cały obszar">${icon("target")}</button><div id="map-status" class="map-status" role="status" hidden></div></div><div class="map-legend"><div id="color-modes" class="color-modes"></div><div id="layer-controls" class="layer-controls" role="group" aria-label="Warstwy dostępu" hidden></div><span id="legend-content"><i class="legend-swatch"></i> Obiecujące wydzielenia <span class="legend-divider"></span><i class="legend-point"></i> Punkt orientacyjny</span><span class="map-caption">Granice lasu, nie gwarancja zbioru.</span></div></div>
    </section>
    <footer class="footer"><span>Borowik <span class="footer-dot">·</span> Dobry spacer zaczyna się od dobrego planu.</span><button id="about">O danych i ograniczeniach ${icon("info")}</button></footer>
  </main>
  <div id="toast" class="toast" role="status" hidden></div>
  <dialog id="about-dialog"><button class="dialog-close" aria-label="Zamknij">${icon("close")}</button><p class="eyebrow">WARTO WIEDZIEĆ</p><h2>Mapa pomaga wybrać las.</h2><p>Model ekspercki porównuje siedliska i warunki pogodowe. Nie został skalibrowany obserwacjami terenowymi i nie przewiduje pewnego zbioru.</p><ul><li>Punkty na mapie to środki wydzieleń, a nie współrzędne parkingów lub wejść.</li><li>Odległość dotyczy dojścia od wejścia albo oszacowania od najbliższej drogi lub parkingu. Nie jest długością dojazdu samochodem.</li><li>Data analizy jest etykietą eksportu. Brakuje osobnych dat pobrania warstw; pogoda pochodzi z okna przy uruchomieniu analizy.</li><li>Maska wyklucza część niedostępnych terenów. Okresowe zakazy są sprawdzane tylko dla najlepszych kandydatów, nie wszystkich wydzieleń.</li><li>Zapis zachowuje tekst i współrzędne w tej przeglądarce. Ponowne uruchomienie strony i podkład mapy wymagają połączenia; pełny tryb offline nie jest jeszcze dostępny.</li></ul><p class="source-links">Źródła: <a href="https://www.bdl.lasy.gov.pl/" target="_blank" rel="noopener noreferrer">Bank Danych o Lasach</a>, <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a>, <a href="https://danepubliczne.imgw.pl/" target="_blank" rel="noopener noreferrer">IMGW-PIB (radar RainGRS, dane przetworzone)</a>, GDOŚ, <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>. Podkład: <a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap</a>.</p></dialog>
`;
const $ = <T extends HTMLElement = HTMLElement>(selector: string) =>
  document.querySelector<T>(selector)!;
function notify(message: string) {
  clearTimeout(noticeTimer);
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  noticeTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 4500);
}
function getSaved() {
  try {
    return readSaved(localStorage);
  } catch {
    return [];
  }
}
function updateSavedCount() {
  $("#saved-count").textContent = String(getSaved().length);
}
function renderTripsPanel() {
  const options = [
    `<option value="">Aktualna</option>`,
    ...savedTrips.map(
      (t) => `<option value="${escape(t.id)}">${escape(formatTripLabel(t))}</option>`,
    ),
  ];
  $("#trips-select").innerHTML = options.join("");
  ($("#trips-select") as HTMLSelectElement).value = currentTripId ?? "";
}
function setMapStatus(message: string) {
  $("#map-status").textContent = message;
  $("#map-status").hidden = !message;
}
function detailFor(standId: string): StandDetail | undefined {
  return detailsById.get(standId);
}

// ---- Wspolne klocki karty ----

// Uzasadnienie wyniku: przy wylaczonej presji wiersz o presji jest pomijany (nie wchodzi do wyniku).
function visibleExplanations(score?: Score) {
  return (score?.explanation ?? []).filter((e) => pressure || e.factor !== "pressure_factor");
}
function explanations(score?: Score, full = false) {
  const list = visibleExplanations(score);
  const entries = full ? list : topExplanations(list);
  return entries.length
    ? `<ul class="reasons">${entries.map((e) => `<li><span class="reason-mark ${e.contribution < 0 ? "negative" : ""}">${e.contribution < 0 ? "−" : "+"}</span><span>${escape(e.text)}</span></li>`).join("")}</ul>`
    : '<p class="muted">Brak uzasadnienia w eksporcie.</p>';
}
function confidence(score?: Score) {
  return `<p>Pewność: <strong>${confidenceLabel(score?.confidence)}</strong></p><ul class="confidence-reasons">${score?.confidence_reasons.length ? score.confidence_reasons.map((r) => `<li>${escape(r)}</li>`).join("") : "<li>Brak szczegółowych powodów w eksporcie.</li>"}</ul>`;
}
// Male paski (wiersz listy): trzy cienkie kreski, wypelnienie = wartosc modelu 0-1.
function miniBars(score: Score) {
  return `<span class="mini-bars" aria-hidden="true">${scoreBars(score, pressure)
    .map(
      (b) =>
        `<i class="mini-${b.key}${b.muted ? " muted" : ""}" style="--v:${b.value === null || b.muted ? 0 : Math.round(b.value * 100)}%"></i>`,
    )
    .join("")}</span>`;
}
function rows(list: ComponentRow[]) {
  return list.length
    ? `<ul class="bar-components">${list
        .map(
          (r) =>
            `<li><span>${escape(r.label)}${r.note ? ` <em>${escape(r.note)}</em>` : ""}</span><b>${escape(r.value)}</b></li>`,
        )
        .join("")}</ul>`
    : "";
}
function barHtml(bar: Bar, extra: string, hint: string) {
  const width = bar.value === null || bar.muted ? 0 : Math.round(Math.max(0, Math.min(1, bar.value)) * 100);
  const exact = bar.muted ? "nie uwzględniony w wyniku" : `wartość modelu ${formatValue(bar.value)}`;
  return `<details class="bar bar-${bar.key}${bar.muted ? " is-muted" : ""}"><summary title="${escape(`${bar.label}: ${exact}`)}"><span class="bar-label">${bar.label}</span><span class="bar-track"><i style="width:${width}%"></i></span><span class="bar-word">${escape(bar.word)}</span></summary><div class="bar-body"><p class="bar-value">${escape(bar.label)}: ${escape(exact)}${hint ? ` · ${escape(hint)}` : ""}</p>${extra}</div></details>`;
}
// Trzy glowne paski w konwencji "wiecej = lepiej", rozwijane do skladnikow (Faza UI.2).
function barsSection(score: Score, options: { top?: boolean } = {}) {
  const detail = detailFor(score.stand_id);
  const bars = scoreBars(score, pressure);
  const weather = detail?.weather;
  const weatherLines = weather ? weatherCardLines(weather) : [];
  const habitat = habitatComponents(detail?.habitat);
  const calmRows = pressureTop(detail?.access);
  const calmExtra = detail?.access
    ? `${rows(calmRows)}<p class="muted">${escape(topPointSummary(detail.access))}</p>`
    : '<p class="muted">Rozbicie presji na punkty dostępu niedostępne w tej analizie.</p>';
  const extras: Record<string, string> = {
    habitat: habitat.length
      ? rows(habitat)
      : '<p class="muted">Składniki siedliska niedostępne w tej analizie.</p>',
    weather:
      rows(weatherComponents(weather)) +
      (weatherLines.length
        ? `<ul class="weather-lines">${weatherLines.map((l) => `<li>${escape(l)}</li>`).join("")}</ul>`
        : '<p class="muted">Składniki pogody niedostępne w tej analizie.</p>'),
    calm: pressure
      ? calmExtra
      : '<p class="muted">Presja grzybiarzy jest wyłączona — nie wpływa na ranking, listę rejonów ani kolory mapy.</p>',
  };
  const hints: Record<string, string> = {
    habitat: options.top ? "wartości najlepszego wydzielenia" : "H",
    weather: options.top ? "wartości najlepszego wydzielenia" : "lokalna pogoda F_loc",
    calm: "1 − P",
  };
  return `<div class="bars" aria-label="Rozbicie wyniku">${bars.map((b) => barHtml(b, extras[b.key], hints[b.key])).join("")}<p class="formula">Wynik = siedlisko × pogoda × spokój${pressure ? "" : " (spokój pominięty)"}</p></div>`;
}
function factChips(facts: string[]) {
  return facts.length
    ? `<ul class="facts">${facts.map((f) => `<li>${escape(f)}</li>`).join("")}</ul>`
    : "";
}
function scoreBadge(value: number) {
  return `<span class="score-badge" title="Wynik rankingowy ${value.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}${pressure ? "" : " (bez presji grzybiarzy)"}"><b>${Math.round(value)}</b><small>wynik</small></span>`;
}

// ---- Szczegoly (zwiniete): wszystko, co dotychczas bylo na karcie i w widoku szczegolow ----

function access(score?: Score) {
  // Faza 3.5: przy modelu punktow dostepu karta podaje odleglosci do
  // parkingu/wjazdu/utwardzonego duktu i element o najwiekszym wplywie na P.
  const accessCard = score ? detailFor(score.stand_id)?.access : null;
  if (accessCard)
    return `<div class="access"><div>${icon("location")}<span>Dostęp: <strong>${escape(accessCardSummary(accessCard))}</strong></span></div><small>${distanceMethod(score?.distance_method)}</small><p>${escape(topPointSummary(accessCard))}</p></div>`;
  return `<div class="access"><div>${icon("location")}<span>Orientacyjne dojście <strong>${distanceLabel(score?.d_park_m)}</strong></span></div><small>${distanceMethod(score?.distance_method)}</small><p>${entranceLabel(score?.entrance_status)} · brak współrzędnych wejścia w danych.</p></div>`;
}
// Faza 3.5: karta rejonu pokazuje dostep dla WSZYSTKICH wydzielen rejonu (zakres i
// mediana), a nie odleglosc jednego, najlepiej ocenionego wydzielenia.
function regionAccess(view: RegionView, score?: Score) {
  const cards = view.members
    .map((m) => detailFor(m.score.stand_id)?.access)
    .filter((c): c is AccessCard => !!c);
  const summary = regionAccessSummary(cards);
  if (!summary) return access(score);
  return `<div class="access"><div>${icon("location")}<span>Dostęp w rejonie: <strong>${escape(summary.distances)}</strong></span></div><small>${distanceMethod(score?.distance_method)} · zakres po ${cards.length} wydzieleniach rejonu</small><p>${escape(summary.top)}</p></div>`;
}
// Plan 2.1 step B3 (spec §5.3 pkt 3): species composition, density, podszyt,
// soil type -- from a BDL package, empty/null when the wydzielenie has no
// package coverage. Presentation only, no effect on R/H/F -- see
// pipeline.bdl_package_details' module docstring and the regression test in
// tests/test_prepare_trip.py on the Python side.
function speciesList(items: SpeciesShare[]) {
  // Real-data finding (Będziemyśl verification): podszyt (understory) rows
  // commonly have no recorded share at all -- an empty parenthetical would
  // be confusing, so it's only shown when there is one.
  return items.length
    ? `<ul class="species-list">${items.map((s) => `<li>${escape(s.name)}${s.share ? ` <span class="muted">(${escape(s.share)})</span>` : ""}</li>`).join("")}</ul>`
    : '<p class="muted">Brak danych.</p>';
}
function packageSection(detail?: StandDetail) {
  if (!detail || !detail.drzew_species.length)
    return '<p class="muted">Skład gatunkowy, zwarcie, podszyt i typ gleby: brak paczki BDL dla tego wydzielenia.</p>';
  return `<div class="package-detail">${detail.searchability_hint ? `<p class="searchability-hint">${escape(detail.searchability_hint)}</p>` : ""}<p><strong>Skład gatunkowy (warstwa drzew)</strong></p>${speciesList(detail.drzew_species)}<p><strong>Zwarcie</strong> ${escape(densityLabel(detail.density))}</p><p><strong>Pokrycie gleby</strong> ${detail.veg_cover ? escape(detail.veg_cover) : "brak danych"}</p><p><strong>Zadrzewienie</strong> ${finite(detail.standdensity_index) ? `${detail.standdensity_index!.toFixed(1)} (skala ok. 0–2, 1,0 = pełne)` : "brak danych"}</p><p><strong>Podszyt</strong></p>${speciesList(detail.podszyt_species)}<p><strong>Typ gleby</strong> ${detail.soil_type ? escape(detail.soil_type) : "brak danych"}</p>${detail.package_date ? `<p class="muted">Dane paczki BDL z dnia ${escape(detail.package_date)}.</p>` : ""}</div>`;
}
function neighborsSection(detail?: StandDetail) {
  const summary = neighborsSummary(detail?.neighbors);
  if (summary !== null || !detail) return `<p class="muted">Graniczy z: ${escape(summary ?? "")}.</p>`;
  return `<p><strong>Graniczy z</strong></p><ul class="neighbors-list">${detail.neighbors.map((n) => `<li>${escape(n)}</li>`).join("")}</ul>`;
}
function structureSection(detail?: StandDetail) {
  if (!detail || (!detail.stand_stru && !detail.prot_categ)) return "";
  return `<dl class="metrics">${detail.stand_stru ? `<div><dt>Budowa drzewostanu</dt><dd>${escape(standStructureLabel(detail.stand_stru))}</dd></div>` : ""}${detail.prot_categ ? `<div><dt>Kategoria ochronności</dt><dd>${escape(detail.prot_categ)}</dd></div>` : ""}</dl>`;
}
function formulaText() {
  return `R = 100 · H · F_loc · (1 − α·P)${pressureAlpha === null ? "" : `, α = ${pressureAlpha.toLocaleString("pl-PL")}`}`;
}
function scoreDetails(score: Score, opts: { rankLine: string; point: [number, number] }) {
  const detail = detailFor(score.stand_id);
  const w = detail?.weather;
  const r = pressure ? score.R : score.R_bez_presji;
  const bothScores = `<div><dt>Wynik z presją (R)</dt><dd>${finite(score.R) ? score.R.toFixed(1) : "—"}</dd></div>${finite(score.R_bez_presji) ? `<div><dt>Wynik bez presji</dt><dd>${score.R_bez_presji.toFixed(1)}</dd></div>` : ""}`;
  return `<div class="details-block"><h4>Wynik i model</h4><p class="muted">${escape(opts.rankLine)}</p><dl class="metrics">${bothScores}<div><dt>Siedlisko H</dt><dd>${formatValue(score.H)} · ${habitatClass(score.H).toLocaleLowerCase("pl")}</dd></div><div><dt>Pogoda lokalna F_loc</dt><dd>${formatValue(score.F_loc)} · ${fruitingClass(score.F_loc).toLocaleLowerCase("pl")}</dd></div><div><dt>Warunki regionalne F</dt><dd>${formatValue(score.F)} · ${fruitingClass(score.F).toLocaleLowerCase("pl")}</dd></div><div><dt>Presja P (spokój = 1 − P)</dt><dd>${finite(score.P) ? score.P.toFixed(2) : "—"}</dd></div></dl><p class="muted">${escape(formulaText())}. Bez presji: 100 · H · F_loc. Wartość ${pressure ? "z" : "bez"} presji: ${finite(r) ? r!.toFixed(1) : "—"}. Pasek „Spokój” pokazuje 1 − P; do wyniku presja wchodzi z wagą α. P jest wskaźnikiem modelu, nie pomiarem tłoku; brak danych o wejściach może go zawyżać. Model nieskalibrowany na danych terenowych.</p></div>
    <div class="details-block"><h4>Dlaczego tutaj</h4>${explanations(score, true)}</div>
    <div class="details-block"><h4>Pewność oceny</h4>${confidence(score)}</div>
    ${w ? `<div class="details-block"><h4>Pogoda w tym miejscu</h4><p class="weather-disclaimer">${escape(WEATHER_DISCLAIMER)}</p></div>` : ""}
    <div class="details-block"><h4>Dostęp i punkt orientacyjny</h4>${access(score)}<div class="point-note">Punkt orientacyjny: ${escape(coordinates(opts.point))}.<br>Dojazd samochodem: brak danych.</div></div>
    <div class="details-block"><h4>Drzewostan i otoczenie</h4>${packageSection(detail)}${structureSection(detail)}${neighborsSection(detail)}</div>
    <div class="details-block data-note"><strong>Zakres danych</strong><p>${score.mask ? "Wydzielenie przeszło filtry modelu. Nie jest to potwierdzenie pełnej dostępności prawnej." : "Wydzielenie wykluczone przez filtr modelu."}</p><p>Analiza: ${formatDate(score.day)}.<br>Daty pobrania poszczególnych źródeł: brak danych.</p><p>Zakazy wstępu do lasu są sprawdzane na dzień przygotowania analizy, nie na dzień wyjazdu.${zakazNote(score.zakaz_status) ? ` ${zakazNote(score.zakaz_status)}` : ""}</p></div>`;
}

// ---- Wiersz listy i karty ----

function rowHtml(o: {
  attr: string;
  selectAttr: string;
  id: string;
  rank: number;
  name: string;
  meta: string;
  value: number;
  score: Score;
  selected: boolean;
  body: string;
  eyebrow?: string;
}) {
  return `<article class="row ${o.selected ? "selected" : ""}" ${o.attr}="${escape(o.id)}"><button class="row-main" ${o.selectAttr}="${escape(o.id)}" aria-pressed="${o.selected}" aria-label="${escape(`${o.rank}. ${o.name}, wynik ${Math.round(o.value)}`)}"><span class="region-number">${String(o.rank).padStart(2, "0")}</span><span class="row-text"><strong class="row-name">${escape(o.name)}</strong><small class="row-meta">${escape(o.meta)}</small></span>${miniBars(o.score)}${scoreBadge(o.value)}</button>${o.body}</article>`;
}
function metaLine(parts: (string | null)[]) {
  return parts.filter((p): p is string => !!p).join(" · ");
}
function actions(o: { saveAttr: string; id: string; saved: boolean; saveLabel: string; navPoint: [number, number]; navLabel: string }) {
  return `<div class="card-actions"><button class="save-button ${o.saved ? "is-saved" : ""}" ${o.saveAttr}="${escape(o.id)}">${icon(o.saved ? "check" : "bookmark")}${o.saved ? "Zapisano" : o.saveLabel}</button><a class="navigation-link" href="${navigationUrl(o.navPoint)}" target="_blank" rel="noopener noreferrer" aria-label="${escape(o.navLabel)}">${icon("location")}Nawiguj</a><button class="show-on-map" data-show-map="1">${icon("map")}Na mapie</button></div>`;
}
// Adres lesny po polsku: nadlesnictwo (kod), lesnictwo, oddzial, pododdzial.
function addressLine(standId: string) {
  const parsed = parseStandId(standId);
  if (!parsed) return "";
  const detail = detailFor(standId);
  const name = standName(standId, detail).split(" · ")[1] ?? "";
  return `<p class="muted">${escape(name)} (kod ${escape(parsed.district)}) · leśnictwo nr ${escape(parsed.forestry)} · oddział ${escape(parsed.section)} · pododdział ${escape(parsed.subsection)}</p>`;
}
function standRow(entry: StandView, index: number) {
  const score = entry.score;
  const detail = detailFor(score.stand_id);
  const isSelected = selected === score.stand_id;
  const name = standName(score.stand_id, detail);
  const meta = metaLine([areaLabel(score.area_ha), startDistanceLabel(startPoint, entry.point)]);
  let body = "";
  if (isSelected) {
    const isSaved = getSaved().some((s) => s.key === savedKey(score.stand_id, entry.point));
    const rank = `Miejsce ${index + 1} w rankingu${pressure ? "" : " bez presji"}: wynik ${entry.r.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}.`;
    body = `<div class="card-body">${barsSection(score)}${factChips(keyFacts(detail?.access, score.area_ha, score.d_park_m))}${actions({ saveAttr: "data-save", id: score.stand_id, saved: isSaved, saveLabel: "Zapisz miejsce", navPoint: entry.point, navLabel: `Nawiguj do punktu orientacyjnego wydzielenia ${name}` })}<details class="card-details"><summary>Szczegóły</summary><div class="details-inner"><div class="details-block"><h4>Identyfikator</h4><p class="stand-id">${escape(score.stand_id)}</p>${addressLine(score.stand_id)}</div>${scoreDetails(score, { rankLine: rank, point: entry.point })}</div></details><div class="freshness">Analiza: ${formatDate(score.day)}</div></div>`;
  }
  return rowHtml({
    attr: "data-card",
    selectAttr: "data-select",
    id: score.stand_id,
    rank: index + 1,
    name,
    meta,
    value: entry.r,
    score,
    selected: isSelected,
    body,
  });
}
function regionPoint(view: RegionView): [number, number] {
  return [view.region.centroid_lon, view.region.centroid_lat];
}
function regionTitle(view: RegionView) {
  return regionName(view.region, regionViews.indexOf(view) + 1);
}
function regionRow(view: RegionView, index: number) {
  const isSelected = selectedRegionId === view.region.region_id;
  const point = regionPoint(view);
  const score = view.top.score;
  const name = regionName(view.region, index + 1);
  const totalArea = view.members.reduce((sum, m) => sum + (finite(m.score.area_ha) ? m.score.area_ha : 0), 0);
  const meta = metaLine([
    `${view.members.length} wydzieleń`,
    areaLabel(totalArea > 0 ? totalArea : null),
    startDistanceLabel(startPoint, point),
  ]);
  let body = "";
  if (isSelected) {
    const isSaved = getSaved().some((s) => s.key === savedKey(view.region.region_id, point));
    const topAccess = detailFor(score.stand_id)?.access;
    const facts = [`${view.members.length} wydzieleń`, ...keyFacts(topAccess, totalArea > 0 ? totalArea : null, score.d_park_m)].slice(0, 4);
    const place = view.region.near_place
      ? `<div class="details-block"><h4>Położenie</h4><p>Najbliższa miejscowość: ${escape(view.region.near_place.name)}, ${distanceLabel(view.region.near_place.distance_m)} od środka rejonu.</p></div>`
      : "";
    const rankLine = `Ranking rejonu: ${view.region.rank_score.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}${pressure ? "" : " (bez presji grzybiarzy)"} — mediana wyniku najlepszych wydzieleń rejonu. Paski i wartości poniżej dotyczą najlepiej ocenionego wydzielenia w rejonie (${escape(standName(score.stand_id, detailFor(score.stand_id)))}).`;
    body = `<div class="card-body">${barsSection(score, { top: true })}${factChips(facts)}${actions({ saveAttr: "data-region-save", id: view.region.region_id, saved: isSaved, saveLabel: "Zapisz rejon", navPoint: point, navLabel: `Nawiguj do punktu orientacyjnego rejonu ${name}` })}<button class="detail-button" data-region-detail="${escape(view.region.region_id)}">Zobacz wydzielenia w rejonie (${view.members.length}) ${icon("arrow")}</button><details class="card-details"><summary>Szczegóły</summary><div class="details-inner"><div class="details-block"><h4>Identyfikator</h4><p class="stand-id">${escape(view.region.region_id)}</p><p class="muted">Środek: ${escape(coordinates(point))}. Wydzielenie najlepsze w rejonie: ${escape(score.stand_id)}.</p></div>${place}${scoreDetails(score, { rankLine, point })}<div class="details-block"><h4>Dostęp w całym rejonie</h4>${regionAccess(view, score)}</div></div></details><div class="freshness">Analiza: ${formatDate(view.region.day)}</div></div>`;
  }
  return rowHtml({
    attr: "data-region-card",
    selectAttr: "data-region-select",
    id: view.region.region_id,
    rank: index + 1,
    name,
    meta,
    value: view.region.rank_score,
    score,
    selected: isSelected,
    body,
  });
}

// ---- Przelacznik presji (Faza UI.1) ----

function renderPressureSwitch() {
  const el = $("#pressure-switch");
  el.hidden = !loaded || savedOnly;
  if (el.hidden) return;
  const hint = !pressureAvailable
    ? "Niedostępne w tej migawce — starszy eksport nie ma wyników bez presji."
    : pressure
      ? "Ranking uwzględnia dojazd i to, ilu innych grzybiarzy można spotkać."
      : "Ranking tylko z siedliska i pogody — bez wpływu presji.";
  el.innerHTML = `<label class="switch-row${pressureAvailable ? "" : " is-disabled"}"><span class="switch-text"><strong>Uwzględniaj presję grzybiarzy</strong><small>${escape(hint)}</small></span><input type="checkbox" id="pressure-toggle" role="switch" ${pressure ? "checked" : ""} ${pressureAvailable ? "" : "disabled"}><span class="switch-track" aria-hidden="true"><i></i></span></label>`;
}
function applyPressure(on: boolean, options: { remember: boolean }) {
  const next = on && pressureAvailable;
  if (options.remember) setPressurePreference(on);
  if (next === pressure && entries.length) {
    renderPressureSwitch();
    return;
  }
  pressure = next;
  entries = pressure ? baseEntries : rankEntries(baseEntries, false);
  const regionSource = pressure ? regionsWithPressure : (regionsWithoutPressure ?? []);
  regionViews = joinRegions(regionSource, entries);
  page = 0;
  regionFilterId = null;
  map?.setData(entries, false);
  if (!entries.some((e) => e.score.stand_id === selected)) selected = entries[0]?.score.stand_id ?? "";
  selectedRegionId = regionViews[0]?.region.region_id ?? "";
  if (viewMode === "regions" && !regionViews.length && entries.length) viewMode = "stands";
  if (viewMode === "regions" && regionViews.length) {
    renderPanel();
    selectRegionCard(selectedRegionId);
  } else {
    renderPanel();
    map?.select(selected);
    map?.focusStand(selected);
  }
}

function renderRegionsPanel() {
  $("#panel-heading").innerHTML =
    `<div><h2>Rejony <span class="count-pill">${regionViews.length}</span></h2><p>Grupy sąsiadujących wydzieleń · po filtrach modelu</p></div><span class="sort-label">Najlepsze najpierw ↓</span>`;
  $("#cards").innerHTML = regionViews.length
    ? regionViews.map((view, i) => regionRow(view, i)).join("")
    : `<div class="empty"><span class="empty-icon">${icon("leaf")}</span><h2>Brak rejonów w tej analizie</h2><p>Żadna grupa wydzieleń nie spełniła kryteriów grupowania. Zobacz widok „Wydzielenia” albo przygotuj nową analizę bliżej wyjazdu.</p></div>`;
  $("#map-title").textContent =
    `${regionViews.length} rejonów · przygotowany obszar`;
  updateLegend();
}
function updateLegend() {
  if (colorMode === "moisture") {
    const gradient = MOISTURE_STOPS.map(([v, c]) => `${c} ${Math.round(v * 100)}%`).join(", ");
    $("#legend-content").innerHTML = `<span class="moisture-legend"><span class="moisture-bar" style="background:linear-gradient(90deg, ${gradient})"></span><span class="moisture-ticks">${MOISTURE_LEGEND_TICKS.map((v) => `<i>${moistureTickLabel(v)}</i>`).join("")}</span></span><span class="moisture-note">Wilgotność M: sucho → wilgotno (skala bezwzględna 0–1). ${escape(MOISTURE_NOTE)} Wydzielenia poza maską modelu — jaśniej.</span>`;
    return;
  }
  $("#legend-content").innerHTML = `<span class="gradient-legend"></span> Niższy → wyższy ranking${pressure ? "" : " bez presji grzybiarzy"} (skala wg rozkładu ocen w tej analizie)`;
}
// Trzy przyciski kolorowania mapy obok legendy (a: wynik, b: wynik bez presji, c: wilgotność).
function renderColorModes() {
  const modes: { id: MapColorMode; label: string; ok: boolean; why: string }[] = [
    { id: "score", label: "Wynik", ok: true, why: "" },
    {
      id: "score_no_pressure",
      label: "Wynik bez presji",
      ok: pressureAvailable,
      why: "Wynik bez presji: niedostępny w tej migawce (starszy eksport).",
    },
    {
      id: "moisture",
      label: "Wilgotność",
      ok: moistureOk,
      why: "Wilgotność: niedostępna w tej migawce (starszy eksport bez składowej M).",
    },
  ];
  const hints = modes.filter((m) => !m.ok).map((m) => m.why);
  $("#color-modes").innerHTML = `<div class="color-mode-group" role="group" aria-label="Kolor mapy">${modes
    .map(
      (m) =>
        `<button class="color-mode${colorMode === m.id ? " active" : ""}" data-color-mode="${m.id}" aria-pressed="${colorMode === m.id}" ${m.ok ? "" : "disabled"} ${m.ok ? "" : `title="${escape(m.why)}"`}>${m.label}</button>`,
    )
    .join("")}</div>${hints.length ? `<p class="color-mode-hint">${escape(hints.join(" "))}</p>` : ""}`;
}
// Jedno miejsce zmiany kolorowania mapy i presji, zeby przelacznik i przyciski nie byly sprzeczne.
function setColorControls(next: { pressure: boolean; colorMode: MapColorMode }) {
  const pressureChanged = next.pressure !== pressure;
  colorMode = next.colorMode;
  setColorModePreference(colorMode);
  if (pressureChanged) applyPressure(next.pressure, { remember: true });
  map?.setColorMode(colorMode);
  renderColorModes();
  renderPressureSwitch();
  updateLegend();
}
function visibleEntries(): StandView[] {
  // Plan 2.1 step A4: sub-0.5ha stands are hidden as standalone targets in
  // the flat "Wydzielenia" list, but NOT when browsing a region's own
  // members (regionFilterId set) -- they still count toward that region's
  // area (pipeline/regions.py, A2) and a user drilling into a region should
  // see every stand that actually makes it up.
  if (!regionFilterId)
    return entries.filter((e) => isStandaloneTarget(e.score));
  const view = regionViews.find((v) => v.region.region_id === regionFilterId);
  if (!view) return entries.filter((e) => isStandaloneTarget(e.score));
  const memberIds = new Set(view.members.map((m) => m.score.stand_id));
  return entries.filter((e) => memberIds.has(e.score.stand_id));
}
function updateViewToggle() {
  const toggle = $("#view-toggle");
  toggle.hidden = savedOnly || !loaded;
  const regionsBtn = document.querySelector<HTMLButtonElement>(
    '[data-view="regions"]',
  )!;
  const standsBtn = document.querySelector<HTMLButtonElement>(
    '[data-view="stands"]',
  )!;
  regionsBtn.disabled = regionViews.length === 0;
  regionsBtn.classList.toggle(
    "active",
    viewMode === "regions" && !regionFilterId,
  );
  standsBtn.classList.toggle(
    "active",
    viewMode === "stands" || !!regionFilterId,
  );
}
function renderPanel() {
  updateSavedCount();
  $("#explore-nav").classList.toggle("active", !savedOnly);
  $("#saved-nav").classList.toggle("active", savedOnly);
  updateViewToggle();
  renderPressureSwitch();
  if (savedOnly) {
    renderSaved();
    return;
  }
  if (!loaded) {
    $("#panel-heading").innerHTML = "<h2>Wydzielenia poszukiwań</h2>";
    if (loadError)
      $("#cards").innerHTML =
        `<div class="empty"><span class="empty-icon">${icon("map")}</span><h2>Nie udało się wczytać analizy</h2><p>${escape(loadError)}</p><button class="primary" id="retry">Spróbuj ponownie</button><p>Zapisane miejsca znajdziesz w zakładce „Zapisane”.</p></div>`;
    return;
  }
  if (viewMode === "regions" && !regionFilterId) {
    renderRegionsPanel();
    scrollSelectedIntoView();
    return;
  }
  const visible = visibleEntries();
  const filterView = regionFilterId
    ? regionViews.find((v) => v.region.region_id === regionFilterId)
    : undefined;
  $("#panel-heading").innerHTML = filterView
    ? `<div><button class="back-button" id="back-to-regions">← Wróć do rejonów</button><h2>${escape(regionTitle(filterView))} <span class="count-pill">${visible.length}</span></h2><p>Wydzielenia należące do tego rejonu</p></div>`
    : `<div><h2>Wydzielenia <span class="count-pill">${visible.length}</span></h2><p>Każde ocenione osobno · po filtrach modelu</p></div><span class="sort-label">Najlepsze najpierw ↓</span>`;
  $("#cards").innerHTML = visible.length
    ? visible
        .slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
        .map((entry, i) => standRow(entry, page * PAGE_SIZE + i))
        .join("") +
      `<div class="pagination"><button id="previous-page" ${page === 0 ? "disabled" : ""}>← Poprzednie</button><span>${page + 1} / ${Math.ceil(visible.length / PAGE_SIZE)}</span><button id="next-page" ${(page + 1) * PAGE_SIZE >= visible.length ? "disabled" : ""}>Następne →</button></div>`
    : '<div class="empty"><span class="empty-icon">' +
      icon("leaf") +
      "</span><h2>Brak propozycji w tej analizie</h2><p>Żadne wydzielenie nie spełniło kryteriów. Sprawdź inny obszar lub przygotuj nową analizę bliżej wyjazdu.</p></div>";
  $("#map-title").textContent = filterView
    ? `${regionTitle(filterView)} · ${visible.length} wydzieleń`
    : `${visible.length} wydzieleń · przygotowany obszar`;
  updateLegend();
  scrollSelectedIntoView();
}
function scrollSelectedIntoView() {
  const el = document.querySelector<HTMLElement>("#cards .row.selected");
  el?.scrollIntoView({ block: "nearest" });
}
function renderSaved() {
  const saved = getSaved();
  $("#panel-heading").innerHTML =
    `<div><h2>Zapisane miejsca <span class="count-pill">${saved.length}</span></h2><p>Twoje miejsca, w tej przeglądarce</p></div>`;
  $("#cards").innerHTML = saved.length
    ? `<p class="saved-notice">Zachowane opisy i współrzędne. Podkład mapy i ponowne otwarcie strony wymagają połączenia.</p>${saved.map((item) => `<article class="saved-card"><p class="eyebrow">${escape(formatDate(item.day))}</p><h3>${escape(item.title)}</h3><span class="badge">${escape(item.conditions)}</span><p class="coordinate-line">${coordinates(item.point)}</p><p class="muted">Punkt orientacyjny w lesie, nie potwierdzone wejście.</p><ul class="saved-reasons">${item.reasons.map((reason) => `<li>${escape(reason)}</li>`).join("")}</ul><div class="card-actions"><a class="navigation-link" href="${navigationUrl(item.point)}" target="_blank" rel="noopener noreferrer">${icon("location")}Nawiguj</a><button data-remove="${escape(item.key)}">Usuń zapis</button></div></article>`).join("")}`
    : `<div class="empty"><span class="empty-icon">${icon("bookmark")}</span><h2>Las jeszcze przed Tobą.</h2><p>Zapisz miejsce, aby zachować jego współrzędne i uzasadnienie na później.</p><button id="show-explore" class="primary">Przeglądaj wydzielenia</button></div>`;
}
function selectStand(id: string, focus = true) {
  selected = id;
  page = Math.max(
    0,
    Math.floor(
      visibleEntries().findIndex((e) => e.score.stand_id === id) / PAGE_SIZE,
    ),
  );
  savedOnly = false;
  renderPanel();
  map?.select(id);
  if (focus) map?.focusStand(id);
}
function selectRegionCard(id: string, focus = true) {
  selectedRegionId = id;
  savedOnly = false;
  viewMode = "regions";
  regionFilterId = null;
  renderPanel();
  const view = regionViews.find((v) => v.region.region_id === id);
  if (!view) return;
  const memberIds = view.members.map((m) => m.score.stand_id);
  const label = String(
    regionViews.findIndex((v) => v.region.region_id === id) + 1,
  );
  map?.selectGroup(memberIds, regionPoint(view), label);
  if (focus) map?.focusStands(memberIds);
}
function enterRegionDetail(id: string) {
  const view = regionViews.find((v) => v.region.region_id === id);
  if (!view) return;
  regionFilterId = id;
  viewMode = "stands";
  page = 0;
  selected = view.top.score.stand_id;
  renderPanel();
  const memberIds = view.members.map((m) => m.score.stand_id);
  map?.selectGroup(memberIds, regionPoint(view), "•");
  map?.focusStands(memberIds);
}
function save(id: string) {
  const entry = entries.find((r) => r.score.stand_id === id);
  if (!entry) return;
  const item: SavedRegion = {
    key: savedKey(id, entry.point),
    title: standName(entry.score.stand_id, detailFor(entry.score.stand_id)),
    point: entry.point,
    day: entry.score.day,
    conditions: fruitingClass(entry.score?.F),
    reasons: topExplanations(visibleExplanations(entry.score)).map((e) => e.text),
    savedAt: new Date().toISOString(),
  };
  try {
    saveRegion(localStorage, item);
    renderPanel();
    notify("Wydzielenie zapisane w tej przeglądarce.");
  } catch {
    notify(
      "Nie można zapisać wydzielenia. Sprawdź, czy przeglądarka pozwala na zapis danych.",
    );
  }
}
function saveRegionCard(id: string) {
  const view = regionViews.find((v) => v.region.region_id === id);
  if (!view) return;
  const point = regionPoint(view);
  const item: SavedRegion = {
    key: savedKey(id, point),
    title: regionTitle(view),
    point,
    day: view.region.day,
    conditions: fruitingClass(view.top.score?.F),
    reasons: topExplanations(visibleExplanations(view.top.score)).map(
      (e) => e.text,
    ),
    savedAt: new Date().toISOString(),
  };
  try {
    saveRegion(localStorage, item);
    renderPanel();
    notify("Rejon zapisany w tej przeglądarce.");
  } catch {
    notify(
      "Nie można zapisać rejonu. Sprawdź, czy przeglądarka pozwala na zapis danych.",
    );
  }
}
function switchView(mode: "regions" | "stands") {
  viewMode = mode;
  regionFilterId = null;
  page = 0;
  setViewModePreference(mode);
  renderPanel();
  // Przelaczenie Rejony <-> Wydzielenia zmienia tylko liste i podswietlenie; widok mapy
  // (przyblizenie i pozycja) zostaje tam, gdzie go ustawil uzytkownik.
  if (mode === "regions") {
    if (regionViews.length) selectRegionCard(regionViews[0].region.region_id, false);
  } else if (selected) {
    // select() removes any group marker and resets the highlight filter to
    // just this stand, so switching out of region mode needs no separate
    // "clear group" call.
    map?.select(selected);
  }
}
// Faza UI.4: zakladki Lista / Mapa na waskim ekranie (na szerokim sa ignorowane przez CSS).
function setPane(pane: "list" | "map") {
  mobilePane = pane;
  $("#workspace").dataset.pane = pane;
  document.querySelectorAll<HTMLElement>(".mobile-tab").forEach((tab) => {
    const active = tab.dataset.pane === pane;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  if (pane === "map")
    requestAnimationFrame(() => {
      // Mapa ukryta na zakladce "Lista" ma zerowy rozmiar -- po pokazaniu odswiez rozmiar i widok.
      map?.resize();
      const region =
        viewMode === "regions" && !regionFilterId
          ? regionViews.find((v) => v.region.region_id === selectedRegionId)
          : undefined;
      if (region) map?.focusStands(region.members.map((m) => m.score.stand_id));
      else if (selected) map?.focusStand(selected);
    });
}
const isNarrow = () => window.matchMedia("(max-width: 760px)").matches;

document.addEventListener("click", (event) => {
  const button = (event.target as Element).closest<HTMLElement>("button");
  if (!button) return;
  if (button.dataset.pane === "list" || button.dataset.pane === "map") {
    setPane(button.dataset.pane);
    return;
  }
  if (button.dataset.colorMode) {
    const next = chooseColorMode(
      { pressure, colorMode },
      button.dataset.colorMode as MapColorMode,
      { pressure: pressureAvailable, moisture: moistureOk },
    );
    if (next) setColorControls(next);
    else notify("Ten tryb kolorowania jest niedostępny w tej migawce.");
    return;
  }
  if (button.dataset.showMap) {
    setPane("map");
    return;
  }
  if (button.dataset.select) {
    selectStand(button.dataset.select);
    return;
  }
  if (button.dataset.save) {
    save(button.dataset.save);
    return;
  }
  if (button.dataset.regionSelect) {
    selectRegionCard(button.dataset.regionSelect);
    return;
  }
  if (button.dataset.regionSave) {
    saveRegionCard(button.dataset.regionSave);
    return;
  }
  if (button.dataset.regionDetail) {
    enterRegionDetail(button.dataset.regionDetail);
    return;
  }
  if (button.dataset.remove) {
    try {
      removeSaved(localStorage, button.dataset.remove);
      renderPanel();
      notify("Usunięto zapis.");
    } catch {
      notify("Nie udało się usunąć zapisu.");
    }
    return;
  }
  if (button.dataset.view === "regions" || button.dataset.view === "stands") {
    if (!(button as HTMLButtonElement).disabled) switchView(button.dataset.view);
    return;
  }
  switch (button.id) {
    case "previous-page":
    case "next-page":
      page += button.id === "next-page" ? 1 : -1;
      renderPanel();
      $("#cards").scrollTop = 0;
      if (isNarrow()) $("#workspace").scrollIntoView();
      break;
    case "back-to-regions":
      if (regionFilterId) selectRegionCard(regionFilterId);
      else switchView("regions");
      break;
    case "explore-nav":
    case "show-explore":
      savedOnly = false;
      renderPanel();
      break;
    case "saved-nav":
      savedOnly = true;
      renderPanel();
      break;
    case "fit-map": {
      const activeRegion =
        viewMode === "regions" && !regionFilterId
          ? regionViews.find((v) => v.region.region_id === selectedRegionId)
          : undefined;
      if (activeRegion)
        map?.focusStands(activeRegion.members.map((m) => m.score.stand_id));
      else map?.fitAll();
      break;
    }
    case "about":
      $("#about-dialog") instanceof HTMLDialogElement &&
        ($("#about-dialog") as HTMLDialogElement).showModal();
      break;
    case "retry":
      void initialize(currentBasePath, currentTripId);
      break;
  }
  if (button.classList.contains("dialog-close"))
    ($("#about-dialog") as HTMLDialogElement).close();
});
document.addEventListener("change", (event) => {
  const select = event.target as HTMLElement;
  if (select.id === "pressure-toggle") {
    setColorControls(
      togglePressureControls((select as HTMLInputElement).checked, { pressure: pressureAvailable }),
    );
    return;
  }
  if (select.id !== "trips-select") return;
  const value = (select as HTMLSelectElement).value;
  void initialize(value ? `data/trips/${value}/` : "data/", value || null);
});
$("#cards").addEventListener("pointerover", (event) => {
  const card = (event.target as Element).closest<HTMLElement>("[data-card]");
  if (card) {
    map?.highlight(card.dataset.card!);
    return;
  }
  const regionCard = (event.target as Element).closest<HTMLElement>(
    "[data-region-card]",
  );
  if (regionCard) {
    const view = regionViews.find(
      (v) => v.region.region_id === regionCard.dataset.regionCard,
    );
    if (view) map?.highlightGroup(view.members.map((m) => m.score.stand_id));
  }
});
$("#cards").addEventListener("pointerleave", () => {
  map?.highlight(null);
  map?.highlightGroup(null);
});
window.addEventListener("storage", () => {
  updateSavedCount();
  renderPanel();
});
let loadSeq = 0;
async function initialize(basePath: string = "data/", tripId: string | null = null) {
  currentBasePath = basePath;
  currentTripId = tripId;
  const seq = ++loadSeq;
  loaded = false;
  loadError = "";
  $("#cards").innerHTML =
    '<div class="empty"><span class="loading-ring"></span><h2>Wczytujemy analizę…</h2></div>';
  renderPanel();
  // Fetched independently of loadData below: a broken "Aktualna" (or a
  // broken saved trip) must still let the user reach a working saved trip
  // from the dropdown, not hide the whole list just because THIS load failed.
  void loadTrips().then((trips) => {
    if (seq !== loadSeq) return; // superseded by a newer switch/retry
    savedTrips = trips;
    renderTripsPanel();
  });
  try {
    const data = await loadData(basePath);
    if (seq !== loadSeq) return; // a newer switch/retry already started
    baseEntries = data.entries;
    allScores = data.scores;
    regionsWithPressure = data.regions;
    regionsWithoutPressure = data.regionsNoPressure;
    detailsById = new Map(data.details.map((d) => [d.stand_id, d]));
    startPoint = data.start;
    pressureAlpha = data.pressureAlpha;
    // Faza UI.1: bez R_bez_presji i drugiego zestawu rejonow (starsza migawka) przelacznik jest
    // nieaktywny, a ranking dziala jak dotad.
    pressureAvailable = pressureSwitchAvailable(allScores, regionsWithoutPressure);
    pressure = pressureAvailable ? getPressurePreference() : true;
    moistureOk = moistureAvailable(allScores);
    colorMode = resolveColorMode(getColorModePreference(), pressure, moistureOk);
    entries = pressure ? baseEntries : rankEntries(baseEntries, false);
    regionViews = joinRegions(
      pressure ? regionsWithPressure : (regionsWithoutPressure ?? []),
      entries,
    );
    loaded = true;
    page = 0;
    regionFilterId = null;
    selected = entries[0]?.score.stand_id ?? "";
    selectedRegionId = regionViews[0]?.region.region_id ?? "";
    viewMode =
      getViewModePreference() ?? (regionViews.length > 0 ? "regions" : "stands");
    if (viewMode === "regions" && regionViews.length === 0) viewMode = "stands";
    const day = allScores[0]?.day ?? entries[0]?.score.day;
    $("#analysis-date").textContent = day ? formatDate(day) : "Brak wyników";
    const values = allScores
      .filter((s) => s.mask && finite(s.F))
      .map((s) => s.F!)
      .sort((a, b) => a - b);
    const median = values.length
      ? (values[Math.floor((values.length - 1) / 2)] +
          values[Math.floor(values.length / 2)]) /
        2
      : null;
    $("#conditions").innerHTML = conditionsHtml(median, data.conditions);
    const wfsBanner = wfsOnlyBanner(data.wfsOnlyShare);
    $("#wfs-banner").textContent = wfsBanner ?? "";
    $("#wfs-banner").hidden = wfsBanner === null;
    if (!map) {
      try {
        map = new ForestMap(
          $("#map"),
          (id) => {
            // Tryb Wilgotnosc pokazuje tez wydzielenia poza maska modelu -- nie maja oceny ani karty.
            if (!entries.some((e) => e.score.stand_id === id)) {
              notify("To wydzielenie jest poza maską modelu — nie ma oceny ani karty.");
              return;
            }
            // Faza UI.4: dotkniecie wydzielenia na mapie (telefon) pokazuje jego karte na liscie.
            if (isNarrow()) setPane("list");
            if (viewMode === "stands" || regionFilterId) {
              selectStand(id);
              const card = Array.from(
                document.querySelectorAll<HTMLElement>("[data-card]"),
              ).find((c) => c.dataset.card === id);
              card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
              return;
            }
            const owner = regionViews.find((v) =>
              v.members.some((m) => m.score.stand_id === id),
            );
            if (!owner) return;
            selectRegionCard(owner.region.region_id, false);
            const card = Array.from(
              document.querySelectorAll<HTMLElement>("[data-region-card]"),
            ).find(
              (c) => c.dataset.regionCard === owner.region.region_id,
            );
            card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
          },
          setMapStatus,
        );
      } catch {
        setMapStatus(
          "Mapa wymaga obsługi WebGL. Możesz korzystać z listy wydzieleń i linków nawigacji.",
        );
      }
    }
    // Geometria WSZYSTKICH wydzielen z M (tryb Wilgotnosc pokazuje tez te poza maska).
    const moistureById = new Map(allScores.map((sc) => [sc.stand_id, finite(sc.M) ? sc.M : null]));
    map?.setAllStands(
      data.stands.features.map((feature) => ({
        feature,
        moisture: moistureById.get(feature.properties.stand_id) ?? null,
      })),
    );
    map?.setData(entries);
    map?.setColorMode(colorMode);
    renderColorModes();
    updateLegend();
    map?.setAccessData(data.accessPoints, data.forestRoads);
    for (const l of ACCESS_LAYERS) map?.setLayerVisible(l.id, layerState[l.id]);
    renderLayerControls(data.accessPoints, data.forestRoads);
    if (viewMode === "regions" && regionViews.length) {
      map?.selectGroup(
        regionViews[0].members.map((m) => m.score.stand_id),
        regionPoint(regionViews[0]),
        "1",
      );
    } else {
      map?.select(selected);
    }
    renderPanel();
  } catch (error) {
    if (seq !== loadSeq) return; // a newer switch/retry already started
    loadError =
      error instanceof Error ? error.message : "Nieznany błąd wczytywania.";
    $("#analysis-date").textContent = "Dane niedostępne";
    $("#conditions").innerHTML =
      `<span class="condition-symbol">${icon("info")}</span><div class="cond-main"><strong>Brak dostępnej analizy</strong><p>Przygotuj komplet danych przed wyjazdem.</p></div>`;
    // Otherwise a failed switch (e.g. a corrupted saved trip) leaves the
    // PREVIOUS dataset's polygons/pin drawn under the error banner, which
    // misleadingly looks like it's still the current view.
    entries = [];
    baseEntries = [];
    regionViews = [];
    moistureOk = false;
    pressureAvailable = false;
    colorMode = "score";
    map?.setAllStands([]);
    map?.setData([]);
    renderColorModes();
    map?.setAccessData(null, null);
    $("#layer-controls").hidden = true;
    map?.select("");
    renderPanel();
  }
}
setPane(mobilePane);
updateSavedCount();
void initialize();
