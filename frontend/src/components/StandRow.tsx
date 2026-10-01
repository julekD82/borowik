import type { StandView } from "../data/types";
import { areaLabel, joinMeta, startDistanceLabel } from "../domain/format";
import { standName } from "../domain/labels";
import { CLASS_LABELS } from "../domain/ranking";
import { classById, details, selectedStandId, start } from "../state/store";

export function StandRow({ entry, rank, onOpen }: { entry: StandView; rank: number; onOpen: () => void }) {
  const id = entry.score.stand_id;
  const cls = classById.value.get(id) ?? 4;
  return (
    <li>
      <button type="button" class="row" onClick={onOpen} aria-current={selectedStandId.value === id ? "true" : undefined}>
        <span class="row-rank">{rank}</span>
        <span class="row-main">
          <span class="row-name">{standName(id, details.value?.get(id) ?? null)}</span>
          <span class="row-meta">{joinMeta([areaLabel(entry.score.area_ha), startDistanceLabel(start.value, entry.point)])}</span>
        </span>
        <span class={`chip chip-class-${cls}`}>{CLASS_LABELS[cls]}</span>
        <span class="row-score">{Math.round(entry.r)}</span>
      </button>
    </li>
  );
}
