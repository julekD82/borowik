import type { Position } from "geojson";
import type { StandFeature } from "../data/types";

export function vertices(feature: StandFeature): Position[] {
  return feature.geometry.type === "Polygon"
    ? feature.geometry.coordinates.flat()
    : feature.geometry.coordinates.flat(2);
}

// Polygon area-weighted centroid. This is an approximate geographic centroid,
// deliberately never described as an entrance or a car-accessible destination.
export function standCentroid(feature: StandFeature): [number, number] {
  const polygons =
    feature.geometry.type === "Polygon"
      ? [feature.geometry.coordinates]
      : feature.geometry.coordinates;
  let sumX = 0,
    sumY = 0,
    totalArea = 0;
  for (const polygon of polygons)
    for (const [ringIndex, ring] of polygon.entries()) {
      let crossSum = 0,
        x = 0,
        y = 0;
      for (let i = 0; i < ring.length - 1; i++) {
        const [ax, ay] = ring[i],
          [bx, by] = ring[i + 1];
        const cross = ax * by - bx * ay;
        crossSum += cross;
        x += (ax + bx) * cross;
        y += (ay + by) * cross;
      }
      if (Math.abs(crossSum) < 1e-14) continue;
      const weight = Math.abs(crossSum) * (ringIndex === 0 ? 1 : -1);
      sumX += (x / (3 * crossSum)) * weight;
      sumY += (y / (3 * crossSum)) * weight;
      totalArea += weight;
    }
  if (totalArea > 0) return [sumX / totalArea, sumY / totalArea];
  const points = vertices(feature);
  return [
    points.reduce((s, p) => s + p[0], 0) / points.length,
    points.reduce((s, p) => s + p[1], 0) / points.length,
  ];
}
