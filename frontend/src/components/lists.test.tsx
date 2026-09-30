// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "../state/store";
import { makeAnalysis, makeRegion, makeScore } from "../test-fixtures";
import { PressureToggle } from "./PressureToggle";
import { RegionList } from "./RegionList";
import { StandList } from "./StandList";
import { Tabs } from "./Tabs";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
});

describe("przełącznik presji", () => {
  it("niedostępny w migawce bez wyników bez presji", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<PressureToggle />);
    expect((screen.getByRole("switch") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText(/starszy eksport/)).toBeTruthy();
  });
  it("wyłączenie zapisuje wybór i przelicza ranking", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regionsNoPressure: [] });
    render(<PressureToggle />);
    fireEvent.click(screen.getByRole("switch"));
    expect(S.pressure.value).toBe(false);
    expect(localStorage.getItem("borowik.pressure.v1")).toBe("off");
  });
});

describe("zakładki i listy", () => {
  it("zakładki pokazują liczebność i przełączają widok", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regions: [makeRegion("region_1", 70, ["A"])] });
    render(<Tabs />);
    expect(screen.getByText("Rejony (1)")).toBeTruthy();
    fireEvent.click(screen.getByText("Wydzielenia (2)"));
    expect(S.tab.value).toBe("stands");
  });
  it("lista rejonów: nazwa, wynik, klik otwiera kartę rejonu", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 76.4, ["A"])] });
    render(<RegionList />);
    expect(screen.getByText("Rejon 1 · Łaziska")).toBeTruthy();
    expect(screen.getByText("76")).toBeTruthy();
    fireEvent.click(screen.getByText("Rejon 1 · Łaziska"));
    expect(S.top.value).toEqual({ kind: "region", regionId: "region_1" });
  });
  it("lista rejonów bez rejonów podpowiada zakładkę Wydzielenia", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    render(<RegionList />);
    expect(screen.getByText(/nie ma rejonów/)).toBeTruthy();
  });
  it("lista wydzieleń: małe ukryte do zaznaczenia, klasa, stronicowanie po 50", () => {
    const scores = Array.from({ length: 60 }, (_, i) => makeScore(`S${String(i).padStart(2, "0")}`, { R: 90 - i * 0.5, area_ha: i === 0 ? 0.2 : 2 }));
    S.analysis.value = makeAnalysis({ scores });
    const { container } = render(<StandList />);
    expect(container.querySelectorAll(".rows li")).toHaveLength(50);
    expect(container.textContent).not.toContain("Oddz.") ; // identyfikatory testowe nie maja adresu lesnego
    expect(screen.getByText(/mniejsze niż 0,5 ha \(1\)/)).toBeTruthy();
    fireEvent.click(screen.getByText("Pokaż więcej (9)"));
    expect(container.querySelectorAll(".rows li")).toHaveLength(59);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(container.querySelectorAll(".rows li")).toHaveLength(50);
    fireEvent.click(container.querySelector(".rows .row")!);
    expect(S.top.value.kind).toBe("stand");
  });
});
