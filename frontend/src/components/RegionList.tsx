import { areaLabel, joinMeta, startDistanceLabel } from "../domain/format";
import { regionName } from "../domain/labels";
import { regionAreaHa } from "../domain/ranking";
import { openRegion, regionViews, start } from "../state/store";

export function RegionList() {
  const views = regionViews.value;
  if (!views.length)
    return <p class="empty">W tej analizie nie ma rejonów. Zobacz zakładkę „Wydzielenia”.</p>;
  return (
    <ol class="rows" aria-label="Rejony">
      {views.map((v, i) => (
        <li key={v.region.region_id}>
          <button type="button" class="row" onClick={() => openRegion(v.region.region_id, "list")}>
            <span class="row-rank region">{i + 1}</span>
            <span class="row-main">
              <span class="row-name">{regionName(v.region, i + 1)}</span>
              <span class="row-meta">
                {joinMeta([
                  `${v.members.length} wydz.`,
                  areaLabel(regionAreaHa(v)),
                  startDistanceLabel(start.value, [v.region.centroid_lon, v.region.centroid_lat]),
                ])}
              </span>
            </span>
            <span class="row-score">{Math.round(v.region.rank_score)}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
