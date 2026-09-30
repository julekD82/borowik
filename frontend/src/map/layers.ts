import type maplibregl from "maplibre-gl";
import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import type { StandFeature } from "../data/types";
import { MOISTURE_NO_DATA_COLOR, MOISTURE_STOPS } from "../domain/moisture";
import type { ScoreClass } from "../domain/ranking";
import type { StandMapProps } from "../state/store";

type Expr = maplibregl.ExpressionSpecification;

// Kolory klas procentowych (1 = najlepsze 5%); klasa 4 prawie niewidoczna.
export const CLASS_COLORS: Record<ScoreClass, string> = { 1: "#1f5c3a", 2: "#4f8f5c", 3: "#a9cba0", 4: "#dcdcd2" };
export const OUTSIDE_LINE_COLOR = "#aeb5a3";

export function buildStandCollection(
  features: StandFeature[],
  props: Map<string, StandMapProps>,
): FeatureCollection<Polygon | MultiPolygon> {
  return {
    type: "FeatureCollection",
    features: features.map((f) => {
      const p = props.get(f.properties.stand_id);
      return {
        type: "Feature",
        geometry: f.geometry,
        properties: {
          stand_id: f.properties.stand_id,
          cls: p?.cls ?? 0,
          moisture: p?.moisture ?? null,
          pressure: p?.pressure ?? null,
          region: p?.region ?? 0,
        },
      };
    }),
  };
}

export const scoreFillColor = (): Expr =>
  ["match", ["get", "cls"], 1, CLASS_COLORS[1], 2, CLASS_COLORS[2], 3, CLASS_COLORS[3], 4, CLASS_COLORS[4], "rgba(0,0,0,0)"] as unknown as Expr;
export const scoreFillOpacity = (): Expr => ["match", ["get", "cls"], 1, 0.85, 2, 0.8, 3, 0.7, 4, 0.45, 0] as unknown as Expr;
export const moistureFillColor = (): Expr =>
  [
    "case",
    ["==", ["typeof", ["get", "moisture"]], "number"],
    ["interpolate", ["linear"], ["get", "moisture"], ...MOISTURE_STOPS.flat()],
    MOISTURE_NO_DATA_COLOR,
  ] as unknown as Expr;
export const moistureFillOpacity = (): Expr => ["case", [">", ["get", "cls"], 0], 0.8, 0.35] as unknown as Expr;
export const lineColor = (): Expr => ["case", [">", ["get", "cls"], 0], "#fffef5", OUTSIDE_LINE_COLOR] as unknown as Expr;
export const lineWidth = (): Expr => ["case", [">", ["get", "cls"], 0], 0.7, 0.5] as unknown as Expr;
