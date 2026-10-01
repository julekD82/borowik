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

// Klasa i numer rejonu zaleza od przelacznika presji -- trafiaja do mapy jako stan obiektu
// (feature-state), zeby przelaczenie nie wysylalo od nowa calej geometrii (ok. 23 MB).
export type StandState = { cls: ScoreClass | 0; region: number };

/** Geometria ze stalymi wlasciwosciami (nie zaleza od presji): maska, wilgotnosc, presja P. */
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
          mask: (p?.cls ?? 0) > 0 ? 1 : 0,
          moisture: p?.moisture ?? null,
          pressure: p?.pressure ?? null,
        },
      };
    }),
  };
}

/** Wydzielenia, ktorym zmienila sie klasa albo rejon (tylko te dostaja nowy stan obiektu). */
export function changedStates(
  previous: Map<string, StandState>,
  props: Map<string, StandMapProps>,
): [string, StandState][] {
  const changes: [string, StandState][] = [];
  for (const [id, p] of props) {
    const old = previous.get(id);
    if (!old || old.cls !== p.cls || old.region !== p.region) changes.push([id, { cls: p.cls, region: p.region }]);
  }
  return changes;
}

const cls = ["coalesce", ["feature-state", "cls"], 0];
const inMask = ["==", ["get", "mask"], 1];

export const scoreFillColor = (): Expr =>
  ["match", cls, 1, CLASS_COLORS[1], 2, CLASS_COLORS[2], 3, CLASS_COLORS[3], 4, CLASS_COLORS[4], "rgba(0,0,0,0)"] as unknown as Expr;
export const scoreFillOpacity = (): Expr => ["match", cls, 1, 0.85, 2, 0.8, 3, 0.7, 4, 0.45, 0] as unknown as Expr;
export const moistureFillColor = (): Expr =>
  [
    "case",
    ["==", ["typeof", ["get", "moisture"]], "number"],
    ["interpolate", ["linear"], ["get", "moisture"], ...MOISTURE_STOPS.flat()],
    MOISTURE_NO_DATA_COLOR,
  ] as unknown as Expr;
export const moistureFillOpacity = (): Expr => ["case", inMask, 0.8, 0.35] as unknown as Expr;
export const lineColor = (): Expr => ["case", inMask, "#fffef5", OUTSIDE_LINE_COLOR] as unknown as Expr;
export const lineWidth = (): Expr => ["case", inMask, 0.7, 0.5] as unknown as Expr;
// Kontury wydzielen dopiero po przyblizeniu na las: w widoku calego obszaru (zoom ok. 10)
// tysiace bialych linii przyslanialy klasy; od 12 do 14 stopniowo sie pojawiaja.
export const standLineOpacity = (): Expr => ["interpolate", ["linear"], ["zoom"], 12, 0, 14, 1] as unknown as Expr;
export const regionOutlineOpacity = (): Expr =>
  ["case", [">", ["coalesce", ["feature-state", "region"], 0], 0], 0.85, 0] as unknown as Expr;
