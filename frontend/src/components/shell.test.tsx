// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../state/loader", () => ({
  openAnalysis: vi.fn(async () => {}),
  retry: vi.fn(async () => {}),
  basePathFor: (id: string | null) => (id ? `data/trips/${id}/` : "data/"),
}));

import { openAnalysis, retry } from "../state/loader";
import * as S from "../state/store";
import { makeAnalysis, makeScore } from "../test-fixtures";
import { AboutDialog } from "./AboutDialog";
import { MobileTabs } from "./MobileTabs";
import { ErrorState } from "./StatusViews";
import { TopBar } from "./TopBar";

const trip = { id: "kieleczka", name: "Kieleczka", radius_km: 20, day: "2026-09-29", lat: 50.5, lon: 18.6, saved_at: "2026-09-29T20:00:00" };

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
  vi.mocked(openAnalysis).mockClear();
});

describe("pasek górny", () => {
  it("opisuje bieżącą analizę", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    S.load.value = { status: "ready" };
    render(<TopBar />);
    expect(screen.getByText("Aktualna analiza · 20 km · 30 września 2026")).toBeTruthy();
  });
  it("podczas wczytywania innej analizy nie łączy nazwy nowej z datą poprzedniej", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    S.load.value = { status: "loading" };
    render(<TopBar />);
    expect(screen.getByText("Wczytywanie analizy…")).toBeTruthy();
  });
  it("lista analiz: ukryta bez migawek, wybór otwiera migawkę", () => {
    const { container, rerender } = render(<TopBar />);
    expect(container.querySelector("select")).toBeNull();
    S.trips.value = [trip];
    rerender(<TopBar />);
    fireEvent.change(container.querySelector("select")!, { target: { value: "kieleczka" } });
    expect(openAnalysis).toHaveBeenCalledWith("data/trips/kieleczka/", "kieleczka");
  });
  it("otwiera okno O danych z podziękowaniem za E-OBS", () => {
    render(<><TopBar /><AboutDialog /></>);
    fireEvent.click(screen.getByText("O danych"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText(/We acknowledge the E-OBS dataset/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Zamknij"));
    expect(S.aboutOpen.value).toBe(false);
  });
});

describe("stany i zakładki telefonu", () => {
  it("błąd z ponowną próbą", () => {
    render(<ErrorState message="Nie udało się wczytać scores.json." />);
    expect(screen.getByRole("alert").textContent).toContain("scores.json");
    fireEvent.click(screen.getByText("Spróbuj ponownie"));
    expect(retry).toHaveBeenCalled();
  });
  it("przełącza listę i mapę", () => {
    render(<MobileTabs />);
    fireEvent.click(screen.getByText("Mapa"));
    expect(S.mobilePane.value).toBe("map");
  });
});
