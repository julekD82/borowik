import { useState } from "preact/hooks";
import { mapMode, moistureOk, requestFitAll, setMapMode } from "../state/store";
import { Icon } from "./icons";
import { LayersPopover } from "./LayersPopover";

export function MapControls() {
  const [open, setOpen] = useState(false);
  return (
    <div class="map-controls">
      <div class="segmented" role="group" aria-label="Kolory mapy">
        <button type="button" aria-pressed={mapMode.value === "score"} onClick={() => setMapMode("score")}>Wynik</button>
        <button
          type="button"
          aria-pressed={mapMode.value === "moisture"}
          disabled={!moistureOk.value}
          title={moistureOk.value ? undefined : "Ta analiza nie ma danych o wilgotności."}
          onClick={() => setMapMode("moisture")}
        >
          Wilgotność
        </button>
      </div>
      <button type="button" class="map-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="layers" />Warstwy
      </button>
      <button type="button" class="map-button" aria-label="Pokaż cały obszar" onClick={requestFitAll}>
        <Icon name="target" />
      </button>
      {open && <LayersPopover onClose={() => setOpen(false)} />}
    </div>
  );
}
