import "maplibre-gl/dist/maplibre-gl.css";
import "./style.css";
import {
  loadData,
  joinRegions,
  fruitingClass,
  habitatClass,
  confidenceLabel,
  entranceLabel,
  distanceLabel,
  distanceMethod,
  topExplanations,
  navigationUrl,
  finite,
  isStandaloneTarget,
} from "./model";
import type { StandView, Score, Region, RegionView } from "./model";
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
let entries: StandView[] = [];
let allScores: Score[] = [];
let allRegions: Region[] = [];
let regionViews: RegionView[] = [];
let selected = "";
let detail = false;
const PAGE_SIZE = 30;
let page = 0;
let savedOnly = false;
let map: ForestMap | undefined;
let loaded = false;
let loadError = "";
let noticeTimer: ReturnType<typeof setTimeout>;
// "regions" (grouped) vs "stands" (flat, every wydzielenie individually) --
// two peer views over the same analysis, not one replacing the other.
let viewMode: "regions" | "stands" = "regions";
let selectedRegionId = "";
// Set via a region card's "Zobacz wydzielenia w rejonie": while non-null,
// the stand view (list, map, detail) is scoped to just that region's
// members, with a way back to the region view instead of the full list.
let regionFilterId: string | null = null;
const VIEW_MODE_KEY = "borowik.view-mode.v1";
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
    <section id="conditions" class="conditions" aria-live="polite"><span class="condition-symbol">${icon("leaf")}</span><div><strong>Sprawdzamy warunki w obszarze</strong><p>Wczytujemy przygotowaną analizę lasu.</p></div><span class="model-label">MODEL EKSPERCKI · NIESKALIBROWANY</span></section>
    <section class="workspace" aria-label="Wydzielenia poszukiwań">
      <aside class="sidebar"><div id="panel-heading" class="panel-heading"></div><div id="view-toggle" class="view-toggle" hidden><button data-view="regions" class="view-toggle-btn">Rejony</button><button data-view="stands" class="view-toggle-btn">Wydzielenia</button></div><div id="cards" class="cards" aria-live="polite"><div class="empty"><span class="loading-ring"></span><h2>Jeszcze chwila…</h2><p>Wczytujemy oceny i granice wydzieleń.</p></div></div><div class="panel-footer">${icon("info")} Ranking porównuje miejsca w tej analizie.<br>Nie jest prawdopodobieństwem znalezienia grzybów.</div></aside>
      <div class="map-area"><div id="map" aria-label="Mapa wydzieleń poszukiwań"></div><div class="map-heading"><span class="status-dot"></span><span id="map-title">Mapa poszukiwań</span></div><button id="fit-map" class="map-fit" aria-label="Pokaż cały obszar">${icon("target")}</button><div id="map-status" class="map-status" role="status" hidden></div><div class="map-legend"><span id="legend-content"><i class="legend-swatch"></i> Obiecujące wydzielenia <span class="legend-divider"></span><i class="legend-point"></i> Punkt orientacyjny</span></div><div class="map-caption">Granice lasu, nie gwarancja zbioru.</div></div>
    </section>
    <footer class="footer"><span>Borowik <span class="footer-dot">·</span> Dobry spacer zaczyna się od dobrego planu.</span><button id="about">O danych i ograniczeniach ${icon("info")}</button></footer>
  </main>
  <div id="toast" class="toast" role="status" hidden></div>
  <dialog id="about-dialog"><button class="dialog-close" aria-label="Zamknij">${icon("close")}</button><p class="eyebrow">WARTO WIEDZIEĆ</p><h2>Mapa pomaga wybrać las.</h2><p>Model ekspercki porównuje siedliska i warunki pogodowe. Nie został skalibrowany obserwacjami terenowymi i nie przewiduje pewnego zbioru.</p><ul><li>Punkty na mapie to środki wydzieleń, a nie współrzędne parkingów lub wejść.</li><li>Odległość dotyczy dojścia od wejścia albo oszacowania od najbliższej drogi lub parkingu. Nie jest długością dojazdu samochodem.</li><li>Data analizy jest etykietą eksportu. Brakuje osobnych dat pobrania warstw; pogoda pochodzi z okna przy uruchomieniu analizy.</li><li>Maska wyklucza część niedostępnych terenów. Okresowe zakazy są sprawdzane tylko dla najlepszych kandydatów, nie wszystkich wydzieleń.</li><li>Zapis zachowuje tekst i współrzędne w tej przeglądarce. Ponowne uruchomienie strony i podkład mapy wymagają połączenia; pełny tryb offline nie jest jeszcze dostępny.</li></ul><p class="source-links">Źródła: <a href="https://www.bdl.lasy.gov.pl/" target="_blank" rel="noopener noreferrer">Bank Danych o Lasach</a>, <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a>, GDOŚ, <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>. Podkład: <a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap</a>.</p></dialog>
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
function setMapStatus(message: string) {
  $("#map-status").textContent = message;
  $("#map-status").hidden = !message;
}
function explanations(score?: Score, full = false) {
  const entries = full
    ? score?.explanation
    : topExplanations(score?.explanation ?? []);
  return entries?.length
    ? `<ul class="reasons">${entries.map((e) => `<li><span class="reason-mark ${e.contribution < 0 ? "negative" : ""}">${e.contribution < 0 ? "−" : "+"}</span><span>${escape(e.text)}</span></li>`).join("")}</ul>`
    : '<p class="muted">Brak uzasadnienia w eksporcie.</p>';
}
function confidence(score?: Score) {
  return `<details class="confidence"><summary>Pewność: <strong>${confidenceLabel(score?.confidence)}</strong><span> ⓘ</span></summary><ul>${score?.confidence_reasons.length ? score.confidence_reasons.map((r) => `<li>${escape(r)}</li>`).join("") : "<li>Brak szczegółowych powodów w eksporcie.</li>"}</ul></details>`;
}
function assessment(score?: Score) {
  return `<div class="assessment"><div><small>SIEDLISKO</small><strong>${habitatClass(score?.H)}</strong></div><div><small>WARUNKI TERAZ</small><strong>${fruitingClass(score?.F)}</strong></div></div>`;
}
function access(score?: Score) {
  return `<div class="access"><div>${icon("location")}<span>Orientacyjne dojście <strong>${distanceLabel(score?.d_park_m)}</strong></span></div><small>${distanceMethod(score?.distance_method)}</small><p>${entranceLabel(score?.entrance_status)} · brak współrzędnych wejścia w danych.</p></div>`;
}
function card(entry: StandView, index: number) {
  const isSelected = selected === entry.score.stand_id;
  const isSaved = getSaved().some(
    (s) => s.key === savedKey(entry.score.stand_id, entry.point),
  );
  return `<article class="region-card ${isSelected ? "selected" : ""}" data-card="${escape(entry.score.stand_id)}"><button class="card-select" data-select="${escape(entry.score.stand_id)}" aria-pressed="${isSelected}"><span class="region-number">${String(index + 1).padStart(2, "0")}</span><span class="card-title"><span class="card-eyebrow">${index === 0 ? "PIERWSZY WYBÓR" : "WARTO ROZWAŻYĆ"}</span><strong>Wydzielenie ${escape(entry.score.stand_id)}</strong><small> ${coordinates(entry.point)}</small></span><span class="select-arrow">${icon("arrow")}</span></button><div class="card-body"><div class="badge-row"><span class="badge">${icon("leaf")}${fruitingClass(entry.score?.F)}</span>${confidence(entry.score)}</div>${assessment(entry.score)}<p class="why-label">Dlaczego tutaj?</p>${explanations(entry.score)}${isSelected ? `${access(entry.score)}<div class="point-note">Punkt orientacyjny: środek wydzielenia.<br>Dojazd samochodem: brak danych.</div><details class="model-details"><summary>Ranking i dostępność</summary><p>Ranking wydzielenia: ${entry.score.R!.toLocaleString("pl-PL", { maximumFractionDigits: 1 })} · model nieskalibrowany.</p><p>Dostępność dla innych odwiedzających (P): ${finite(entry.score?.P) ? entry.score!.P!.toFixed(2) : "brak danych"}. To wskaźnik modelu, nie pomiar tłoku. Brak danych o wejściach może obniżać ten wynik.</p></details>` : ""}<div class="card-actions"><button class="save-button ${isSaved ? "is-saved" : ""}" data-save="${escape(entry.score.stand_id)}">${icon(isSaved ? "check" : "bookmark")}${isSaved ? "Zapisano" : "Zapisz miejsce"}</button><a class="navigation-link" href="${navigationUrl(entry.point)}" target="_blank" rel="noopener noreferrer" aria-label="Nawiguj do punktu orientacyjnego wydzielenia ${escape(entry.score.stand_id)}">${icon("location")}Nawiguj</a></div><button class="detail-button" data-detail="${escape(entry.score.stand_id)}">Szczegóły wydzielenia ${icon("arrow")}</button><div class="freshness">Analiza: ${formatDate(entry.score.day)}</div></div></article>`;
}
function regionPoint(view: RegionView): [number, number] {
  return [view.region.centroid_lon, view.region.centroid_lat];
}
function regionCard(view: RegionView, index: number) {
  const isSelected = selectedRegionId === view.region.region_id;
  const point = regionPoint(view);
  const isSaved = getSaved().some(
    (s) => s.key === savedKey(view.region.region_id, point),
  );
  const score = view.top.score;
  return `<article class="region-card ${isSelected ? "selected" : ""}" data-region-card="${escape(view.region.region_id)}"><button class="card-select" data-region-select="${escape(view.region.region_id)}" aria-pressed="${isSelected}"><span class="region-number">${String(index + 1).padStart(2, "0")}</span><span class="card-title"><span class="card-eyebrow">${index === 0 ? "PIERWSZY WYBÓR" : "WARTO ROZWAŻYĆ"}</span><strong>Rejon ${escape(view.region.region_id)}</strong><small> ${view.members.length} wydzieleń · ${coordinates(point)}</small></span><span class="select-arrow">${icon("arrow")}</span></button><div class="card-body"><div class="badge-row"><span class="badge">${icon("leaf")}${fruitingClass(score?.F)}</span>${confidence(score)}</div>${assessment(score)}<p class="why-label">Dlaczego tutaj?</p>${explanations(score)}${isSelected ? `${access(score)}<div class="point-note">Punkt orientacyjny: środek najlepiej ocenionego wydzielenia w rejonie.<br>Dojazd samochodem: brak danych.</div><details class="model-details"><summary>Ranking i dostępność</summary><p>Ranking rejonu: ${view.region.rank_score.toLocaleString("pl-PL", { maximumFractionDigits: 1 })} · mediana najlepszych wydzieleń, model nieskalibrowany.</p><p>Dostępność dla innych odwiedzających (P): ${finite(score?.P) ? score!.P!.toFixed(2) : "brak danych"} (najlepiej ocenione wydzielenie). To wskaźnik modelu, nie pomiar tłoku. Brak danych o wejściach może obniżać ten wynik.</p></details>` : ""}<div class="card-actions"><button class="save-button ${isSaved ? "is-saved" : ""}" data-region-save="${escape(view.region.region_id)}">${icon(isSaved ? "check" : "bookmark")}${isSaved ? "Zapisano" : "Zapisz rejon"}</button><a class="navigation-link" href="${navigationUrl(point)}" target="_blank" rel="noopener noreferrer" aria-label="Nawiguj do punktu orientacyjnego rejonu ${escape(view.region.region_id)}">${icon("location")}Nawiguj</a></div><button class="detail-button" data-region-detail="${escape(view.region.region_id)}">Zobacz wydzielenia w rejonie (${view.members.length}) ${icon("arrow")}</button><div class="freshness">Analiza: ${formatDate(view.region.day)}</div></div></article>`;
}
function renderRegionsPanel() {
  $("#panel-heading").innerHTML =
    `<div><h2>Rejony <span class="count-pill">${regionViews.length}</span></h2><p>Grupy sąsiadujących wydzieleń · po filtrach modelu</p></div><span class="sort-label">Najlepsze najpierw ↓</span>`;
  $("#cards").innerHTML = regionViews.length
    ? regionViews.map((view, i) => regionCard(view, i)).join("")
    : `<div class="empty"><span class="empty-icon">${icon("leaf")}</span><h2>Brak rejonów w tej analizie</h2><p>Żadna grupa wydzieleń nie spełniła kryteriów grupowania. Zobacz widok „Wydzielenia” albo przygotuj nową analizę bliżej wyjazdu.</p></div>`;
  $("#map-title").textContent =
    `${regionViews.length} rejonów · przygotowany obszar`;
  $("#legend-content").innerHTML =
    '<span class="gradient-legend"></span> Niższy → wyższy ranking względny';
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
  if (detail) {
    renderDetail();
    return;
  }
  if (viewMode === "regions" && !regionFilterId) {
    renderRegionsPanel();
    return;
  }
  const visible = visibleEntries();
  const filterView = regionFilterId
    ? regionViews.find((v) => v.region.region_id === regionFilterId)
    : undefined;
  $("#panel-heading").innerHTML = filterView
    ? `<div><button class="back-button" id="back-to-regions">← Wróć do rejonów</button><h2>Rejon ${escape(filterView.region.region_id)} <span class="count-pill">${visible.length}</span></h2><p>Wydzielenia należące do tego rejonu</p></div>`
    : `<div><h2>Wydzielenia <span class="count-pill">${visible.length}</span></h2><p>Każde ocenione osobno · po filtrach modelu</p></div><span class="sort-label">Najlepsze najpierw ↓</span>`;
  $("#cards").innerHTML = visible.length
    ? visible
        .slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
        .map((entry, i) => card(entry, page * PAGE_SIZE + i))
        .join("") +
      `<div class="pagination"><button id="previous-page" ${page === 0 ? "disabled" : ""}>← Poprzednie</button><span>${page + 1} / ${Math.ceil(visible.length / PAGE_SIZE)}</span><button id="next-page" ${(page + 1) * PAGE_SIZE >= visible.length ? "disabled" : ""}>Następne →</button></div>`
    : '<div class="empty"><span class="empty-icon">' +
      icon("leaf") +
      "</span><h2>Brak propozycji w tej analizie</h2><p>Żadne wydzielenie nie spełniło kryteriów. Sprawdź inny obszar lub przygotuj nową analizę bliżej wyjazdu.</p></div>";
  $("#map-title").textContent = filterView
    ? `Rejon ${filterView.region.region_id} · ${visible.length} wydzieleń`
    : `${visible.length} wydzieleń · przygotowany obszar`;
  $("#legend-content").innerHTML =
    '<span class="gradient-legend"></span> Niższy → wyższy ranking względny';
}
function renderDetail() {
  const entry = entries.find((r) => r.score.stand_id === selected);
  if (!entry) return;
  const score = entry.score;
  $("#panel-heading").innerHTML =
    '<button class="back-button" id="back">← Wróć do listy wydzieleń</button>';
  $("#cards").innerHTML =
    `<div class="stand-panel">${score ? `<p class="eyebrow detail-eyebrow">SZCZEGÓŁY WYDZIELENIA</p><h3 class="stand-id">${escape(score.stand_id)}</h3><div class="badge-row"><span class="badge">${fruitingClass(score.F)}</span>${confidence(score)}</div>${assessment(score)}<dl class="metrics"><div><dt>Ranking R</dt><dd>${finite(score.R) ? score.R.toFixed(1) : "—"}</dd></div><div><dt>Siedlisko H</dt><dd>${finite(score.H) ? score.H.toFixed(2) : "—"}</dd></div><div><dt>Warunki regionalne F</dt><dd>${fruitingClass(score.F)}</dd></div><div><dt>Warunki lokalne F</dt><dd>${fruitingClass(score.F_loc)}</dd></div><div><dt>Dostępność dla odwiedzających P</dt><dd>${finite(score.P) ? score.P.toFixed(2) : "—"}</dd></div></dl><p class="muted">Model ekspercki, nieskalibrowany. P jest szacunkiem dostępności, nie pomiarem tłoku.</p><h3>Co wpływa na wynik?</h3>${explanations(score, true)}${access(score)}<div class="data-note"><strong>Zakres danych</strong><p>${score.mask ? "Wydzielenie przeszło filtry modelu. Nie jest to potwierdzenie pełnej dostępności prawnej." : "Wydzielenie wykluczone przez filtr modelu."}</p><p>Domieszki gatunkowe: brak danych. Osobne składowe siedliska i szczegółowa pogoda nie są dostępne w eksporcie.</p><p>Analiza: ${formatDate(score.day)}.<br>Daty pobrania poszczególnych źródeł: brak danych.</p></div>` : "<p>Brak szczegółów.</p>"}</div>`;
  $("#map-title").textContent = `Wydzielenie ${entry.score.stand_id}`;
  $("#legend-content").innerHTML =
    '<span class="gradient-legend"></span> Niższy → wyższy ranking względny';
  map?.select(selected);
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
  detail = false;
  savedOnly = false;
  renderPanel();
  map?.select(id);
  if (focus) map?.focusStand(id);
}
function selectRegionCard(id: string, focus = true) {
  selectedRegionId = id;
  detail = false;
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
    title: `Wydzielenie ${entry.score.stand_id}`,
    point: entry.point,
    day: entry.score.day,
    conditions: fruitingClass(entry.score?.F),
    reasons: topExplanations(entry.score?.explanation ?? []).map((e) => e.text),
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
    title: `Rejon ${view.region.region_id}`,
    point,
    day: view.region.day,
    conditions: fruitingClass(view.top.score?.F),
    reasons: topExplanations(view.top.score?.explanation ?? []).map(
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
  if (mode === "regions") {
    if (regionViews.length) selectRegionCard(regionViews[0].region.region_id);
  } else if (selected) {
    // select() removes any group marker and resets the highlight filter to
    // just this stand, so switching out of region mode needs no separate
    // "clear group" call.
    map?.select(selected);
    map?.fitAll();
  }
}

document.addEventListener("click", (event) => {
  const button = (event.target as Element).closest<HTMLElement>("button");
  if (!button) return;
  if (button.dataset.select) {
    selectStand(button.dataset.select);
    return;
  }
  if (button.dataset.save) {
    save(button.dataset.save);
    return;
  }
  if (button.dataset.detail) {
    selected = button.dataset.detail;
    detail = true;
    renderPanel();
    map?.focusStand(selected);
    $("#back").focus();
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
      break;
    case "back":
      detail = false;
      renderPanel();
      map?.select(selected);
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
      if (detail) map?.focusStand(selected);
      else if (activeRegion)
        map?.focusStands(activeRegion.members.map((m) => m.score.stand_id));
      else map?.fitAll();
      break;
    }
    case "about":
      $("#about-dialog") instanceof HTMLDialogElement &&
        ($("#about-dialog") as HTMLDialogElement).showModal();
      break;
    case "retry":
      void initialize();
      break;
  }
  if (button.classList.contains("dialog-close"))
    ($("#about-dialog") as HTMLDialogElement).close();
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
async function initialize() {
  loaded = false;
  loadError = "";
  $("#cards").innerHTML =
    '<div class="empty"><span class="loading-ring"></span><h2>Wczytujemy analizę…</h2></div>';
  renderPanel();
  try {
    const data = await loadData();
    entries = data.entries;
    allScores = data.scores;
    allRegions = data.regions;
    regionViews = joinRegions(allRegions, entries);
    loaded = true;
    page = 0;
    detail = false;
    regionFilterId = null;
    selected = entries[0]?.score.stand_id ?? "";
    selectedRegionId = regionViews[0]?.region.region_id ?? "";
    viewMode =
      getViewModePreference() ?? (regionViews.length > 0 ? "regions" : "stands");
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
    $("#conditions").innerHTML =
      `<span class="condition-symbol">${icon("leaf")}</span><div><strong>Warunki w obszarze: ${fruitingClass(median).toLocaleLowerCase("pl")}</strong><p>Ocena pogody z analizy · mediana dla wydzieleń przechodzących filtry</p></div><span class="model-label">MODEL EKSPERCKI · NIESKALIBROWANY</span>`;
    if (!map) {
      try {
        map = new ForestMap(
          $("#map"),
          (id) => {
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
    map?.setData(entries);
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
    loadError =
      error instanceof Error ? error.message : "Nieznany błąd wczytywania.";
    $("#analysis-date").textContent = "Dane niedostępne";
    $("#conditions").innerHTML =
      `<span class="condition-symbol">${icon("info")}</span><div><strong>Brak dostępnej analizy</strong><p>Przygotuj komplet danych przed wyjazdem.</p></div>`;
    renderPanel();
  }
}
updateSavedCount();
void initialize();
