import { openStand, rankIndex, ranked, showSmall, standPage, visibleStands } from "../state/store";
import { StandRow } from "./StandRow";

export const STAND_PAGE_SIZE = 50;

export function StandList() {
  const list = visibleStands.value;
  const shown = list.slice(0, standPage.value * STAND_PAGE_SIZE);
  const hiddenSmall = ranked.value.length - list.length;
  return (
    <section class="rows-section" aria-label="Wydzielenia">
      <label class="check">
        <input
          type="checkbox"
          checked={showSmall.value}
          onChange={(event) => {
            showSmall.value = (event.currentTarget as HTMLInputElement).checked;
            standPage.value = 1;
          }}
        />
        Pokaż też wydzielenia mniejsze niż 0,5 ha{!showSmall.value && hiddenSmall > 0 ? ` (${hiddenSmall})` : ""}
      </label>
      {list.length === 0 ? (
        <p class="empty">Brak wydzieleń spełniających filtry modelu w tej analizie.</p>
      ) : (
        <ol class="rows">
          {shown.map((e) => (
            <StandRow
              key={e.score.stand_id}
              entry={e}
              rank={(rankIndex.value.get(e.score.stand_id) ?? 0) + 1}
              onOpen={() => openStand(e.score.stand_id, "list")}
            />
          ))}
        </ol>
      )}
      {shown.length < list.length && (
        <button type="button" class="button more" onClick={() => { standPage.value += 1; }}>
          Pokaż więcej ({list.length - shown.length})
        </button>
      )}
    </section>
  );
}
