import { describe, expect, it, vi } from "vitest";
import {
  fruitingClass,
  joinData,
  joinRegions,
  topExplanations,
  navigationUrl,
  distanceLabel,
  zakazNote,
  parseData,
  isStandaloneTarget,
  MIN_STANDALONE_AREA_HA,
  standStructureLabel,
  densityLabel,
  neighborsSummary,
  parseTrips,
  formatTripLabel,
  parseConditions,
  dayLabel,
  loadData,
} from "./model";
import { readSaved, saveRegion } from "./storage";
import type { Score, Stands, Region, StandDetail, TripMeta } from "./model";

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
  it("accepts an optional rain_radar_coverage field and still loads without it", () => {
    const scores = [
      { ...score("A", 40), rain_radar_coverage: 0.93 },
      score("B", 30), // no rain_radar_coverage -- older export
    ];
    const result = parseData(scores, stands);
    expect(result.scores.map((s) => s.rain_radar_coverage)).toEqual([0.93, undefined]);
  });
  it("rejects a malformed rain_radar_coverage instead of silently accepting it", () => {
    expect(() =>
      parseData(
        [{ ...score("A", 40), rain_radar_coverage: "not-a-number" }, score("B", 30)],
        stands,
      ),
    ).toThrow();
  });
  it("rejects a malformed tie_break instead of silently accepting it", () => {
    expect(() =>
      parseData(
        [{ ...score("A", 40), tie_break: "not-a-number" }, score("B", 30)],
        stands,
      ),
    ).toThrow();
  });
  describe("joinData tie_break secondary sort", () => {
    it("prefers the higher tie_break when R rounds to the same value at 2 decimals", () => {
      // A has the higher RAW R (50.004 > 50.001) but the lower tie_break --
      // both round to 50.00, so a plain (unrounded) R sort would already
      // put A first without tie_break mattering at all. Swapping which
      // side has the higher tie_break proves tie_break is what decides
      // the order, not leftover precision in R itself.
      const entries = joinData(
        [
          { ...score("A", 50.004), tie_break: 0.2 },
          { ...score("B", 50.001), tie_break: 0.9 },
        ],
        stands,
      );
      expect(entries.map((e) => e.score.stand_id)).toEqual(["B", "A"]);
    });

    it("falls back to stand_id when tie_break is absent on both sides (older export)", () => {
      const entries = joinData([score("B", 50.0), score("A", 50.0)], stands);
      expect(entries.map((e) => e.score.stand_id)).toEqual(["A", "B"]);
    });
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
    veg_cover: "zadarniona",
    standdensity_index: 0.9,
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
  it("parseData accepts a details entry from an older export missing veg_cover/standdensity_index", () => {
    const scores = [score("A", 40), score("B", 30)];
    const older = detail("A") as Partial<StandDetail>;
    delete older.veg_cover;
    delete older.standdensity_index;
    const result = parseData(scores, stands, undefined, [older]);
    expect(result.details[0].veg_cover).toBeUndefined();
    expect(result.details[0].standdensity_index).toBeUndefined();
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
  it("parseData round-trips veg_cover and standdensity_index, and accepts them null without package coverage", () => {
    const scores = [score("A", 40), score("B", 30)];
    const result = parseData(scores, stands, undefined, [detail("A")]);
    expect(result.details[0].veg_cover).toBe("zadarniona");
    expect(result.details[0].standdensity_index).toBe(0.9);

    const noPackage = detail("B", { veg_cover: null, standdensity_index: null });
    const result2 = parseData(scores, stands, undefined, [noPackage]);
    expect(result2.details[0].veg_cover).toBeNull();
    expect(result2.details[0].standdensity_index).toBeNull();
  });
  it("parseData rejects a malformed veg_cover or standdensity_index", () => {
    const scores = [score("A", 40), score("B", 30)];
    expect(() =>
      parseData(scores, stands, undefined, [
        { ...detail("A"), veg_cover: 42 },
      ]),
    ).toThrow();
    expect(() =>
      parseData(scores, stands, undefined, [
        { ...detail("A"), standdensity_index: "0.9" },
      ]),
    ).toThrow();
  });
  it("parseData accepts a details entry from an older export missing searchability_hint (plan 1.6.5)", () => {
    const scores = [score("A", 40), score("B", 30)];
    const older = detail("A") as Partial<StandDetail>;
    delete older.searchability_hint;
    const result = parseData(scores, stands, undefined, [older]);
    expect(result.details[0].searchability_hint).toBeUndefined();
  });
  it("parseData round-trips searchability_hint, null included", () => {
    const scores = [score("A", 40), score("B", 30)];
    const withHint = detail("A", { searchability_hint: "Obecny podszyt — może utrudniać poruszanie się." });
    const result = parseData(scores, stands, undefined, [withHint]);
    expect(result.details[0].searchability_hint).toBe("Obecny podszyt — może utrudniać poruszanie się.");

    const withoutHint = detail("B", { searchability_hint: null });
    const result2 = parseData(scores, stands, undefined, [withoutHint]);
    expect(result2.details[0].searchability_hint).toBeNull();
  });
  it("parseData rejects a malformed searchability_hint", () => {
    const scores = [score("A", 40), score("B", 30)];
    expect(() =>
      parseData(scores, stands, undefined, [
        { ...detail("A"), searchability_hint: 42 },
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

const trip = (overrides: Partial<TripMeta> = {}): TripMeta => ({
  id: "bedziemysl-2026-09-26",
  name: "Będziemyśl",
  radius_km: 20,
  day: "2026-09-26",
  lat: 50.0555,
  lon: 21.7889,
  saved_at: "2026-09-26T18:04:12+02:00",
  ...overrides,
});

describe("saved trips", () => {
  it("formats a trip as name - radius - short date", () => {
    expect(formatTripLabel(trip())).toBe("Będziemyśl - 20km - 26.09");
  });
  it("parses a well-formed trips list", () => {
    expect(parseTrips([trip()])).toEqual([trip()]);
  });
  it("returns an empty list for a non-array payload", () => {
    expect(parseTrips({ not: "an array" })).toEqual([]);
    expect(parseTrips(null)).toEqual([]);
  });
  it("filters out entries missing required fields, keeping valid ones", () => {
    const bad = { ...trip(), id: undefined };
    expect(parseTrips([trip(), bad])).toEqual([trip()]);
  });
  it("filters out an entry with a malformed day", () => {
    const bad = trip({ day: "26-09-2026" });
    expect(parseTrips([bad])).toEqual([]);
  });
  it("filters out an entry with a non-finite radius or coordinate", () => {
    expect(parseTrips([trip({ radius_km: NaN })])).toEqual([]);
    expect(parseTrips([trip({ lat: Infinity })])).toEqual([]);
  });
});

describe("conditions timeline", () => {
  const conditions = (over: Record<string, unknown> = {}) => ({
    day: "2026-09-27",
    generated_for: "2026-09-27",
    horizon_days: 7,
    pulse_min_mm: 15.0,
    rains: [],
    summary: "Ostatni większy deszcz: 21–22.09 (28.5 mm), 5 dni temu",
    days: [{ date: "2026-09-27", F: 0.803, level: 3, forecast: false }],
    ...over,
  });
  it("returns null when conditions.json is absent", () => {
    expect(parseConditions(undefined, "2026-09-27")).toBeNull();
  });
  it("accepts a valid same-day timeline", () => {
    expect(parseConditions(conditions(), "2026-09-27")?.summary).toContain("deszcz");
  });
  it("rejects another day's timeline or malformed tiles", () => {
    expect(() => parseConditions(conditions(), "2026-09-26")).toThrow();
    expect(() =>
      parseConditions(conditions({ days: [{ date: "2026-09-27", F: 0.8, level: 7, forecast: false }] }), "2026-09-27"),
    ).toThrow();
  });
  it("labels today and Polish weekdays", () => {
    expect(dayLabel("2026-09-27", 0)).toBe("dziś");
    expect(dayLabel("2026-09-28", 1)).toBe("pn");
    expect(dayLabel("2026-10-03", 6)).toBe("sb");
  });
});

describe("loadData against a dev-server SPA fallback for missing optional files", () => {
  // Review finding (Critical #1): Vite's dev-server html-fallback middleware
  // answers a GET for a genuinely missing file (any missing file, not just
  // conditions.json -- e.g. a saved trip made before regions/details/
  // conditions existed) with 200 text/html (index.html), not 404. A naive
  // `response.ok` check then treats that as "the file exists" and .json()
  // throws, turning an optional, normally-absent file into a fatal load
  // error for the WHOLE map, not just its own section.
  function jsonResponse(body: unknown) {
    return {
      ok: true,
      headers: new Headers({ "content-type": "application/json; charset=utf-8" }),
      json: async () => body,
    } as unknown as Response;
  }
  function htmlFallbackResponse() {
    return {
      ok: true,
      headers: new Headers({ "content-type": "text/html" }),
      json: async () => {
        throw new SyntaxError("Unexpected token '<'");
      },
    } as unknown as Response;
  }
  const scoresBody = [score("A", 40), score("B", 30)];

  it("treats a 200 text/html response for regions/details/conditions as absent, not a fatal error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: unknown) => {
        const url = String(input);
        if (url.includes("scores.json")) return jsonResponse(scoresBody);
        if (url.includes("stands.geojson")) return jsonResponse(stands);
        // regions.json / details.json / conditions.json: genuinely absent,
        // but the dev server answers as if they were present.
        return htmlFallbackResponse();
      }),
    );
    const data = await loadData();
    expect(data.regions).toEqual([]);
    expect(data.details).toEqual([]);
    expect(data.conditions).toBeNull();
    vi.unstubAllGlobals();
  });
});

describe("zakazNote", () => {
  it("returns a discrete notice for nie_sprawdzono and blad", () => {
    expect(zakazNote("nie_sprawdzono")).toContain("nie sprawdzono");
    expect(zakazNote("blad")).toContain("nie powiodło się");
  });
  it("returns a notice for an active zakaz", () => {
    expect(zakazNote("zakaz")).toContain("Wykryto zakaz");
  });
  it("returns an empty string for brak or an undefined/unknown value", () => {
    expect(zakazNote("brak")).toBe("");
    expect(zakazNote(undefined)).toBe("");
    expect(zakazNote("cos_innego")).toBe("");
  });
});

// Faza 3.5: warstwy punktow dostepu i karta wydzielenia.
import {
  ACCESS_LAYERS,
  accessCardSummary,
  distanceMethod as distanceMethodF3,
  parseAccessCollection,
  pointTypeLabel,
  roadKindLabel,
  surfaceLabel,
  topPointSummary,
} from "./model";

describe("access layers (Faza 3.5)", () => {
  it("offers a legend toggle for parkings, entrances, roads, fire roads, settlements and P", () => {
    const ids = ACCESS_LAYERS.map((l) => l.id);
    expect(ids).toEqual(["parkings", "entrances", "roads", "fire", "settlements", "pressure"]);
    // gesta warstwa pozarowa, osiedla i P domyslnie wylaczone
    const off = ACCESS_LAYERS.filter((l) => !l.defaultOn).map((l) => l.id);
    expect(off).toEqual(["fire", "settlements", "pressure"]);
  });
  it("parses an access collection, treats absence as null and rejects garbage", () => {
    expect(parseAccessCollection(undefined, "x.json")).toBeNull();
    const fc = { type: "FeatureCollection", features: [] };
    expect(parseAccessCollection(fc, "x.json")).toEqual(fc);
    expect(() => parseAccessCollection({ type: "Feature" }, "x.json")).toThrow(/x\.json/);
    expect(() => parseAccessCollection("nope", "x.json")).toThrow();
  });
  it("summarises the card as nearest parking / entrance / paved forest road", () => {
    const text = accessCardSummary({
      d_parking_m: 854,
      d_entrance_m: 402,
      d_hard_forest_road_m: null,
      top_point_id: "pk-bdl-1",
      top_point_type: "parking",
      top_point_source: "bdl",
      top_point_name: "Leśna",
    });
    expect(text).toContain("najbliższy parking 850 m");
    expect(text).toContain("wjazd lub szlaban 400 m");
    expect(text).toContain("utwardzony dukt brak w pobliżu");
    expect(accessCardSummary(null)).toBe("");
  });
  it("names the top contributing point, or says no point reaches the stand", () => {
    const base = {
      d_parking_m: 1, d_entrance_m: 1, d_hard_forest_road_m: 1,
      top_point_id: "pk-1", top_point_type: "parking", top_point_source: "bdl", top_point_name: "Leśna",
    };
    expect(topPointSummary(base)).toContain("parking „Leśna” (BDL)");
    expect(topPointSummary({ ...base, top_point_id: null })).toContain("P = 0");
  });
  it("labels types, surfaces, road kinds and the new distance method in Polish", () => {
    expect(pointTypeLabel("gate")).toBe("Szlaban");
    expect(surfaceLabel("hard")).toBe("twarda");
    expect(surfaceLabel("zzz")).toBe("nieznana");
    expect(roadKindLabel("closed")).toBe("zamknięta droga leśna");
    expect(roadKindLabel("public")).toBe("droga publiczna");
    expect(distanceMethodF3("access_points")).toContain("punktów dostępu");
  });
});

describe("attractivenessClass", () => {
  it("classifies from the exported number and tolerates absence", async () => {
    const { attractivenessClass } = await import("./model");
    expect(attractivenessClass(0.05)).toBe("niska");
    expect(attractivenessClass(0.2)).toBe("średnia");
    expect(attractivenessClass(0.5)).toBe("wysoka");
    expect(attractivenessClass(null)).toBeNull();
    expect(attractivenessClass(undefined)).toBeNull();
  });
});

describe("rankColorStops", () => {
  it("pins the 6 colours to percentiles of R in this analysis, strictly increasing", async () => {
    const { rankColorStops, RANK_COLORS } = await import("./model");
    // dane skupione w 35-65, jak w prawdziwej analizie: stare stale progi 0/35/65/100 dawaly jeden zielony
    const values = Array.from({ length: 200 }, (_, i) => 35 + (30 * i) / 199);
    const stops = rankColorStops(values);
    expect(stops.map((s) => s[1])).toEqual(RANK_COLORS);
    for (let i = 1; i < stops.length; i++) expect(stops[i][0]).toBeGreaterThan(stops[i - 1][0]);
    expect(stops[0][0]).toBeGreaterThanOrEqual(35);
    expect(stops[5][0]).toBeLessThanOrEqual(65);
    expect(stops[2][0]).toBeCloseTo(50, 0); // mediana
  });
  it("ignores zero (masked) and null values", async () => {
    const { rankColorStops } = await import("./model");
    const withJunk = [0, 0, null, undefined, NaN, ...Array.from({ length: 50 }, (_, i) => 40 + i)];
    const clean = Array.from({ length: 50 }, (_, i) => 40 + i);
    expect(rankColorStops(withJunk)).toEqual(rankColorStops(clean));
  });
  it("falls back to a fixed 0-100 scale for empty or constant data and never repeats a stop", async () => {
    const { rankColorStops } = await import("./model");
    for (const values of [[], [0, 0], [50], [50, 50, 50]]) {
      const stops = rankColorStops(values);
      expect(stops).toHaveLength(6);
      for (let i = 1; i < stops.length; i++) expect(stops[i][0]).toBeGreaterThan(stops[i - 1][0]);
    }
  });
});

describe("regionAccessSummary", () => {
  const card = (parking: number | null, entrance: number | null, road: number | null, id: string | null = "pk-1") => ({
    d_parking_m: parking,
    d_entrance_m: entrance,
    d_hard_forest_road_m: road,
    top_point_id: id,
    top_point_type: id ? "parking" : null,
    top_point_source: id ? "bdl" : null,
    top_point_name: id ? "Rytwiny 148h" : null,
  });
  it("shows min-max and median over ALL stands of the region, not one stand's distance", async () => {
    const { regionAccessSummary } = await import("./model");
    const s = regionAccessSummary([card(795, 400, 300), card(1485, 1000, 900), card(2095, 1890, 2250)])!;
    expect(s.distances).toContain("najbliższy parking od 800 m do 2100 m (mediana 1490 m)");
    expect(s.distances).toContain("wjazd lub szlaban od 400 m do 1890 m (mediana 1000 m)");
    expect(s.distances).toContain("utwardzony dukt od 300 m do 2250 m (mediana 900 m)");
    expect(s.top).toContain("w 3 z 3 wydzieleń");
    expect(s.top).toContain("parking „Rytwiny 148h” (BDL)");
  });
  it("collapses equal values, skips nulls, and picks the most frequent top point", async () => {
    const { regionAccessSummary } = await import("./model");
    const s = regionAccessSummary([card(500, null, null, "a"), card(500, null, null, "b"), card(500, null, null, "b")])!;
    expect(s.distances).toContain("najbliższy parking 500 m ·");
    expect(s.distances).toContain("wjazd lub szlaban brak w pobliżu");
    expect(s.top).toContain("w 2 z 3 wydzieleń");
  });
  it("returns null without cards and says P = 0 when no stand has a top point", async () => {
    const { regionAccessSummary } = await import("./model");
    expect(regionAccessSummary([])).toBeNull();
    expect(regionAccessSummary([card(900, 900, 900, null)])!.top).toContain("P = 0");
  });
});
