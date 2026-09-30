import { analysisLabel } from "../domain/labels";
import { aboutOpen, analysis, tripId, trips } from "../state/store";
import { AnalysisPicker } from "./AnalysisPicker";
import { Icon } from "./icons";

export function TopBar() {
  const a = analysis.value;
  const trip = trips.value.find((t) => t.id === tripId.value) ?? null;
  const label = a
    ? analysisLabel({ tripName: trip?.name ?? null, radiusKm: a.manifest.radius_km ?? trip?.radius_km ?? null, day: a.day || null })
    : "Wczytywanie analizy…";
  return (
    <header class="topbar">
      <a class="brand" href="./"><Icon name="mushroom" /><span>Borowik</span></a>
      <p class="topbar-context">{label}</p>
      <AnalysisPicker />
      <button type="button" class="link-button" onClick={() => { aboutOpen.value = true; }}>
        <Icon name="info" />O danych
      </button>
    </header>
  );
}
