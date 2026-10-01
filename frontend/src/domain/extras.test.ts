import { describe, expect, it } from "vitest";
import fixture from "../../../tests/fixtures/klasy_procentowe.json";
import { CLASS_LABELS, classifyByPercentile, regionAreaHa } from "./ranking";
import { analysisLabel, formatDateLong, maskReasonTexts, speciesShort, tooltipText, yearsLabel } from "./labels";
import { barNotes, median, regionBars } from "./bars";
import { joinMeta } from "./format";
import { joinRegions } from "./ranking";
import { makeAnalysis, makeDetail, makeRegion, makeScore } from "../test-fixtures";

describe("classifyByPercentile", () => {
  it("daje te same klasy co eksport KMZ (wspólny przykład z Pythonem)", () => {
    for (const c of fixture.przypadki) expect(classifyByPercentile(c.wartosci)).toEqual(c.klasy);
  });
  it("opisuje klasy słowami", () => {
    expect(CLASS_LABELS[1]).toBe("najlepsze 5%");
    expect(CLASS_LABELS[4]).toBe("pozostałe");
  });
});

describe("pasek rejonu i opisy pod paskami", () => {
  it("rejon: mediana 5 najlepszych wydzieleń", () => {
    const hs = [1, 0.9, 0.8, 0.7, 0.6, 0.1];
    const scores = hs.map((h, i) => makeScore(`S${i}`, { H: h, R: 90 - i * 10 }));
    const a = makeAnalysis({ scores, regions: [makeRegion("region_1", 70, scores.map((s) => s.stand_id))] });
    const [view] = joinRegions(a.regions, a.entries);
    expect(regionBars(view.members, true)[0].value).toBeCloseTo(0.8);
    expect(regionAreaHa(view)).toBe(12);
  });
  it("median", () => {
    expect(median([])).toBeNull();
    expect(median([3, 1, 2])).toBe(2);
    expect(median([1, 2, 3, 4])).toBe(2.5);
  });
  it("opisy: skład, siedlisko, wiek; opad i wilgotność; źródło presji tylko z presją", () => {
    const detail = makeDetail("A", {
      weather: {
        p26_mm: 79.4, cwb26_mm: 9.4, cwb26_typical_mm: -5.6, pct_cwb26: 0.74, tmean20_c: 13.5, temp_optimum_c: 13,
        tmin3_c: 10.4, frost: "brak", frost_date: null, F: 0.82, forecast_days: 1, forecast_window_share: 0,
      },
    });
    const notes = barNotes(makeScore("A", { M: 0.915 }), detail, true);
    expect(notes.habitat).toBe("sosna 100% · Bór mieszany świeży · 64 lata");
    expect(notes.weather).toBe("opad 79 mm / 26 dni · wilgotność 0,92 · 13,5 °C średnio 20 dni");
    expect(notes.calm).toBe("najwięcej presji: parking (2,4 km)");
    expect(barNotes(makeScore("A"), detail, false).calm).toBeUndefined();
    expect(barNotes(makeScore("A", { M: null }), null, true)).toEqual({});
  });
});

describe("etykiety", () => {
  it("powody spoza filtrów", () => {
    expect(maskReasonTexts(["too_young", "gdos"])).toEqual([
      "za młody drzewostan (poniżej progu wieku, obecnie 35 lat)",
      "rezerwat przyrody lub park narodowy (GDOŚ)",
    ]);
    expect(maskReasonTexts([])).toEqual(["powód nieznany w tej analizie"]);
    expect(maskReasonTexts(undefined)).toEqual(["powód nieznany w tej analizie"]);
    expect(maskReasonTexts(["nowy_kod"])).toEqual(["nowy_kod"]);
  });
  it("lata po polsku", () => {
    expect([1, 2, 4, 5, 12, 22, 64, 100, 112].map(yearsLabel)).toEqual([
      "1 rok", "2 lata", "4 lata", "5 lat", "12 lat", "22 lata", "64 lata", "100 lat", "112 lat",
    ]);
  });
  it("skład w skrócie: łączy powtórzone gatunki, pomija udziały śladowe", () => {
    expect(speciesShort([
      { species_cd: "JS", name: "jesion wyniosły", share: "udział 60 %" },
      { species_cd: "LP", name: "lipa drobnolistna", share: "udział 10 %" },
      { species_cd: "LP", name: "lipa drobnolistna", share: "udział 20 %" },
      { species_cd: "JS", name: "jesion wyniosły", share: "udział 10 %" },
      { species_cd: "BK", name: "buk zwyczajny", share: "poniżej 5 % - miejscami" },
    ])).toBe("jesion 70%, lipa 30%");
    expect(speciesShort([])).toBeNull();
  });
  it("daty, opis analizy, dymek, metryka", () => {
    expect(formatDateLong("2026-09-30")).toBe("30 września 2026");
    expect(formatDateLong(null)).toBe("—");
    expect(analysisLabel({ tripName: null, radiusKm: 20, day: "2026-09-30" })).toBe("Aktualna analiza · 20 km · 30 września 2026");
    expect(analysisLabel({ tripName: "Kieleczka", radiusKm: null, day: null })).toBe("Kieleczka");
    expect(tooltipText("Oddz. 96a", 81.1, 1)).toBe("Oddz. 96a · wynik 81 · najlepsze 5%");
    expect(tooltipText("Oddz. 96a", null, 0)).toBe("Oddz. 96a · poza filtrami modelu");
    expect(tooltipText("Oddz. 96a", null, 3)).toBe("Oddz. 96a · brak wyniku");
    expect(joinMeta(["3,9 ha", null, "", false, "8 km"])).toBe("3,9 ha · 8 km");
  });
});
