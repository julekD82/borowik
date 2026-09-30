import { ranked, regionViews, setTab, tab } from "../state/store";

export function Tabs() {
  return (
    <div class="tabs" role="tablist" aria-label="Lista">
      <button type="button" role="tab" aria-selected={tab.value === "regions"} onClick={() => setTab("regions")}>
        Rejony ({regionViews.value.length})
      </button>
      <button type="button" role="tab" aria-selected={tab.value === "stands"} onClick={() => setTab("stands")}>
        Wydzielenia ({ranked.value.length.toLocaleString("pl-PL")})
      </button>
    </div>
  );
}
