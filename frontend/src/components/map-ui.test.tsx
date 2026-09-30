// @vitest-environment jsdom
import { act } from "preact/test-utils";
import { fireEvent, render, screen } from "@testing-library/preact";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ maps: [] as { handlers: Record<string, (id: string) => unknown>; calls: Record<string, unknown[][]> }[] }));

vi.mock("../map/forestMap", () => ({
  ForestMap: class {
    handlers: Record<string, (id: string) => unknown>;
    calls: Record<string, unknown[][]> = {};
    constructor(_container: HTMLElement, handlers: Record<string, (id: string) => unknown>) {
      this.handlers = handlers;
      mocks.maps.push(this);
    }
    private record(name: string, args: unknown[]) {
      (this.calls[name] ??= []).push(args);
    }
    setStands(...args: unknown[]) { this.record("setStands", args); }
    setMode(...args: unknown[]) { this.record("setMode", args); }
    setRegions(...args: unknown[]) { this.record("setRegions", args); }
    setSelection(...args: unknown[]) { this.record("setSelection", args); }
    setAccessData(...args: unknown[]) { this.record("setAccessData", args); }
    setLayerVisible(...args: unknown[]) { this.record("setLayerVisible", args); }
    fitFeatures(...args: unknown[]) { this.record("fitFeatures", args); }
    resize() { this.record("resize", []); }
    destroy() { this.record("destroy", []); }
  },
}));

import * as S from "../state/store";
import { makeAnalysis, makeRegion, makeScore } from "../test-fixtures";
import { App } from "./App";
import { Legend } from "./Legend";
import { MapControls } from "./MapControls";
import { MapView } from "./MapView";

beforeEach(() => {
  localStorage.clear();
  S.resetStore();
  mocks.maps.length = 0;
});

describe("mapa w interfejsie", () => {
  it("przekazuje wydzielenia do mapy; kliknięcie wydzielenia otwiera kartę bez przybliżania", () => {
    render(<MapView />);
    const map = mocks.maps[0];
    act(() => {
      S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regionsNoPressure: [] });
    });
    const [features, props] = map.calls.setStands.at(-1)! as [unknown[], Map<string, unknown>];
    expect(features).toHaveLength(2);
    expect(props.get("A")).toMatchObject({ cls: 1 });
    act(() => { map.handlers.onStandClick("B"); });
    expect(S.top.value).toEqual({ kind: "stand", standId: "B" });
    expect(map.calls.fitFeatures ?? []).toHaveLength(0);
    expect(map.handlers.tooltip("A")).toMatch(/wynik 60/);
  });
  it("przybliża tylko na żądanie, nie po przełączeniu presji", () => {
    render(<MapView />);
    const map = mocks.maps[0];
    act(() => {
      S.analysis.value = makeAnalysis({ scores: [makeScore("A"), makeScore("B")], regionsNoPressure: [] });
      S.requestFitAll();
    });
    const fits = map.calls.fitFeatures.length;
    act(() => S.setPressure(false));
    expect(map.calls.fitFeatures).toHaveLength(fits);
  });
  it("znacznik rejonu otwiera kartę rejonu", () => {
    render(<MapView />);
    act(() => {
      S.analysis.value = makeAnalysis({ scores: [makeScore("A")], regions: [makeRegion("region_1", 70, ["A"])] });
    });
    act(() => { mocks.maps[0].handlers.onRegionClick("region_1"); });
    expect(S.top.value).toEqual({ kind: "region", regionId: "region_1" });
  });
});

describe("kontrolki i legenda", () => {
  it("Wilgotność nieaktywna bez M; wybór zapamiętany", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A", { M: undefined })] });
    const { rerender } = render(<MapControls />);
    expect((screen.getByText("Wilgotność") as HTMLButtonElement).disabled).toBe(true);
    act(() => { S.analysis.value = makeAnalysis({ scores: [makeScore("A")] }); });
    rerender(<MapControls />);
    fireEvent.click(screen.getByText("Wilgotność"));
    expect(S.mapMode.value).toBe("moisture");
    expect(localStorage.getItem("borowik.map-color.v1")).toBe("moisture");
  });
  it("warstwy: lista dostępnych, przełączenie zapamiętane", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    S.access.value = { loaded: true, points: { type: "FeatureCollection", features: [] }, roads: null };
    render(<MapControls />);
    fireEvent.click(screen.getByText("Warstwy"));
    expect(screen.getByText("Parkingi")).toBeTruthy();
    expect(screen.queryByText("Drogi leśne")).toBeNull();
    fireEvent.click(screen.getByLabelText("Osiedla przy lesie"));
    expect(S.layers.value.settlements).toBe(true);
    expect(JSON.parse(localStorage.getItem("borowik.access-layers.v1")!).settlements).toBe(true);
  });
  it("legenda: klasy albo skala wilgotności", () => {
    S.analysis.value = makeAnalysis({ scores: [makeScore("A")] });
    const { rerender } = render(<Legend />);
    expect(screen.getByText("najlepsze 5%")).toBeTruthy();
    act(() => S.setMapMode("moisture"));
    rerender(<Legend />);
    expect(screen.getByText("Wilgotność (model)")).toBeTruthy();
  });
  it("cała aplikacja montuje jedną mapę i pokazuje wczytywanie", () => {
    render(<App />);
    expect(mocks.maps).toHaveLength(1);
    expect(screen.getByText("Wczytuję analizę…")).toBeTruthy();
  });
});
