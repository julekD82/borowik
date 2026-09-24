import maplibregl from "maplibre-gl";
import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";
import type { StandView, StandFeature } from "./model";
import { vertices } from "./model";

export class ForestMap {
  private map: maplibregl.Map;
  private entries: StandView[] = [];
  private selected = "";
  private marker?: maplibregl.Marker;
  // Region-mode state, deliberately kept separate from `selected` above
  // (single-stand mode's own field) rather than generalizing it -- the two
  // modes are never active at once (the UI toggles between them), and
  // keeping them apart means neither can leak a stale filter into the
  // other. See selectGroup/highlightGroup/focusStands.
  private groupSelected: string[] = [];
  private groupHover: string[] = [];
  private geometry: FeatureCollection<Polygon | MultiPolygon> = {
    type: "FeatureCollection",
    features: [],
  };
  constructor(
    container: HTMLElement,
    private selectStand: (id: string) => void,
    private status: (message: string) => void,
  ) {
    this.map = new maplibregl.Map({
      container,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: "paper",
            type: "background",
            paint: { "background-color": "#e7ecdf" },
          },
        ],
      },
      center: [17.5, 52.2],
      zoom: 6,
      attributionControl: { compact: true },
    });
    this.map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    this.map.addControl(
      new maplibregl.ScaleControl({ unit: "metric" }),
      "bottom-left",
    );
    this.map.on("style.load", () => {
      this.addLayers();
      this.select(this.selected);
    });
    this.map.on("error", () =>
      this.status(
        "Nie udało się wczytać części mapy. Lista wydzieleń pozostaje dostępna.",
      ),
    );
    this.map.on("click", "stand-fill", (event) => {
      const id = event.features?.[0]?.properties?.stand_id;
      if (id) this.selectStand(id);
    });
    this.map.on("mouseenter", "stand-fill", () => {
      this.map.getCanvas().style.cursor = "pointer";
    });
    this.map.on("mouseleave", "stand-fill", () => {
      this.map.getCanvas().style.cursor = "";
    });
    void this.loadBasemap();
  }
  private async loadBasemap() {
    try {
      const response = await fetch(
        "https://tiles.openfreemap.org/styles/liberty",
        { signal: AbortSignal.timeout(15000) },
      );
      if (!response.ok) throw new Error();
      this.map.setStyle(await response.json());
    } catch {
      this.status(
        "Podkład mapy jest niedostępny. Granice wydzieleń i szczegóły nadal działają.",
      );
    }
  }
  private addLayers() {
    if (this.map.getSource("stands")) return;
    this.map.addSource("stands", {
      type: "geojson",
      data: this.geometry,
      attribution: "Bank Danych o Lasach",
    });
    this.map.addLayer({
      id: "stand-fill",
      type: "fill",
      source: "stands",
      paint: {
        "fill-color": [
          "interpolate",
          ["linear"],
          ["get", "rank"],
          0,
          "#d5d5b8",
          35,
          "#98af74",
          65,
          "#3b7553",
          100,
          "#184b3a",
        ],
        "fill-opacity": 0.6,
      },
    });
    this.map.addLayer({
      id: "stand-line",
      type: "line",
      source: "stands",
      paint: { "line-color": "#fffef5", "line-width": 1 },
    });
    // Selection stays above all polygons; no unions or marker per stand.
    this.map.addLayer({
      id: "stand-selected",
      type: "line",
      source: "stands",
      filter: ["==", ["get", "stand_id"], ""],
      paint: { "line-color": "#de7a39", "line-width": 3 },
    });
  }
  setData(entries: StandView[]) {
    this.entries = entries;
    this.geometry = {
      type: "FeatureCollection",
      features: entries.map((e) => ({
        ...e.feature,
        properties: { ...e.feature.properties, rank: e.score.R },
      })),
    };
    (
      this.map.getSource("stands") as maplibregl.GeoJSONSource | undefined
    )?.setData(this.geometry);
    this.fit(
      entries.map((e) => e.feature),
      0,
    );
  }
  select(id: string) {
    this.selected = id;
    this.highlight(null);
    this.marker?.remove();
    this.marker = undefined;
    const index = this.entries.findIndex((e) => e.score.stand_id === id);
    const entry = this.entries[index];
    if (!entry) return;
    const element = document.createElement("button");
    element.className = "map-pin active";
    element.textContent = String(index + 1);
    element.setAttribute("aria-label", `Pokaż wydzielenie ${id}`);
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      this.selectStand(id);
    });
    this.marker = new maplibregl.Marker({ element })
      .setLngLat(entry.point)
      .addTo(this.map);
  }
  highlight(id: string | null) {
    if (!this.map.getLayer("stand-selected")) return;
    this.map.setFilter("stand-selected", [
      "in",
      ["get", "stand_id"],
      ["literal", [this.selected, id ?? this.selected]],
    ]);
  }
  focusStand(id: string) {
    const entry = this.entries.find((e) => e.score.stand_id === id);
    if (entry) this.fit([entry.feature]);
  }
  fitAll() {
    this.fit(this.entries.map((e) => e.feature));
  }
  // Region mode: persistent highlight over every member stand at once
  // (not just one/two ids the way highlight() combines with `selected`),
  // with a single pin at the region's own point (its top stand's
  // centroid) rather than one looked up from `entries` by id.
  selectGroup(ids: string[], pinPoint: [number, number], label = "•") {
    this.groupSelected = ids;
    this.groupHover = [];
    this.applyGroupFilter();
    this.marker?.remove();
    const element = document.createElement("button");
    element.className = "map-pin active";
    element.textContent = label;
    element.setAttribute("aria-label", "Pokaż rejon");
    element.addEventListener("click", (event) => event.stopPropagation());
    this.marker = new maplibregl.Marker({ element })
      .setLngLat(pinPoint)
      .addTo(this.map);
  }
  highlightGroup(ids: string[] | null) {
    this.groupHover = ids ?? [];
    this.applyGroupFilter();
  }
  private applyGroupFilter() {
    if (!this.map.getLayer("stand-selected")) return;
    const ids = [...new Set([...this.groupSelected, ...this.groupHover])];
    this.map.setFilter("stand-selected", [
      "in",
      ["get", "stand_id"],
      ["literal", ids],
    ]);
  }
  focusStands(ids: string[]) {
    const features = ids
      .map((id) => this.entries.find((e) => e.score.stand_id === id)?.feature)
      .filter((f): f is StandFeature => f !== undefined);
    if (features.length) this.fit(features);
  }
  resize() {
    this.map.resize();
  }
  private fit(features: StandFeature[], duration = 650) {
    const bounds = new maplibregl.LngLatBounds();
    for (const feature of features)
      for (const p of vertices(feature)) bounds.extend([p[0], p[1]]);
    if (bounds.isEmpty()) return;
    this.map.fitBounds(bounds, {
      padding: 55,
      maxZoom: 15,
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 0
        : duration,
    });
  }
}
