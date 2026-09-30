import { beforeEach, describe, expect, it, vi } from "vitest";

// Czesciowa atrapa: dane testowe (makeAnalysis) uzywaja prawdziwego buildAnalysis.
vi.mock("../data/load", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../data/load")>()),
  loadCore: vi.fn(),
  loadBackground: vi.fn(),
  loadTrips: vi.fn(async () => []),
}));

import { loadBackground, loadCore, type Background } from "../data/load";
import { openAnalysis, retry } from "./loader";
import * as S from "./store";
import { makeAnalysis, makeDetail, makeScore } from "../test-fixtures";

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const background = (id: string): Background => ({ details: new Map([[id, makeDetail(id)]]), accessPoints: null, forestRoads: null });

beforeEach(() => {
  S.resetStore();
  vi.mocked(loadCore).mockReset();
  vi.mocked(loadBackground).mockReset();
});

describe("openAnalysis", () => {
  it("szczegóły poprzedniej analizy nie nadpisują nowej", async () => {
    const first = makeAnalysis({ scores: [makeScore("A")] });
    const second = { ...makeAnalysis({ scores: [makeScore("B")] }), basePath: "data/trips/x/" };
    let releaseFirst: (value: Background) => void = () => {};
    vi.mocked(loadCore).mockResolvedValueOnce(first).mockResolvedValueOnce(second);
    vi.mocked(loadBackground)
      .mockImplementationOnce(() => new Promise((resolve) => { releaseFirst = resolve; }))
      .mockResolvedValueOnce(background("B"));
    await openAnalysis("data/", null);
    await openAnalysis("data/trips/x/", "x");
    await flush();
    releaseFirst(background("A"));
    await flush();
    expect(S.analysis.value?.basePath).toBe("data/trips/x/");
    expect([...S.details.value!.keys()]).toEqual(["B"]);
    expect(S.access.value.loaded).toBe(true);
  });
  it("błąd pokazuje komunikat; ponowna próba wczytuje tę samą analizę", async () => {
    vi.mocked(loadCore).mockRejectedValueOnce(new Error("Nie udało się wczytać scores.json."));
    await openAnalysis("data/trips/x/", "x");
    expect(S.load.value).toEqual({ status: "error", message: "Nie udało się wczytać scores.json." });
    vi.mocked(loadCore).mockResolvedValueOnce(makeAnalysis({ scores: [makeScore("A")] }));
    vi.mocked(loadBackground).mockResolvedValueOnce(background("A"));
    await retry();
    expect(vi.mocked(loadCore).mock.calls[1][0]).toBe("data/trips/x/");
    expect(S.load.value.status).toBe("ready");
  });
  it("zakładka Rejony bez rejonów przechodzi na Wydzielenia; cały obszar do przybliżenia", async () => {
    vi.mocked(loadCore).mockResolvedValueOnce(makeAnalysis({ scores: [makeScore("A")] }));
    vi.mocked(loadBackground).mockResolvedValueOnce(background("A"));
    await openAnalysis("data/", null);
    expect(S.tab.value).toBe("stands");
    expect(S.fitRequest.value?.req).toEqual({ target: "all" });
  });
});
