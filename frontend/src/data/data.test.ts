import { afterEach, describe, expect, it, vi } from "vitest";
import { buildAnalysis, fetchJson, loadBackground } from "./load";
import { parseConditions, parseData, parseDetails, parseManifest } from "./parse";
import { DAY, legacyConditions, makeAnalysis, makeConditions, makeDetail, makeScore, makeStands } from "../test-fixtures";

const json = (body: unknown) =>
  ({ ok: true, headers: new Headers({ "content-type": "application/json" }), json: async () => body }) as unknown as Response;
const html = () =>
  ({ ok: true, headers: new Headers({ "content-type": "text/html" }), json: async () => { throw new SyntaxError("<"); } }) as unknown as Response;
const missing = () => ({ ok: false, headers: new Headers(), json: async () => null }) as unknown as Response;

afterEach(() => vi.unstubAllGlobals());

describe("parseData — nowe i opcjonalne pola wyników", () => {
  it("przyjmuje wyniki bez confidence/explanation i uzupełnia wartości domyślne", () => {
    const bare = { ...makeScore("A") } as Record<string, unknown>;
    delete bare.confidence;
    delete bare.confidence_reasons;
    delete bare.explanation;
    const { scores } = parseData([bare], makeStands(["A"]));
    expect(scores[0].confidence).toBe("");
    expect(scores[0].explanation).toEqual([]);
  });
  it("sprawdza mask_reason: lista tekstów albo brak", () => {
    expect(parseData([makeScore("A", { mask: false, mask_reason: ["too_young"] })], makeStands(["A"])).scores[0].mask_reason)
      .toEqual(["too_young"]);
    expect(() => parseData([{ ...makeScore("A"), mask_reason: "x" }], makeStands(["A"]))).toThrow();
  });
});

describe("parseDetails", () => {
  const ids = new Set(["A"]);
  it("pusty wynik bez pliku, typ siedliska i wiek z pliku", () => {
    expect(parseDetails(undefined, DAY, ids)).toEqual([]);
    const [d] = parseDetails([makeDetail("A")], DAY, ids);
    expect(d.site_type?.label).toBe("Bór mieszany świeży");
    expect(d.age_years).toBe(64);
  });
  it("przyjmuje szczegóły ze starszego eksportu bez site_type i age_years", () => {
    const old = { ...makeDetail("A") } as Record<string, unknown>;
    delete old.site_type;
    delete old.age_years;
    expect(parseDetails([old], DAY, ids)).toHaveLength(1);
  });
  it("odrzuca zły typ siedliska, obce wydzielenie i inną datę", () => {
    expect(() => parseDetails([makeDetail("A", { site_type: { code: 1 } as never })], DAY, ids)).toThrow();
    expect(() => parseDetails([makeDetail("B")], DAY, ids)).toThrow();
    expect(() => parseDetails([makeDetail("A", { day: "2026-09-29" })], DAY, ids)).toThrow();
  });
});

describe("parseConditions — pola panelu pogody", () => {
  it("przyjmuje nowy i stary format", () => {
    expect(parseConditions(makeConditions(), DAY)?.rain26?.normal_mm).toBe(48);
    expect(parseConditions(legacyConditions(), DAY)?.daily).toBeUndefined();
  });
  it("odrzuca zły wiersz daily, rain26 bez sumy i złe ostrzeżenie", () => {
    const bad = makeConditions();
    expect(() => parseConditions({ ...bad, daily: [{ date: DAY }] }, DAY)).toThrow();
    expect(() => parseConditions({ ...bad, rain26: { ...bad.rain26!, sum_mm: null } }, DAY)).toThrow();
    expect(() => parseConditions({ ...bad, warnings: [{ type: "frost", dates: ["wczoraj"] }] }, DAY)).toThrow();
  });
  it("przyjmuje rain26 bez normy", () => {
    const c = makeConditions();
    const noNormal = { ...c, rain26: { ...c.rain26!, normal_mm: null, pct: null, normal_source: null, normal_cells: 0 } };
    expect(parseConditions(noNormal, DAY)?.rain26?.normal_mm).toBeNull();
  });
});

describe("parseManifest", () => {
  it("toleruje brak pliku i złe wartości", () => {
    expect(parseManifest(undefined)).toEqual({ lat: null, lon: null, radius_km: null, day: null, pressure_alpha: null });
    expect(parseManifest({ lat: 50.6, lon: "x", radius_km: 20, day: DAY }).lon).toBeNull();
  });
});

describe("fetchJson", () => {
  it("plik opcjonalny: strona HTML lub 404 to brak pliku", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => html()));
    expect(await fetchJson("data/", "regions.json", false)).toBeUndefined();
    vi.stubGlobal("fetch", vi.fn(async () => missing()));
    expect(await fetchJson("data/", "regions.json", false)).toBeUndefined();
  });
  it("plik wymagany: brak albo niepoprawna treść to czytelny błąd", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => missing()));
    await expect(fetchJson("data/", "scores.json", true)).rejects.toThrow("Nie udało się wczytać scores.json");
    vi.stubGlobal("fetch", vi.fn(async () => html()));
    await expect(fetchJson("data/", "scores.json", true)).rejects.toThrow("niepoprawny");
  });
});

describe("buildAnalysis i loadBackground", () => {
  it("buduje mapy wyników i geometrii oraz ranking wydzieleń w masce", () => {
    const a = makeAnalysis({ scores: [makeScore("A", { R: 50 }), makeScore("B", { R: 70 }), makeScore("C", { mask: false, R: 0 })] });
    expect(a.day).toBe(DAY);
    expect(a.scoreById.size).toBe(3);
    expect(a.features.has("C")).toBe(true);
    expect(a.entries.map((e) => e.score.stand_id)).toEqual(["B", "A"]);
    expect(a.manifest.radius_km).toBe(20);
  });
  it("wczytuje szczegóły i warstwy w tle; brak pliku szczegółów to pusta mapa", async () => {
    const a = buildAnalysis({ basePath: "data/", scoresRaw: [makeScore("A")], standsRaw: makeStands(["A"]) });
    vi.stubGlobal("fetch", vi.fn(async (url: unknown) => (String(url).includes("details.json") ? json([makeDetail("A")]) : html())));
    const bg = await loadBackground(a);
    expect(bg.details.get("A")?.age_years).toBe(64);
    expect(bg.accessPoints).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => html()));
    expect((await loadBackground(a)).details.size).toBe(0);
  });
});
