import { load, tab, top } from "../state/store";
import { PressureToggle } from "./PressureToggle";
import { RegionCard } from "./RegionCard";
import { RegionList } from "./RegionList";
import { StandCard } from "./StandCard";
import { StandList } from "./StandList";
import { ErrorState, LoadingState } from "./StatusViews";
import { Tabs } from "./Tabs";
import { WeatherPanel } from "./WeatherPanel";

function PanelBody() {
  const view = top.value;
  if (view.kind === "stand") return <StandCard standId={view.standId} />;
  if (view.kind === "region") return <RegionCard regionId={view.regionId} />;
  return tab.value === "regions" ? <RegionList /> : <StandList />;
}

export function Sidebar() {
  const state = load.value;
  return (
    <aside class="sidebar" aria-label="Panel analizy">
      {state.status === "loading" ? (
        <LoadingState />
      ) : state.status === "error" ? (
        <ErrorState message={state.message} />
      ) : (
        <>
          <WeatherPanel />
          <PressureToggle />
          <Tabs />
          <PanelBody />
          <p class="sidebar-note">
            Model ekspercki, nieskalibrowany. Wynik porównuje miejsca w tej analizie; to nie jest prawdopodobieństwo znalezienia grzybów.
          </p>
        </>
      )}
    </aside>
  );
}
