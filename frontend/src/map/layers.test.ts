import { expression, latest } from "@maplibre/maplibre-gl-style-spec";
import { describe, expect, it } from "vitest";
import {
  CLASS_COLORS, buildStandCollection, changedStates, moistureFillColor, regionOutlineOpacity, scoreFillColor, standLineOpacity,
} from "./layers";
import { squareFeature } from "../test-fixtures";

describe("warstwy mapy", () => {
  it("geometria niesie tylko stałe właściwości; klasa i rejon idą przez stan obiektu", () => {
    const fc = buildStandCollection(
      [squareFeature("A", 0), squareFeature("B", 1)],
      new Map([["A", { cls: 2, moisture: 0.5, pressure: 0.1, region: 3 }]]),
    );
    expect(fc.features[0].properties).toEqual({ stand_id: "A", mask: 1, moisture: 0.5, pressure: 0.1 });
    expect(fc.features[1].properties).toEqual({ stand_id: "B", mask: 0, moisture: null, pressure: null });
  });
  it("zmienione stany: tylko wydzielenia, którym zmieniła się klasa albo rejon", () => {
    const previous = new Map([["A", { cls: 1 as const, region: 1 }], ["B", { cls: 4 as const, region: 0 }]]);
    const next = new Map([
      ["A", { cls: 1 as const, moisture: 0.5, pressure: 0.1, region: 1 }],
      ["B", { cls: 2 as const, moisture: 0.5, pressure: 0.1, region: 0 }],
      ["C", { cls: 0 as const, moisture: null, pressure: null, region: 0 }],
    ]);
    expect(changedStates(previous, next)).toEqual([["B", { cls: 2, region: 0 }], ["C", { cls: 0, region: 0 }]]);
  });
  it("wynik: cztery kolory klas ze stanu obiektu, poza filtrami przezroczyste", () => {
    const expr = JSON.stringify(scoreFillColor());
    for (const c of [1, 2, 3, 4] as const) expect(expr).toContain(CLASS_COLORS[c]);
    expect(expr).toContain("feature-state");
    expect(expr).toContain("rgba(0,0,0,0)");
    expect(JSON.stringify(regionOutlineOpacity())).toContain("feature-state");
  });
  it("wilgotność: skala bezwzględna i kolor braku danych", () => {
    const expr = JSON.stringify(moistureFillColor());
    expect(expr).toContain("interpolate");
    expect(expr).toContain("#cfd2c6");
  });
  it("kontury wydzieleń: niewidoczne w widoku całego obszaru, pełne po przybliżeniu na las", () => {
    const e = expression.createPropertyExpression(standLineOpacity() as never, latest.paint_line["line-opacity"] as never);
    if (e.result !== "success") throw new Error("niepoprawne wyrażenie MapLibre");
    const at = (zoom: number) => e.value.evaluate({ zoom } as never);
    expect([10, 12].map(at)).toEqual([0, 0]);
    expect(at(13)).toBeGreaterThan(0);
    expect(at(13)).toBeLessThan(1);
    expect([14, 16].map(at)).toEqual([1, 1]);
  });
});
