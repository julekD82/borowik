import { effect, untracked } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { ACCESS_LAYERS } from "../domain/access";
import { ForestMap } from "../map/forestMap";
import {
  access, analysis, featuresFor, fitRequest, layers, mapMode, mapStatus, mobilePane, openRegion, openStand,
  regionMarkers, selection, standProps, standTooltip,
} from "../state/store";
import { Legend } from "./Legend";
import { MapControls } from "./MapControls";

export function MapView() {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const map = new ForestMap(container.current, {
      onStandClick: (id) => openStand(id, "map"),
      onRegionClick: (id) => openRegion(id, "map"),
      onStatus: (message) => { mapStatus.value = message; },
      tooltip: standTooltip,
    });
    const stops = [
      effect(() => {
        const a = analysis.value;
        if (a) map.setStands([...a.features.values()], standProps.value);
      }),
      effect(() => map.setMode(mapMode.value)),
      effect(() => map.setRegions(regionMarkers.value)),
      effect(() => map.setSelection(selection.value)),
      effect(() => map.setAccessData(access.value.points, access.value.roads)),
      effect(() => {
        const on = layers.value;
        for (const l of ACCESS_LAYERS) map.setLayerVisible(l.id, on[l.id]);
      }),
      // Przyblizenie tylko po nowym zadaniu (fitRequest); zmiany rankingu nie przesuwaja mapy.
      effect(() => {
        const request = fitRequest.value;
        if (request) untracked(() => map.fitFeatures(featuresFor(request.req)));
      }),
      effect(() => {
        void mobilePane.value;
        requestAnimationFrame(() => map.resize());
      }),
    ];
    return () => {
      for (const stop of stops) stop();
      map.destroy();
    };
  }, []);
  return (
    <div class="map-stage">
      <div ref={container} class="map-canvas" aria-label="Mapa wydzieleń" />
      <MapControls />
      <Legend />
      {mapStatus.value && <p class="map-status" role="status">{mapStatus.value}</p>}
    </div>
  );
}
