import maplibregl from "maplibre-gl";
import type { AccessCollection, AccessLayerId, StandFeature } from "../data/types";
import {
  SURFACE_COLORS, attractivenessClass, pointTypeLabel, roadKindLabel, sourceLabel, surfaceLabel,
} from "../domain/access";
import { vertices } from "../domain/geometry";
import type { RegionMarker, StandMapProps } from "../state/store";
import {
  buildStandCollection, lineColor, lineWidth, moistureFillColor, moistureFillOpacity, scoreFillColor, scoreFillOpacity,
} from "./layers";

export type MapHandlers = {
  onStandClick: (id: string) => void;
  onRegionClick: (id: string) => void;
  onStatus: (message: string) => void;
  tooltip: (id: string) => string | null;
};

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

const ACCESS_CLICK_LAYERS = [
  "ap-parking-bdl", "ap-parking-osm", "ap-entrance", "ap-gate", "ap-settlement", "road-public", "road-closed", "road-fire",
];

export class ForestMap {
  private map: maplibregl.Map;
  private collection = buildStandCollection([], new Map());
  private mode: "score" | "moisture" = "score";
  private selection: { standId: string | null; regionStandIds: string[] } = { standId: null, regionStandIds: [] };
  private markers: maplibregl.Marker[] = [];
  private hover: maplibregl.Popup;
  private accessPoints: AccessCollection | null = null;
  private forestRoads: AccessCollection | null = null;
  private layerVisible: Record<AccessLayerId, boolean> = {
    parkings: true, entrances: true, roads: true, fire: false, settlements: false, pressure: false,
  };

  constructor(container: HTMLElement, private handlers: MapHandlers) {
    this.map = new maplibregl.Map({
      container,
      style: { version: 8, sources: {}, layers: [{ id: "paper", type: "background", paint: { "background-color": "#e7ecdf" } }] },
      center: [17.5, 52.2],
      zoom: 6,
      attributionControl: { compact: true },
    });
    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    this.map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    this.hover = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "stand-tooltip" });
    // Podklad (setStyle) usuwa nasze zrodla i warstwy -- odtworz je po kazdym zaladowaniu stylu.
    this.map.on("style.load", () => {
      this.addLayers();
      this.applyMode();
      this.applySelection();
    });
    this.map.on("error", () => this.handlers.onStatus("Nie udało się wczytać części mapy. Lista pozostaje dostępna."));
    this.map.on("click", "stand-fill", (event) => {
      const id = event.features?.[0]?.properties?.stand_id;
      if (typeof id === "string") this.handlers.onStandClick(id);
    });
    this.map.on("mousemove", "stand-fill", (event) => {
      this.map.getCanvas().style.cursor = "pointer";
      const id = event.features?.[0]?.properties?.stand_id;
      const text = typeof id === "string" ? this.handlers.tooltip(id) : null;
      if (text) this.hover.setLngLat(event.lngLat).setText(text).addTo(this.map);
    });
    this.map.on("mouseleave", "stand-fill", () => {
      this.map.getCanvas().style.cursor = "";
      this.hover.remove();
    });
    for (const layer of ACCESS_CLICK_LAYERS) this.map.on("click", layer, (event) => this.showAccessPopup(event));
    void this.loadBasemap();
  }

  private addLayers() {
    if (this.map.getSource("stands")) return;
    this.map.addSource("stands", { type: "geojson", data: this.collection, attribution: "Bank Danych o Lasach" });
    this.map.addLayer({ id: "stand-fill", type: "fill", source: "stands", paint: { "fill-color": scoreFillColor(), "fill-opacity": scoreFillOpacity() } });
    this.map.addLayer({ id: "stand-line", type: "line", source: "stands", paint: { "line-color": lineColor(), "line-width": lineWidth() } });
    this.map.addLayer({
      id: "region-outline", type: "line", source: "stands", filter: [">", ["get", "region"], 0],
      paint: { "line-color": "#234b3d", "line-width": 1.6, "line-opacity": 0.85 },
    });
    this.map.addLayer({
      id: "region-selected", type: "line", source: "stands", filter: ["in", ["get", "stand_id"], ["literal", []]],
      paint: { "line-color": "#234b3d", "line-width": 3 },
    });
    this.map.addLayer({
      id: "stand-selected", type: "line", source: "stands", filter: ["==", ["get", "stand_id"], ""],
      paint: { "line-color": "#d35400", "line-width": 3 },
    });
    this.addAccessLayers();
  }

  private applyMode() {
    if (!this.map.getLayer("stand-fill")) return;
    const moisture = this.mode === "moisture";
    this.map.setPaintProperty("stand-fill", "fill-color", moisture ? moistureFillColor() : scoreFillColor());
    this.map.setPaintProperty("stand-fill", "fill-opacity", moisture ? moistureFillOpacity() : scoreFillOpacity());
  }

  private applySelection() {
    if (!this.map.getLayer("stand-selected")) return;
    this.map.setFilter("stand-selected", ["==", ["get", "stand_id"], this.selection.standId ?? ""]);
    this.map.setFilter("region-selected", ["in", ["get", "stand_id"], ["literal", this.selection.regionStandIds]]);
  }

  setStands(features: StandFeature[], props: Map<string, StandMapProps>) {
    this.collection = buildStandCollection(features, props);
    (this.map.getSource("stands") as maplibregl.GeoJSONSource | undefined)?.setData(this.collection);
  }

  setMode(mode: "score" | "moisture") {
    this.mode = mode;
    this.applyMode();
  }

  setSelection(selection: { standId: string | null; regionStandIds: string[] }) {
    this.selection = selection;
    this.applySelection();
  }

  setRegions(regions: RegionMarker[]) {
    for (const marker of this.markers) marker.remove();
    this.markers = regions.map((region) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "region-marker";
      element.textContent = String(region.number);
      element.setAttribute("aria-label", `Rejon ${region.number}`);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        this.handlers.onRegionClick(region.id);
      });
      return new maplibregl.Marker({ element }).setLngLat(region.point).addTo(this.map);
    });
  }

  fitFeatures(features: StandFeature[], duration = 650) {
    const bounds = new maplibregl.LngLatBounds();
    for (const feature of features) for (const p of vertices(feature)) bounds.extend([p[0], p[1]]);
    if (bounds.isEmpty()) return;
    this.map.fitBounds(bounds, {
      padding: 55,
      maxZoom: 15,
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : duration,
    });
  }

  resize() {
    this.map.resize();
  }

  destroy() {
    this.hover.remove();
    for (const marker of this.markers) marker.remove();
    this.map.remove();
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
      this.handlers.onStatus(
        "Podkład mapy jest niedostępny. Granice wydzieleń i szczegóły nadal działają.",
      );
    }
  }
}
