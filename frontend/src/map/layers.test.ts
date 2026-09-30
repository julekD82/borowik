import { describe, expect, it } from "vitest";
import { CLASS_COLORS, buildStandCollection, moistureFillColor, scoreFillColor } from "./layers";
import { squareFeature } from "../test-fixtures";

describe("warstwy mapy", () => {
  it("łączy geometrię z właściwościami; brak właściwości = poza filtrami", () => {
    const fc = buildStandCollection(
      [squareFeature("A", 0), squareFeature("B", 1)],
      new Map([["A", { cls: 2, moisture: 0.5, pressure: 0.1, region: 3 }]]),
    );
    expect(fc.features[0].properties).toEqual({ stand_id: "A", cls: 2, moisture: 0.5, pressure: 0.1, region: 3 });
    expect(fc.features[1].properties).toEqual({ stand_id: "B", cls: 0, moisture: null, pressure: null, region: 0 });
  });
  it("wynik: cztery kolory klas, poza filtrami przezroczyste", () => {
    const expr = JSON.stringify(scoreFillColor());
    for (const c of [1, 2, 3, 4] as const) expect(expr).toContain(CLASS_COLORS[c]);
    expect(expr).toContain("rgba(0,0,0,0)");
  });
  it("wilgotność: skala bezwzględna i kolor braku danych", () => {
    const expr = JSON.stringify(moistureFillColor());
    expect(expr).toContain("interpolate");
    expect(expr).toContain("#cfd2c6");
  });
});
