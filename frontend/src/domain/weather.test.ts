import { describe, expect, it } from "vitest";
import { buildWeatherPanel, dayRangeLabel, daysAgoLabel } from "./weather";
import { DAY, legacyConditions, makeConditions } from "../test-fixtures";

describe("panel pogody — nowy format", () => {
  const m = buildWeatherPanel(makeConditions())!;
  it("nagłówek z samymi faktami", () => {
    expect(m.legacy).toBe(false);
    expect(m.headline).toBe("6 dni po większym deszczu · 60 mm w 26 dni (norma 48)");
  });
  it("trzy liczby", () => {
    expect(m.facts.map((f) => [f.value, f.note])).toEqual([
      ["60 mm", "norma 48 mm"],
      ["6 dni temu", "20–24.09 · 30,7 mm"],
      ["13,7 °C", "optimum ok. 13 °C"],
    ]);
  });
  it("zdanie o normie", () => {
    expect(m.normalLine).toBe("Więcej deszczu niż w 71% lat 1991–2020 o tej porze (E-OBS).");
  });
  it("słupki: 35 dni wstecz + dziś + 6 dni prognozy, okno 26 dni, jeden dzień dzisiejszy", () => {
    expect(m.bars).toHaveLength(42);
    expect(m.bars.filter((b) => b.inWindow)).toHaveLength(26);
    expect(m.bars.findIndex((b) => b.isToday)).toBe(35);
    expect(m.bars[0].kind).toBe("measured");
    expect(m.bars[41].kind).toBe("forecast");
  });
  it("tabela 7 dni i brak ostrzeżeń", () => {
    expect(m.forecast.map((r) => r.label)).toEqual(["dziś", "cz", "pt", "sb", "nd", "pn", "wt"]);
    expect(m.checks).toEqual([
      { label: "bez przymrozku", active: false },
      { label: "bez upału z suszą", active: false },
    ]);
  });
});

describe("panel pogody — warianty", () => {
  it("mniej deszczu niż zwykle", () => {
    const c = makeConditions();
    const m = buildWeatherPanel({ ...c, rain26: { ...c.rain26!, pct: 0.3 } })!;
    expect(m.normalLine).toBe("Mniej deszczu niż w 70% lat 1991–2020 o tej porze (E-OBS).");
  });
  it("bez większego deszczu i bez normy", () => {
    const c = makeConditions();
    const m = buildWeatherPanel({ ...c, rains: [], rain26: { ...c.rain26!, normal_mm: null, pct: null, normal_source: null, normal_cells: 0 } })!;
    expect(m.headline).toBe("Brak większego deszczu od 45 dni · 60 mm w 26 dni");
    expect(m.facts[0].note).toBe("bez normy");
    expect(m.normalLine).toBeNull();
  });
  it("przymrozek w prognozie i dzień bez radaru", () => {
    const c = makeConditions({ warnings: [{ type: "frost", dates: ["2026-10-04"] }, { type: "heat_drought", dates: [] }] });
    c.daily![10] = { ...c.daily![10], radar_share: 0 };
    const m = buildWeatherPanel(c)!;
    expect(m.checks[0]).toEqual({ label: "Przymrozek: 4.10", active: true });
    expect(m.bars[10].kind).toBe("model");
  });
  it("stara migawka: zdanie o deszczu i temperatura, bez wykresu", () => {
    const m = buildWeatherPanel(legacyConditions())!;
    expect(m.legacy).toBe(true);
    expect(m.headline).toContain("Ostatni większy deszcz");
    expect(m.bars).toEqual([]);
    expect(m.facts.map((f) => f.value)).toEqual(["13,7 °C"]);
  });
  it("brak pliku warunków", () => {
    expect(buildWeatherPanel(null)).toBeNull();
  });
});

describe("pomocnicze", () => {
  it("zakres dni i dni temu", () => {
    expect(dayRangeLabel("2026-09-20", "2026-09-24")).toBe("20–24.09");
    expect(dayRangeLabel("2026-09-20", "2026-09-20")).toBe("20.09");
    expect(dayRangeLabel("2026-09-30", "2026-10-02")).toBe("30.09–2.10");
    expect([0, 1, 6].map(daysAgoLabel)).toEqual(["dziś", "wczoraj", "6 dni temu"]);
    expect(DAY).toBe("2026-09-30");
  });
});
