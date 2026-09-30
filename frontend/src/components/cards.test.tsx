// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { act } from "preact/test-utils";
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "../state/store";
import { makeAnalysis, makeDetail, makeRegion, makeScore } from "../test-fixtures";
import { RegionCard } from "./RegionCard";
import { Sidebar } from "./Sidebar";
import { StandCard } from "./StandCard";

const ID = "02-14-3-11-96    -a   -00@2026";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
});

describe("karta wydzielenia", () => {
  it("w modelu: nazwa, miejsce w rankingu, wynik, paski z opisami, drzewostan, dojazd, dane", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore(ID, { R: 81.1 }), makeScore("B", { R: 40 })], regionsNoPressure: [] });
    S.details.value = new Map([[ID, makeDetail(ID)]]);
    S.stack.value = [{ kind: "list" }, { kind: "stand", standId: ID }];
    const { container } = render(<StandCard standId={ID} />);
    expect(screen.getByText("Oddz. 96a · Nadl. Zawadzkie")).toBeTruthy();
    expect(container.textContent).toContain("#1 z 2");
    expect(container.querySelector(".score-badge strong")?.textContent).toBe("81");
    expect(screen.getByText("sosna 100% · Bór mieszany świeży · 64 lata")).toBeTruthy();
    expect(screen.getByText("Bór mieszany świeży (BMSW)")).toBeTruthy();
    expect(screen.getByText("parking 2,4 km")).toBeTruthy();
    expect(container.textContent).toContain("leśnictwo 3 · oddział 96 · pododdział a");
    expect(screen.getByRole("link", { name: /Nawiguj/ }).getAttribute("href")).toMatch(/^https:\/\/www\.google\.com\/maps\?q=/);
  });
  it("szczegóły jeszcze się wczytują", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore(ID)] });
    render(<StandCard standId={ID} />);
    expect(screen.getAllByText("Wczytuję szczegóły…").length).toBeGreaterThan(0);
  });
  it("poza filtrami: powody zamiast pasków", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("C", { mask: false, R: 0, mask_reason: ["too_young", "gdos"] })] });
    S.details.value = new Map();
    const { container } = render(<StandCard standId="C" />);
    expect(screen.getByText("Nie spełnia filtrów modelu")).toBeTruthy();
    expect(screen.getByText("za młody drzewostan (młodnik)")).toBeTruthy();
    expect(container.querySelector(".bars")).toBeNull();
    expect(screen.getByText("Brak szczegółów dla tego wydzielenia.")).toBeTruthy();
  });
  it("w masce, ale bez wyniku w wariancie bez presji: brak wyniku, nie „powód nieznany”", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A"), makeScore("B", { R_bez_presji: null })],
      regionsNoPressure: [],
    });
    S.setPressure(false);
    render(<StandCard standId="B" />);
    expect(screen.getByText("Brak wyniku dla tego wydzielenia w tej analizie.")).toBeTruthy();
    expect(screen.queryByText("powód nieznany w tej analizie")).toBeNull();
  });
  it("wstecz wraca do listy", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore(ID)] });
    S.stack.value = [{ kind: "list" }, { kind: "stand", standId: ID }];
    render(<StandCard standId={ID} />);
    fireEvent.click(screen.getByText("Wróć"));
    expect(S.stack.value).toEqual([{ kind: "list" }]);
  });
});

describe("karta rejonu", () => {
  it("wynik rejonu, paski z mediany 5 najlepszych, lista wydzieleń otwiera kartę", () => {
    const scores = [1, 0.9, 0.8, 0.7, 0.6, 0.1].map((h, i) => makeScore(`S${i}`, { H: h, R: 90 - i * 10 }));
    S.analysis.value = makeAnalysis({ scores, regions: [makeRegion("region_1", 76.4, scores.map((s) => s.stand_id))] });
    S.details.value = new Map();
    S.stack.value = [{ kind: "list" }, { kind: "region", regionId: "region_1" }];
    const { container } = render(<RegionCard regionId="region_1" />);
    expect(screen.getByText("Rejon 1 · Łaziska")).toBeTruthy();
    expect(container.querySelector(".score-badge strong")?.textContent).toBe("76");
    expect(container.querySelector(".bar-habitat .bar-word")?.textContent).toContain("0,80");
    expect(container.querySelectorAll(".rows li")).toHaveLength(6);
    fireEvent.click(container.querySelector(".rows .row")!);
    expect(S.top.value).toEqual({ kind: "stand", standId: "S0" });
  });
  it("nieistniejący rejon (np. po zmianie migawki) nie wysypuje karty", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<RegionCard regionId="region_9" />);
    expect(screen.getByText(/Nie ma już tego rejonu/)).toBeTruthy();
  });
});

describe("panel boczny", () => {
  it("wczytywanie, błąd, lista, karta z wierzchu stosu", () => {
    const { rerender } = render(<Sidebar />);
    expect(screen.getByText("Wczytuję analizę…")).toBeTruthy();
    S.load.value = { status: "error", message: "Brak scores.json." };
    rerender(<Sidebar />);
    expect(screen.getByRole("alert").textContent).toContain("Brak scores.json.");
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 70, ["A"])] });
    S.load.value = { status: "ready" };
    rerender(<Sidebar />);
    expect(screen.getByText("Rejon 1 · Łaziska")).toBeTruthy();
    // Zmiana sygnalu poza zdarzeniem: act() wymusza odswiezenie komponentow potomnych.
    act(() => S.openRegion("region_1", "list"));
    expect(screen.getByText("Wydzielenia w rejonie (1)")).toBeTruthy();
  });
  it("przejście do karty przewija panel na górę", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 70, ["A"])] });
    S.load.value = { status: "ready" };
    const { container } = render(<Sidebar />);
    const aside = container.querySelector("aside")!;
    aside.scrollTop = 500;
    act(() => S.openRegion("region_1", "list"));
    expect(aside.scrollTop).toBe(0);
  });
});
