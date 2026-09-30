import { beforeEach, describe, expect, it } from "vitest";
import * as S from "./store";
import { makeAnalysis, makeRegion, makeScore } from "../test-fixtures";

beforeEach(() => S.resetStore());

describe("stos nawigacji", () => {
  it("z listy przybliża; z mapy nie przybliża, zastępuje kartę wydzielenia i przełącza telefon na listę", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")] });
    S.mobilePane.value = "map";
    S.openStand("A", "list");
    expect(S.stack.value.map((v) => v.kind)).toEqual(["list", "stand"]);
    expect(S.fitRequest.value?.req).toEqual({ target: "stand", id: "A" });
    const seq = S.fitRequest.value!.seq;
    S.openStand("B", "map");
    expect(S.stack.value).toEqual([{ kind: "list" }, { kind: "stand", standId: "B" }]);
    expect(S.fitRequest.value!.seq).toBe(seq);
    expect(S.mobilePane.value).toBe("list");
  });
  it("wstecz wraca o poziom i nigdy nie usuwa listy", () => {
    S.openRegion("region_1", "list");
    S.openStand("A", "list");
    S.back();
    expect(S.top.value).toEqual({ kind: "region", regionId: "region_1" });
    S.back();
    S.back();
    expect(S.stack.value).toEqual([{ kind: "list" }]);
  });
  it("zmiana zakładki czyści stos", () => {
    S.openStand("A", "list");
    S.setTab("stands");
    expect(S.tab.value).toBe("stands");
    expect(S.stack.value).toEqual([{ kind: "list" }]);
  });
  it("znacznik rejonu na mapie: zakładka Rejony z kartą rejonu, bez przybliżania", () => {
    S.setTab("stands");
    S.openRegion("region_2", "map");
    expect(S.tab.value).toBe("regions");
    expect(S.stack.value).toEqual([{ kind: "list" }, { kind: "region", regionId: "region_2" }]);
    expect(S.fitRequest.value).toBeNull();
  });
});

describe("presja", () => {
  it("przełączenie zamyka karty rejonów, bo rejony obu wariantów mają te same id", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A", { R: 80, R_bez_presji: 50 }), makeScore("B", { R: 50, R_bez_presji: 80 })],
      regions: [makeRegion("region_1", 70, ["A"])],
      regionsNoPressure: [makeRegion("region_1", 75, ["B"])],
    });
    S.openRegion("region_1", "list");
    S.openStand("A", "list");
    S.setPressure(false);
    expect(S.stack.value.map((v) => v.kind)).toEqual(["list", "stand"]);
    expect(S.regionViews.value[0].members[0].score.stand_id).toBe("B");
  });
  it("ranking i klasy idą za wariantem presji", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A", { R: 80, R_bez_presji: 50 }), makeScore("B", { R: 50, R_bez_presji: 80 })],
      regionsNoPressure: [],
    });
    expect(S.classById.value.get("A")).toBe(1);
    expect(S.classById.value.get("B")).toBe(4);
    S.setPressure(false);
    expect(S.ranked.value[0].score.stand_id).toBe("B");
    expect(S.classById.value.get("A")).toBe(4);
  });
  it("migawka bez wyników bez presji: przełącznik niedostępny, presja zawsze włączona", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    S.setPressure(false);
    expect(S.pressureAvailable.value).toBe(false);
    expect(S.pressure.value).toBe(true);
  });
});

describe("mapa", () => {
  it("Wilgotność bez M w migawce wraca do Wyniku", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A", { M: undefined })] });
    S.setMapMode("moisture");
    expect(S.moistureOk.value).toBe(false);
    expect(S.mapMode.value).toBe("score");
  });
  it("właściwości wydzieleń: klasa 0 poza maską, numer rejonu, wilgotność", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A"), makeScore("C", { mask: false, R: 0, M: 0.3, mask_reason: ["too_young"] })],
      regions: [makeRegion("region_1", 70, ["A"])],
    });
    expect(S.standProps.value.get("A")).toEqual({ cls: 1, moisture: 0.8, pressure: 0.2, region: 1 });
    expect(S.standProps.value.get("C")).toEqual({ cls: 0, moisture: 0.3, pressure: 0.2, region: 0 });
    expect(S.regionMarkers.value).toEqual([{ id: "region_1", number: 1, point: [18.41, 50.61] }]);
  });
  it("featuresFor: wydzielenie, rejon, cały obszar", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regions: [makeRegion("region_1", 70, ["B"])] });
    expect(S.featuresFor({ target: "stand", id: "A" })).toHaveLength(1);
    expect(S.featuresFor({ target: "region", id: "region_1" }).map((f) => f.properties.stand_id)).toEqual(["B"]);
    expect(S.featuresFor({ target: "all" })).toHaveLength(2);
  });
  it("dymek: wynik i klasa albo poza filtrami", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A", { R: 81.2 }), makeScore("C", { mask: false, R: 0 })] });
    expect(S.standTooltip("A")).toMatch(/wynik 81 · najlepsze 5%$/);
    expect(S.standTooltip("C")).toMatch(/poza filtrami modelu$/);
    expect(S.standTooltip("nie-ma")).toBeNull();
  });
});
