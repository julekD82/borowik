import { MOISTURE_LEGEND_NOTE, MOISTURE_LEGEND_TICKS, MOISTURE_STOPS, moistureTickLabel } from "../domain/moisture";
import { CLASS_LABELS } from "../domain/ranking";
import { CLASS_COLORS } from "../map/layers";
import { mapMode, pressure } from "../state/store";

export function Legend() {
  if (mapMode.value === "moisture") {
    const gradient = `linear-gradient(90deg, ${MOISTURE_STOPS.map(([v, c]) => `${c} ${v * 100}%`).join(", ")})`;
    return (
      <div class="legend">
        <strong>Wilgotność (model)</strong>
        <div class="gradient" style={{ background: gradient }} />
        <div class="ticks">{MOISTURE_LEGEND_TICKS.map((t) => <span>{moistureTickLabel(t)}</span>)}</div>
        <p class="legend-note">{MOISTURE_LEGEND_NOTE}</p>
      </div>
    );
  }
  return (
    <div class="legend">
      <strong>{pressure.value ? "Wynik" : "Wynik bez presji"}</strong>
      <ul>
        {([1, 2, 3, 4] as const).map((c) => (
          <li><i style={{ background: CLASS_COLORS[c] }} />{CLASS_LABELS[c]}</li>
        ))}
        <li><i class="outline" />poza filtrami modelu</li>
        <li><i class="region" />rejon</li>
      </ul>
    </div>
  );
}
