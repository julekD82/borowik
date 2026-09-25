import { describe, expect, it } from "vitest";
import {
  fruitingClass,
  joinData,
  joinRegions,
  topExplanations,
  navigationUrl,
  distanceLabel,
  parseData,
  isStandaloneTarget,
  MIN_STANDALONE_AREA_HA,
  standStructureLabel,
  densityLabel,
  neighborsSummary,
} from "./model";
import { readSaved, saveRegion } from "./storage";
import type { Score, Stands, Region, StandDetail } from "./model";

describe("stand detail labels", () => {
  it("expands stand structure codes, with or without diacritics", () => {
    expect(standStructureLabel("DRZEW")).toBe("jednopiętrowy");
    expect(standStructureLabel("2 PIĘT")).toBe("dwupiętrowy");
    expect(standStructureLabel("2 PIET")).toBe("dwupiętrowy");
    expect(standStructureLabel("KO")).toBe("klasa odnowienia (KO)");
    expect(standStructureLabel("XYZ")).toBe("XYZ");
  });
  it("adds the scale to numeric density and leaves descriptive density alone", () => {
    expect(densityLabel("0.9")).toBe("0.9 (skala 0–1)");
    expect(densityLabel("1.0")).toBe("1.0 (skala 0–1)");
    expect(densityLabel("umiarkowane")).toBe("umiarkowane");
    expect(densityLabel(null)).toBe("brak danych");
  });
  it("tells no-data apart from only-similar neighbours", () => {
    expect(neighborsSummary(undefined)).toBe("brak danych o sąsiedztwie");
    expect(neighborsSummary([])).toMatch(/^tylko podobne drzewostany/);
    expect(neighborsSummary(["zrąb"])).toBeNull();
  });
});

const score = (id: string, r: number, mask = true): Score => ({
  stand_id: id,
  R: r,
  H: 0.8,
  F: 0.6,
  F_loc: 0.6,
  P: 0.1,
  mask,
  confidence: "SREDNIA",
  confidence_reasons: [],
  explanation: [],
  day: "2026-09-24",
  distance_method: "euclidean",
  entrance_status: "not_evaluated",
});
const stands: Stands = {
  type: "FeatureCollection",
  features: ["A", "B"].map((id, i) => ({
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
};

describe("data and classification", () => {
  it.each([
    [0, "Słabe warunki"],
    [0.199, "Słabe warunki"],
    [0.2, "Umiarkowane"],
    [0.45, "Dobre"],
    [0.7, "Bardzo dobre"],
    [1, "Bardzo dobre"],
    [null, "Brak danych"],
    [NaN, "Brak danych"],
  ])("classifies %s", (value, label) =>
    expect(fruitingClass(value as number | null)).toBe(label),
  );
  it("joins by exact identifiers and chooses the highest eligible R", () => {
    const result = joinData([score("B", 80), score("A", 40)], stands);
    expect(result[0].score.stand_id).toBe("B");
    expect(result.map((e) => e.score.stand_id)).toEqual(["B", "A"]);
    expect(result[0].feature.properties.stand_id).toBe("B");
    expect(result[0].point[0]).toBeGreaterThan(16.01);
  });
  it("never promotes a masked stand or silently drops missing members", () => {
    expect(
      joinData([score("A", 99, false), score("B", 40)], stands)[0].score
        .stand_id,
    ).toBe("B");
    expect(() => joinData([score("A", 40)], stands)).toThrow(/zestaw/);
  });
  it("retains low/zero ranks, sorts ties deterministically and excludes missing ranks", () => {
    expect(
      joinData([score("B", 0), score("A", 0)], stands).map(
        (e) => e.score.stand_id,
      ),
    ).toEqual(["A", "B"]);
    expect(
      joinData([{ ...score("A", 40), R: null }, score("B", 20)], stands).map(
        (e) => e.score.stand_id,
      ),
    ).toEqual(["B"]);
  });
  it("accepts an optional G_season field and still loads without it", () => {
    const scores = [
      { ...score("A", 40), G_season: 0.42 },
      score("B", 30), // no G_season -- older export
    ];
    const result = parseData(scores, stands);
    expect(result.scores.map((s) => s.G_season)).toEqual([0.42, undefined]);
  });
  it("rejects a malformed G_season instead of silently accepting it", () => {
    expect(() =>
      parseData(
        [{ ...score("A", 40), G_season: "not-a-number" }, score("B", 30)],
        stands,
      ),
    ).toThrow();
  });
  it("rejects mixed dates and malformed data", () => {
    expect(() =>
      parseData(
        [{ ...score("A", 40), day: "2026-09-23" }, score("B", 30)],
        stands,
      ),
    ).toThrow(/dat/);
    expect(() => parseData({}, stands)).toThrow();
    expect(() =>
      parseData([score("A", 40), score("B", 30)], {
        type: "FeatureCollection",
        features: [],
      }),
    ).toThrow();
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
  it("joins regions to their member stands and picks the highest-R member as top", () => {
    const entries = joinData([score("A", 40), score("B", 80)], stands);
    const result = joinRegions([region("region_1", 50, ["A", "B"])], entries);
    expect(result).toHaveLength(1);
    expect(result[0].top.score.stand_id).toBe("B");
    expect(result[0].members.map((m) => m.score.stand_id).sort()).toEqual([
      "A",
      "B",
    ]);
  });
  it("sorts regions by rank_score, drops a region whose members are all missing", () => {
    const entries = joinData([score("A", 40), score("B", 80)], stands);
    const result = joinRegions(
      [
        region("low", 10, ["A"]),
        region("high", 90, ["B"]),
        region("ghost", 99, ["MISSING"]),
      ],
      entries,
    );
    expect(result.map((r) => r.region.region_id)).toEqual(["high", "low"]);
  });
  it("keeps a region whose members are only partly present", () => {
    // B has a geometry (so joinData's own consistency check is satisfied)
    // but fails the mask, so joinData excludes it from entries -- the
    // region still references it.
    const entries = joinData([score("A", 40), score("B", 20, false)], stands);
    const result = joinRegions([region("r", 10, ["A", "B"])], entries);
    expect(result[0].members.map((m) => m.score.stand_id)).toEqual(["A"]);
  });
  it("parseData accepts a missing regions argument and an empty regions array", () => {
    const scores = [score("A", 40), score("B", 30)];
    expect(parseData(scores, stands).regions).toEqual([]);
    expect(parseData(scores, stands, []).regions).toEqual([]);
  });
  it("parseData validates a provided regions array against the same day and known stand_ids", () => {
    const scores = [score("A", 40), score("B", 30)];
    const result = parseData(scores, stands, [region("r", 10, ["A"])]);
    expect(result.regions).toHaveLength(1);
    expect(() =>
      parseData(scores, stands, [
        { ...region("r", 10, ["A"]), day: "2026-09-23" },
      ]),
    ).toThrow(/dat/);
    expect(() =>
      parseData(scores, stands, [region("r", 10, ["GHOST"])]),
    ).toThrow();
    expect(() => parseData(scores, stands, "not an array")).toThrow();
  });
  it("selects strongest explanations without mutating input", () => {
    const items = [0.1, -0.7, 0.5].map((contribution) => ({
      factor: "host",
      text: "tekst",
      contribution,
    }));
    expect(topExplanations(items).map((x) => x.contribution)).toEqual([
      -0.7, 0.5,
    ]);
    expect(items[0].contribution).toBe(0.1);
  });
  it("uses latitude before longitude in navigation and validates coordinates", () => {
    expect(navigationUrl([16.7, 53.1])).toBe(
      "https://www.google.com/maps?q=53.1,16.7",
    );
    expect(() => navigationUrl([NaN, 53])).toThrow();
  });
  it("distinguishes zero distance from missing distance", () => {
    expect(distanceLabel(undefined)).toBe("Brak danych");
    expect(distanceLabel(0)).toBe("0 m");
    expect(distanceLabel(1250)).toBe("1,3 km");
  });
  it("isStandaloneTarget hides small stands but not unknown-area ones (plan 2.1 step A4)", () => {
    expect(isStandaloneTarget(score("A", 40))).toBe(true); // no area_ha field at all
    expect(isStandaloneTarget({ ...score("A", 40), area_ha: null })).toBe(
      true,
    );
    expect(isStandaloneTarget({ ...score("A", 40), area_ha: 0.1 })).toBe(
      false,
    );
    expect(
      isStandaloneTarget({
        ...score("A", 40),
        area_ha: MIN_STANDALONE_AREA_HA,
      }),
    ).toBe(true); // boundary is inclusive
    expect(isStandaloneTarget({ ...score("A", 40), area_ha: 5 })).toBe(true);
  });
  const detail = (
    standId: string,
    overrides: Partial<StandDetail> = {},
  ): StandDetail => ({
    stand_id: standId,
    day: "2026-09-24",
    drzew_species: [{ species_cd: "SO", name: "sosna zwyczajna", share: "udział 70 %" }],
    density: "0.7",
    podszyt_species: [],
    soil_type: "brunatna wyługowana",
    package_date: "2026-06-23",
    neighbors: ["zrąb"],
    stand_stru: "DRZEW",
    prot_categ: null,
    ...overrides,
  });
  it("parseData accepts a missing details argument and an empty details array (plan 2.1 step B3)", () => {
    const scores = [score("A", 40), score("B", 30)];
    expect(parseData(scores, stands).details).toEqual([]);
    expect(parseData(scores, stands, undefined, []).details).toEqual([]);
  });
  it("parseData validates a provided details array against the same day and known stand_ids", () => {
    const scores = [score("A", 40), score("B", 30)];
    const result = parseData(scores, stands, undefined, [detail("A")]);
    expect(result.details).toHaveLength(1);
    expect(() =>
      parseData(scores, stands, undefined, [
        { ...detail("A"), day: "2026-09-23" },
      ]),
    ).toThrow(/dat/);
    expect(() =>
      parseData(scores, stands, undefined, [detail("GHOST")]),
    ).toThrow();
    expect(() =>
      parseData(scores, stands, undefined, "not an array"),
    ).toThrow();
  });
  it("parseData accepts a stand's details with empty package fields but real neighbours/stand_stru (no package coverage)", () => {
    const scores = [score("A", 40), score("B", 30)];
    const noPackage = detail("B", {
      drzew_species: [],
      density: null,
      podszyt_species: [],
      soil_type: null,
      package_date: null,
      stand_stru: null,
    });
    const result = parseData(scores, stands, undefined, [noPackage]);
    expect(result.details[0].drzew_species).toEqual([]);
    expect(result.details[0].neighbors).toEqual(["zrąb"]);
  });
  it("parseData rejects a malformed details entry", () => {
    const scores = [score("A", 40), score("B", 30)];
    expect(() =>
      parseData(scores, stands, undefined, [
        { ...detail("A"), drzew_species: [{ species_cd: "SO" }] },
      ]),
    ).toThrow();
    expect(() =>
      parseData(scores, stands, undefined, [
        { ...detail("A"), neighbors: "zrąb" },
      ]),
    ).toThrow();
  });
  it("parseData accepts scores without area_ha (older exports) and validates it when present", () => {
    const scores = [score("A", 40), score("B", 30)];
    expect(parseData(scores, stands).scores[0].area_ha).toBeUndefined();
    expect(
      parseData(
        [{ ...score("A", 40), area_ha: 0.3 }, score("B", 30)],
        stands,
      ).scores[0].area_ha,
    ).toBe(0.3);
    expect(() =>
      parseData(
        [
          { ...score("A", 40), area_ha: "big" as unknown as number },
          score("B", 30),
        ],
        stands,
      ),
    ).toThrow();
  });
});

describe("saved regions", () => {
  const memory = () => {
    const data = new Map<string, string>();
    return {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => {
        data.set(k, v);
      },
    };
  };
  it("round-trips a summary, updates the same place, keeps different locations with reused ids", () => {
    const store = memory();
    const item = {
      key: "one",
      title: "Rejon 1",
      day: "2026-09-24",
      point: [16.7, 53.1] as [number, number],
      reasons: ["Las"],
      conditions: "Dobre",
      savedAt: "2026-09-24T10:00:00Z",
    };
    saveRegion(store, item);
    saveRegion(store, { ...item, title: "Nowa nazwa" });
    saveRegion(store, { ...item, key: "two", point: [18, 50] });
    expect(readSaved(store)).toHaveLength(2);
    expect(readSaved(store).find((r) => r.key === "one")?.title).toBe(
      "Nowa nazwa",
    );
  });
  it("handles corrupt storage without crashing", () => {
    expect(readSaved({ getItem: () => "{broken" })).toEqual([]);
    expect(
      readSaved({ getItem: () => '{"version":1,"regions":[{}]}' }),
    ).toEqual([]);
  });
});
