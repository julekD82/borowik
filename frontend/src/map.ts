import maplibregl from "maplibre-gl";
import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";
import type { StandView, StandFeature, AccessCollection, AccessLayerId } from "./model";
import {
  vertices,
  SURFACE_COLORS,
  pointTypeLabel,
  sourceLabel,
  surfaceLabel,
  roadKindLabel,
  attractivenessClass,
} from "./model";

// Faza 3.5: warstwy mapy (grupa przelaczana w legendzie -> id warstw MapLibre).
const ACCESS_LAYER_GROUPS: Record<AccessLayerId, string[]> = {
  parkings: ["ap-parking-osm", "ap-parking-bdl", "ap-parking-label"],
  entrances: ["ap-entrance", "ap-gate"],
  roads: ["road-public", "road-closed"],
  fire: ["road-fire"],
  settlements: ["ap-settlement"],
  pressure: ["stand-pressure"],
};
const SURFACE_MATCH = [
  "match",
  ["get", "surface"],
  ...Object.entries(SURFACE_COLORS).flat(),
  SURFACE_COLORS.unknown,
] as unknown as maplibregl.ExpressionSpecification;

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
  private accessPoints: AccessCollection | null = null;
  private forestRoads: AccessCollection | null = null;
  private layerVisible: Record<AccessLayerId, boolean> = {
    parkings: true,
    entrances: true,
    roads: true,
    fire: false,
    settlements: false,
    pressure: false,
  };
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
    for (const layer of [
      "ap-parking-bdl",
      "ap-parking-osm",
      "ap-entrance",
      "ap-gate",
      "ap-settlement",
      "road-public",
      "road-closed",
      "road-fire",
    ])
      this.map.on("click", layer, (event) => this.showAccessPopup(event));
    void this.loadBasemap();
  }
  private showAccessPopup(event: maplibregl.MapLayerMouseEvent) {
    const props = event.features?.[0]?.properties;
    if (!props) return;
    const escapeHtml = (s: unknown) =>
      String(s ?? "").replace(
        /[&<>"']/g,
        (c) =>
          ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
      );
    const level =
      attractivenessClass(props.attractiveness) ?? props.attractiveness_class;
    const cls = level
      ? `atrakcyjność: <strong>${escapeHtml(level)}</strong>`
      : "atrakcyjność: nie dotyczy";
    const html = props.kind
      ? `<strong>${escapeHtml(roadKindLabel(props.kind))}</strong><br>nawierzchnia: ${escapeHtml(surfaceLabel(props.surface))}<br>źródło: ${escapeHtml(sourceLabel(props.source ?? (props.kind === "fire" ? "bdl_ppoz" : "")))}${props.fire_no ? `<br>numer dojazdu: ${escapeHtml(props.fire_no)}` : ""}<br>${cls}`
      : `<strong>${escapeHtml(pointTypeLabel(props.type))}${props.name ? ` „${escapeHtml(props.name)}”` : ""}</strong><br>źródło: ${escapeHtml(sourceLabel(props.source))}<br>${cls}`;
    new maplibregl.Popup({ closeButton: true, maxWidth: "240px" })
      .setLngLat(event.lngLat)
      .setHTML(`<div class="access-popup">${html}</div>`)
      .addTo(this.map);
  }
  private addAccessLayers() {
    const before = this.map.getLayer("stand-selected") ? "stand-selected" : undefined;
    if (!this.map.getSource("access-points")) {
      const empty = { type: "FeatureCollection", features: [] } as AccessCollection;
      this.map.addSource("access-points", { type: "geojson", data: this.accessPoints ?? empty });
      this.map.addSource("forest-roads", { type: "geojson", data: this.forestRoads ?? empty });
    }
    // Presja P: polprzezroczysta warstwa pod obrysami wydzielen.
    this.map.addLayer(
      {
        id: "stand-pressure",
        type: "fill",
        source: "stands",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "pressure"], 0],
            0,
            "#fff3d6",
            0.5,
            "#f0a54a",
            1,
            "#b23b2e",
          ],
          "fill-opacity": 0.45,
        },
      },
      "stand-line",
    );
    // grubosc linii wg atrakcyjnosci odcinka
    const width = [
      "interpolate",
      ["linear"],
      ["coalesce", ["get", "attractiveness"], 0],
      0,
      1,
      0.3,
      2.2,
      1,
      4,
    ] as unknown as maplibregl.ExpressionSpecification;
    this.map.addLayer(
      {
        id: "road-fire",
        type: "line",
        source: "forest-roads",
        filter: ["==", ["get", "kind"], "fire"],
        paint: { "line-color": "#6b7fa0", "line-width": 1, "line-opacity": 0.7 },
      },
      before,
    );
    this.map.addLayer(
      {
        id: "road-closed",
        type: "line",
        source: "forest-roads",
        filter: ["==", ["get", "kind"], "closed"],
        // zamkniete drogi lesne: linia przerywana (publiczne sa ciagle)
        paint: { "line-color": SURFACE_MATCH, "line-width": width, "line-dasharray": [2, 1.2] },
      },
      before,
    );
    this.map.addLayer(
      {
        id: "road-public",
        type: "line",
        source: "forest-roads",
        filter: ["==", ["get", "kind"], "public"],
        paint: { "line-color": SURFACE_MATCH, "line-width": 2.2 },
      },
      before,
    );
    const ofType = (type: string, source?: string) =>
      (source
        ? ["all", ["==", ["get", "type"], type], ["==", ["get", "source"], source]]
        : ["==", ["get", "type"], type]) as maplibregl.FilterSpecification;
    this.map.addLayer(
      {
        id: "ap-settlement",
        type: "circle",
        source: "access-points",
        filter: ofType("settlement"),
        paint: {
          "circle-radius": 4,
          "circle-color": "#c9a8d4",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1,
          "circle-opacity": 0.8,
        },
      },
      before,
    );
    this.map.addLayer(
      {
        id: "ap-entrance",
        type: "circle",
        source: "access-points",
        filter: ["in", ["get", "type"], ["literal", ["entrance", "road_fallback"]]],
        paint: {
          "circle-radius": 3.5,
          "circle-color": "#2a8f7a",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1,
        },
      },
      before,
    );
    this.map.addLayer(
      {
        id: "ap-gate",
        type: "circle",
        source: "access-points",
        filter: ofType("gate"),
        // szlaban: wiekszy czerwony znacznik z grubym obrysem (osobny symbol)
        paint: {
          "circle-radius": 5,
          "circle-color": "#c0392b",
          "circle-stroke-color": "#3b0d08",
          "circle-stroke-width": 2,
        },
      },
      before,
    );
    this.map.addLayer(
      {
        id: "ap-parking-osm",
        type: "circle",
        source: "access-points",
        filter: ofType("parking", "osm"),
        paint: {
          "circle-radius": 7,
          "circle-color": "#5b8ec9",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        },
      },
      before,
    );
    this.map.addLayer(
      {
        id: "ap-parking-bdl",
        type: "circle",
        source: "access-points",
        filter: ofType("parking", "bdl"),
        paint: {
          "circle-radius": 7,
          "circle-color": "#1f4e9c",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        },
      },
      before,
    );
    // Litera "P" wymaga glifow z podkladu; bez nich zostaja same kolka.
    if (this.map.getStyle()?.glyphs) {
      this.map.addLayer(
        {
          id: "ap-parking-label",
          type: "symbol",
          source: "access-points",
          filter: ofType("parking"),
          layout: {
            "text-field": "P",
            "text-size": 10,
            "text-font": ["Noto Sans Bold"],
            "text-allow-overlap": true,
          },
          paint: { "text-color": "#ffffff" },
        },
        before,
      );
    }
    this.applyAccessVisibility();
  }
  private applyAccessVisibility() {
    for (const [group, layers] of Object.entries(ACCESS_LAYER_GROUPS))
      for (const id of layers)
        if (this.map.getLayer(id))
          this.map.setLayoutProperty(
            id,
            "visibility",
            this.layerVisible[group as AccessLayerId] ? "visible" : "none",
          );
  }
  setAccessData(points: AccessCollection | null, roads: AccessCollection | null) {
    this.accessPoints = points;
    this.forestRoads = roads;
    const empty = { type: "FeatureCollection", features: [] } as AccessCollection;
    (this.map.getSource("access-points") as maplibregl.GeoJSONSource | undefined)?.setData(
      points ?? empty,
    );
    (this.map.getSource("forest-roads") as maplibregl.GeoJSONSource | undefined)?.setData(
      roads ?? empty,
    );
  }
  setLayerVisible(id: AccessLayerId, visible: boolean) {
    this.layerVisible[id] = visible;
    this.applyAccessVisibility();
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
    this.addAccessLayers();
  }
  setData(entries: StandView[]) {
    this.entries = entries;
    this.geometry = {
      type: "FeatureCollection",
      features: entries.map((e) => ({
        ...e.feature,
        properties: { ...e.feature.properties, rank: e.score.R, pressure: e.score.P },
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
