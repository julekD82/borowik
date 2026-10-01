// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it } from "vitest";
import * as S from "../state/store";
import { legacyConditions, makeAnalysis, makeConditions, makeScore } from "../test-fixtures";
import { WeatherPanel } from "./WeatherPanel";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
});

describe("panel pogody", () => {
  it("nowa analiza: nagłówek, liczby, norma, wykres; szczegóły po rozwinięciu", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], conditions: makeConditions() });
    const { container } = render(<WeatherPanel />);
    expect(screen.getByText("6 dni po większym deszczu · 60 mm w 26 dni (norma 48)")).toBeTruthy();
    expect(screen.getByText("Więcej deszczu niż w 71% lat 1991–2020 o tej porze (E-OBS).")).toBeTruthy();
    expect(container.querySelectorAll(".rain-chart rect[class^='bar-']")).toHaveLength(42);
    expect(container.querySelector(".forecast")).toBeNull();
    fireEvent.click(screen.getByText("Szczegóły: temperatura, prognoza"));
    expect(container.querySelectorAll(".forecast tbody tr")).toHaveLength(7);
    expect(container.querySelector(".temp-band")).not.toBeNull();
    expect(screen.getByText("bez przymrozku")).toBeTruthy();
  });
  it("ostrzeżenie widać też po zwinięciu", () => {
    S.analysis.value = makeAnalysis({
      scores: [makeScore("A")],
      conditions: makeConditions({ warnings: [{ type: "frost", dates: ["2026-10-04"] }, { type: "heat_drought", dates: [] }] }),
    });
    render(<WeatherPanel />);
    expect(screen.getByText("Przymrozek: 4.10")).toBeTruthy();
  });
  it("stara migawka: zdanie o deszczu, bez wykresu i bez rozwijania", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")], conditions: legacyConditions() });
    const { container } = render(<WeatherPanel />);
    expect(screen.getByText(/Ostatni większy deszcz: 20–24.09/)).toBeTruthy();
    expect(container.querySelector(".rain-chart")).toBeNull();
    expect(screen.queryByText("Szczegóły: temperatura, prognoza")).toBeNull();
  });
  it("bez pliku warunków nic nie pokazuje", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    const { container } = render(<WeatherPanel />);
    expect(container.innerHTML).toBe("");
  });
});
