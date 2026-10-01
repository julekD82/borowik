import { regionAccessSummary } from "../domain/access";
import { regionBars } from "../domain/bars";
import { areaLabel, joinMeta, startDistanceLabel } from "../domain/format";
import { regionName } from "../domain/labels";
import { regionAreaHa } from "../domain/ranking";
import type { AccessCard } from "../data/types";
import { details, openStand, pressure, rankIndex, regionViews, start } from "../state/store";
import { BackButton, CardActions, ScoreBadge } from "./CardParts";
import { ScoreBars } from "./ScoreBars";
import { StandRow } from "./StandRow";

export function RegionCard({ regionId }: { regionId: string }) {
  const index = regionViews.value.findIndex((v) => v.region.region_id === regionId);
  const view = regionViews.value[index];
  if (!view)
    return (
      <article class="card">
        <BackButton />
        <p class="empty">Nie ma już tego rejonu w bieżącym wariancie rankingu.</p>
      </article>
    );
  const name = regionName(view.region, index + 1);
  const point: [number, number] = [view.region.centroid_lon, view.region.centroid_lat];
  const loaded = details.value !== null;
  const cards = view.members
    .map((m) => details.value?.get(m.score.stand_id)?.access)
    .filter((c): c is AccessCard => !!c);
  const access = regionAccessSummary(cards);
  const members = [...view.members].sort((a, b) => b.r - a.r);
  return (
    <article class="card">
      <BackButton />
      <header class="card-head">
        <div>
          <h2>{name}</h2>
          <p class="muted">
            {joinMeta([`${view.members.length} wydz.`, areaLabel(regionAreaHa(view)), startDistanceLabel(start.value, point)])}
          </p>
        </div>
        <ScoreBadge value={view.region.rank_score} label="wynik rejonu" />
      </header>
      <section>
        <h3>Dlaczego taki wynik</h3>
        <ScoreBars bars={regionBars(view.members, pressure.value)} />
        <p class="hint">Mediana 5 najlepszych wydzieleń rejonu — ta sama podstawa co wynik rejonu.</p>
      </section>
      <section>
        <h3>Dojazd</h3>
        {!loaded ? (
          <p class="muted">Wczytuję szczegóły…</p>
        ) : access ? (
          <>
            <p>{access.distances}</p>
            <p class="muted small">{access.top}</p>
          </>
        ) : (
          <p class="muted">Brak danych o dojeździe.</p>
        )}
      </section>
      <section>
        <h3>Wydzielenia w rejonie ({view.members.length})</h3>
        <ol class="rows">
          {members.map((m) => (
            <StandRow
              key={m.score.stand_id}
              entry={m}
              rank={(rankIndex.value.get(m.score.stand_id) ?? 0) + 1}
              onOpen={() => openStand(m.score.stand_id, "list")}
            />
          ))}
        </ol>
      </section>
      <CardActions point={point} label={name} />
    </article>
  );
}
