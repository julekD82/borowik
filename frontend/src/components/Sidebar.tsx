import { useEffect, useRef } from "preact/hooks";
import { load, tab, top, type PanelView } from "../state/store";
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
  const view = top.value;
  const panel = useRef<HTMLElement>(null);
  // Przewiniecie zapamietane dla kazdego widoku stosu: „Wroc” (ten sam obiekt widoku) wraca
  // na swoje miejsce, nowy widok (karta, inna zakladka, klik na mapie) zaczyna od gory.
  const scrolled = useRef(new WeakMap<PanelView, number>());
  useEffect(() => {
    if (panel.current) panel.current.scrollTop = scrolled.current.get(view) ?? 0;
  }, [view]);
  return (
    <aside
      ref={panel}
      class="sidebar"
      aria-label="Panel analizy"
      onScroll={(event) => scrolled.current.set(top.peek(), (event.currentTarget as HTMLElement).scrollTop)}
    >
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
