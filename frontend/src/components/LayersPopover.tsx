import { ACCESS_LAYERS, SURFACE_COLORS, SURFACE_LABELS } from "../domain/access";
import { access, layers, setLayer } from "../state/store";
import { Icon } from "./icons";

export function LayersPopover({ onClose }: { onClose: () => void }) {
  const state = access.value;
  const available = ACCESS_LAYERS.filter((l) => l.needs === "stands" || (l.needs === "points" ? state.points : state.roads));
  return (
    <div class="popover" role="dialog" aria-label="Warstwy mapy">
      <div class="popover-head">
        <strong>Warstwy</strong>
        <button type="button" class="icon-button" aria-label="Zamknij warstwy" onClick={onClose}><Icon name="close" /></button>
      </div>
      {!state.loaded ? (
        <p class="muted small">Wczytuję warstwy…</p>
      ) : (
        <ul class="layer-list">
          {available.map((l) => (
            <li>
              <label>
                <input
                  type="checkbox"
                  checked={layers.value[l.id]}
                  onChange={(event) => setLayer(l.id, (event.currentTarget as HTMLInputElement).checked)}
                />
                {l.label}
              </label>
            </li>
          ))}
        </ul>
      )}
      {state.loaded && (state.points || state.roads) && (
        <div class="layer-legend">
          <span class="key"><i class="dot" style={{ background: "#1f4e9c" }} />parking (BDL)</span>
          <span class="key"><i class="dot" style={{ background: "#5b8ec9" }} />parking (OSM)</span>
          <span class="key"><i class="dot" style={{ background: "#2a8f7a" }} />wjazd do lasu</span>
          <span class="key"><i class="dot" style={{ background: "#c0392b" }} />szlaban</span>
          {Object.keys(SURFACE_COLORS).map((k) => (
            <span class="key"><i style={{ background: SURFACE_COLORS[k] }} />droga: {SURFACE_LABELS[k]}</span>
          ))}
          <span>Linia ciągła — droga publiczna, przerywana — zamknięta droga leśna; grubość — atrakcyjność.</span>
        </div>
      )}
    </div>
  );
}
