// Faza UI: przelacznik presji, paski wyniku, nazwy i fakty karty.
import { describe, expect, it } from "vitest";
import {
  areaLabel,
  conditionBars,
  effectiveR,
  habitatComponents,
  haversineKm,
  joinData,
  joinRegions,
  keyFacts,
  parseData,
  parseStandId,
  pressureSwitchAvailable,
  pressureTop,
  rankEntries,
  regionName,
  scoreBars,
  standName,
  startDistanceLabel,
  weatherComponents,
} from "./model";
import type { AccessCard, ConditionsDay, Region, Score, StandDetail, Stands } from "./model";

const score = (id: string, r: number, rNoPressure: number | undefined, extra: Partial<Score> = {}): Score => ({
  stand_id: id,
  R: r,
  ...(rNoPressure === undefined ? {} : { R_bez_presji: rNoPressure }),
  H: 0.8,
  F: 0.6,
  F_loc: 0.6,
  P: 0.1,
  mask: true,
  confidence: "SREDNIA",
  confidence_reasons: [],
  explanation: [],
  day: "2026-09-24",
  distance_method: "euclidean",
  entrance_status: "not_evaluated",
  ...extra,
});
const stands = (ids: string[]): Stands => ({
  type: "FeatureCollection",
  features: ids.map((id, i) => ({
    type: "Feature",
    properties: { stand_id: id },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [16 + i * 0.01, 53],
          [16.005 + i * 0.01, 53],
          [16.005 + i * 0.01, 53.005],
          [16 + i * 0.01, 53.005],
          [16 + i * 0.01, 53],
        ],
      ],
    },
  })),
});
const region = (id: string, rank: number, standIds: string[]): Region => ({
  region_id: id,
  rank_score: rank,
  stand_count: standIds.length,
  stand_ids: standIds,
  day: "2026-09-24",
  centroid_lat: 53.002,
  centroid_lon: 16.005,
});

describe("Faza UI.1: przełącznik presji", () => {
  // A: wysoki R z presją, ale niski bez presji; B odwrotnie.
  const scores = [score("A", 80, 82), score("B", 60, 95), score("C", 40, 30)];
  const geometry = stands(["A", "B", "C"]);

  it("przy włączonej presji ranking jest identyczny jak dotychczasowy joinData", () => {
    const base = joinData(scores, geometry);
    expect(base.map((e) => e.score.stand_id)).toEqual(["A", "B", "C"]);
    expect(base.map((e) => e.r)).toEqual([80, 60, 40]);
    const again = rankEntries(base, true);
    expect(again.map((e) => e.score.stand_id)).toEqual(base.map((e) => e.score.stand_id));
    expect(again.map((e) => e.r)).toEqual(base.map((e) => e.r));
  });
  it("przełączenie tam i z powrotem przywraca dokładnie ten sam ranking", () => {
    const base = joinData(scores, geometry);
    const back = rankEntries(rankEntries(base, false), true);
    expect(back.map((e) => [e.score.stand_id, e.r])).toEqual(base.map((e) => [e.score.stand_id, e.r]));
  });
  it("bez presji sortuje wg R_bez_presji", () => {
    const off = rankEntries(joinData(scores, geometry), false);
    expect(off.map((e) => e.score.stand_id)).toEqual(["B", "A", "C"]);
    expect(off.map((e) => e.r)).toEqual([95, 82, 30]);
  });
  it("nie awansuje wydzieleń spoza maski i pomija brakujący R_bez_presji", () => {
    const set = [score("A", 80, 99, { mask: false }), score("B", 60, undefined), score("C", 40, 30)];
    const on = joinData(set, geometry);
    expect(on.map((e) => e.score.stand_id)).toEqual(["B", "C"]);
    expect(rankEntries(on, false).map((e) => e.score.stand_id)).toEqual(["C"]);
  });
  it("effectiveR czyta R albo R_bez_presji", () => {
    const s = score("A", 80, 90);
    expect(effectiveR(s, true)).toBe(80);
    expect(effectiveR(s, false)).toBe(90);
    expect(effectiveR(score("A", 80, undefined), false)).toBeNull();
  });
  it("rejony z presją i bez presji wybierają własne najlepsze wydzielenie", () => {
    const base = joinData(scores, geometry);
    const withP = joinRegions([region("r1", 70, ["A", "B"])], base);
    const withoutP = joinRegions([region("r1", 90, ["A", "B"])], rankEntries(base, false));
    expect(withP[0].top.score.stand_id).toBe("A");
    expect(withoutP[0].top.score.stand_id).toBe("B");
    expect(withoutP[0].top.r).toBe(95);
  });
  it("przełącznik jest dostępny tylko z R_bez_presji i drugim zestawem rejonów", () => {
    expect(pressureSwitchAvailable(scores, [])).toBe(true);
    expect(pressureSwitchAvailable(scores, null)).toBe(false); // stara migawka bez regions_bez_presji
    expect(pressureSwitchAvailable([score("A", 80, undefined)], [])).toBe(false);
  });
  it("parseData przyjmuje regions_bez_presji, zostawia null bez pliku i odrzuca obce wydzielenia", () => {
    expect(parseData(scores, geometry, [region("r1", 1, ["A"])]).regionsNoPressure).toBeNull();
    expect(
      parseData(scores, geometry, [region("r1", 1, ["A"])], undefined, [region("r1", 1, ["B"])])
        .regionsNoPressure,
    ).toHaveLength(1);
    expect(() =>
      parseData(scores, geometry, undefined, undefined, [region("r1", 1, ["GHOST"])]),
    ).toThrow(/bez presji/);
  });
  it("R_bez_presji jest opcjonalne, ale jeśli jest, musi być liczbą", () => {
    expect(() => parseData([score("A", 1, undefined)], stands(["A"]))).not.toThrow();
    expect(() =>
      parseData([{ ...score("A", 1, 2), R_bez_presji: "x" as unknown as number }], stands(["A"])),
    ).toThrow();
  });
});

describe("Faza UI.2: paski", () => {
  it("trzy paski w konwencji więcej = lepiej: H, F_loc, 1 − P", () => {
    const bars = scoreBars({ H: 0.72, F_loc: 0.66, P: 0.3 }, true);
    expect(bars.map((b) => b.key)).toEqual(["habitat", "weather", "calm"]);
    expect(bars.map((b) => b.label)).toEqual(["Siedlisko", "Pogoda", "Spokój"]);
    expect(bars[0].value).toBe(0.72);
    expect(bars[1].value).toBe(0.66);
    expect(bars[2].value).toBeCloseTo(0.7);
    expect(bars.every((b) => !b.muted)).toBe(true);
  });
  it("oceny słowne: niskie/średnie/wysokie i klasy pogody", () => {
    const bars = scoreBars({ H: 0.3, F_loc: 0.5, P: 0.9 }, true);
    expect(bars[0].word).toBe("niskie");
    expect(bars[1].word).toBe("dobre");
    expect(bars[2].word).toBe("niski"); // spokój 0,1
    expect(scoreBars({ H: 0.9, F_loc: 0.9, P: 0 }, true)[2].word).toBe("wysoki");
    expect(scoreBars({ H: 0.5, F_loc: 0.1, P: 0.5 }, true).map((b) => b.word)).toEqual([
      "średnie",
      "słabe warunki",
      "średni",
    ]);
  });
  it("przy wyłączonej presji Spokój jest wyszarzony i „nie uwzględniony”", () => {
    const bars = scoreBars({ H: 0.7, F_loc: 0.7, P: 0.3 }, false);
    expect(bars[2].muted).toBe(true);
    expect(bars[2].word).toBe("nie uwzględniony");
    expect(bars[0].muted || bars[1].muted).toBe(false);
  });
  it("brak wartości daje brak danych, bez zmyślonego paska", () => {
    const bars = scoreBars({ H: null, F_loc: null, P: null }, true);
    expect(bars.map((b) => b.value)).toEqual([null, null, null]);
    expect(bars.map((b) => b.word)).toEqual(["brak danych", "brak danych", "brak danych"]);
  });
  it("składniki siedliska: wiek w trybie neutral „nie wpływa na wynik”", () => {
    const rows = habitatComponents({ S_host: 1, S_site: 0.85, S_age: 1, age_mode: "neutral" });
    expect(rows.map((r) => r.label)).toEqual(["Skład drzewostanu", "Typ siedliska", "Wiek drzewostanu"]);
    expect(rows[0].value).toBe("1,00");
    expect(rows[2].note).toBe("nie wpływa na wynik");
    const curve = habitatComponents({ S_host: 1, S_site: 1, S_age: 0.6, age_mode: "curve" });
    expect(curve[2].value).toBe("0,60");
    expect(curve[2].note).toBeUndefined();
    expect(habitatComponents(null)).toEqual([]);
  });
  it("składniki pogody: M, T, K_frost (jeśli eksport je ma)", () => {
    const w = {
      p26_mm: 80, cwb26_mm: 13, cwb26_typical_mm: -6, pct_cwb26: 0.78, tmean20_c: 13.5,
      temp_optimum_c: 13, tmin3_c: 5, frost: "brak" as const, frost_date: null, F: 0.66,
      M: 0.95, T: 0.98, K_frost: 1, forecast_days: 1, forecast_window_share: 0,
    };
    expect(weatherComponents(w).map((r) => [r.label, r.value])).toEqual([
      ["Wilgotność", "0,95"],
      ["Temperatura", "0,98"],
      ["Przymrozek", "1,00"],
    ]);
    expect(weatherComponents({ ...w, M: undefined, T: undefined, K_frost: undefined })).toEqual([]);
  });
  const card = (extra: Partial<AccessCard> = {}): AccessCard => ({
    d_parking_m: 2400,
    d_entrance_m: 2100,
    d_hard_forest_road_m: null,
    top_point_id: "p1",
    top_point_type: "parking",
    top_point_source: "bdl",
    top_point_name: "Łaziska 192n",
    pressure_contrib: { parking: 0.5, entrance: 0.2, gate: 0.1, settlement: 0.15, forest_road: 0.05, road_fallback: 0 },
    ...extra,
  });
  it("Spokój: 2–3 punkty o największym wkładzie, wjazd i szlaban łączone", () => {
    const rows = pressureTop(card());
    expect(rows).toHaveLength(3);
    expect(rows[0]).toEqual({ label: "parking Łaziska 192n", value: "2,4 km", note: "50% presji" });
    expect(rows[1].label).toBe("wjazd lub szlaban");
    expect(rows[1].note).toBe("30% presji");
    expect(rows[2].label).toBe("osiedle");
    expect(rows[2].value).toBe(""); // eksport nie ma odległości do osiedla
  });
  it("Spokój: bez rozbicia wkładu w eksporcie lub przy zerowej presji lista jest pusta", () => {
    expect(pressureTop(null)).toEqual([]);
    expect(pressureTop(card({ pressure_contrib: undefined }))).toEqual([]);
    expect(pressureTop(card({ pressure_contrib: { parking: 0, entrance: 0 } }))).toEqual([]);
  });
});

describe("Faza UI.3: nazwy i fakty", () => {
  it("rozbiera adres leśny na oddział i pododdział", () => {
    expect(parseStandId("02-14-3-11-96 -a -00@2026")).toEqual({
      district: "02-14", forestry: "3", section: "96", subsection: "a",
    });
    expect(parseStandId("02-25-1-05-265   -c   -00@2026")?.section).toBe("265");
    expect(parseStandId("A")).toBeNull();
  });
  it("nazwa wydzielenia: oddział + nadleśnictwo (słownik, potem eksport, potem kod)", () => {
    expect(standName("02-14-3-11-96 -a -00@2026")).toBe("Oddz. 96a · Nadl. Zawadzkie");
    expect(standName("02-16-1-01-5 -b -00@2026")).toBe("Oddz. 5b · Nadl. Koszęcin");
    const detail = { forest_district: "Debica" } as StandDetail;
    expect(standName("03-04-2-10-221   -m   -00@2026", detail)).toBe("Oddz. 221m · Nadl. Debica");
    expect(standName("03-04-2-10-221   -m   -00@2026")).toBe("Oddz. 221m · nadl. 03-04");
    expect(standName("A")).toBe("Wydzielenie A");
  });
  it("nazwa rejonu: numer w rankingu i najbliższa miejscowość, bez odmiany", () => {
    expect(regionName({ ...region("region_4", 50, ["A"]), near_place: { name: "Łaziska", distance_m: 900 } }, 1)).toBe(
      "Rejon 1 · Łaziska",
    );
    expect(regionName(region("region_4", 50, ["A"]), 2)).toBe("Rejon 2");
    expect(regionName({ ...region("region_4", 50, ["A"]), near_place: null }, 3)).toBe("Rejon 3");
  });
  it("odległość od startu i powierzchnia", () => {
    expect(haversineKm([18.6, 50.5], [18.6, 50.5])).toBe(0);
    expect(haversineKm([18.6, 50.0], [18.6, 51.0])).toBeCloseTo(111.2, 0);
    expect(startDistanceLabel([18.6, 50.5], [18.6, 50.6])).toBe("11,1 km od startu");
    expect(startDistanceLabel(null, [18.6, 50.6])).toBeNull();
    expect(areaLabel(3.24)).toBe("3,2 ha");
    expect(areaLabel(42.4)).toBe("42 ha");
    expect(areaLabel(null)).toBeNull();
  });
  it("klucz faktów: do 4 krótkich etykiet", () => {
    const facts = keyFacts(
      { d_parking_m: 620, d_entrance_m: 2100, d_hard_forest_road_m: 300, top_point_id: null, top_point_type: null, top_point_source: null, top_point_name: null },
      3.24,
    );
    expect(facts).toEqual(["parking 620 m", "wjazd 2,1 km", "utwardzony dukt 300 m", "3,2 ha"]);
    expect(keyFacts(null, 5, 1300)).toEqual(["dojście ok. 1,3 km", "5,0 ha"]);
    expect(keyFacts(null, null, null)).toEqual([]);
  });
});

describe("Faza UI.3: słupki 7 dni", () => {
  const day = (i: number, F: number, uncertainty?: "ok" | "uncertain" | "indicative"): ConditionsDay => ({
    date: `2026-09-${String(29 + i).padStart(2, "0")}`.replace("2026-09-3", "2026-10-0"),
    F, level: 2, forecast: i > 0, uncertainty,
  });
  it("wysokość słupka to F, z oznaczeniem niepewności", () => {
    const bars = conditionBars([day(0, 0.66, "ok"), day(4, 0.4, "uncertain"), day(9, 1.4, "indicative")], (d) => d);
    expect(bars.map((b) => b.value)).toEqual([0.66, 0.4, 1]);
    expect(bars.map((b) => b.uncertainty)).toEqual(["ok", "uncertain", "indicative"]);
    expect(bars[0].label).toBe("dziś");
    expect(bars[1].title).toContain("prognoza niepewna");
    expect(bars[2].title).toContain("orientacyjnie");
  });
});
