import { mobilePane } from "../state/store";
import { Icon } from "./icons";

export function MobileTabs() {
  return (
    <div class="mobile-tabs" role="tablist" aria-label="Widok">
      <button type="button" role="tab" aria-selected={mobilePane.value === "list"} onClick={() => { mobilePane.value = "list"; }}>
        <Icon name="list" />Lista
      </button>
      <button type="button" role="tab" aria-selected={mobilePane.value === "map"} onClick={() => { mobilePane.value = "map"; }}>
        <Icon name="map" />Mapa
      </button>
    </div>
  );
}
