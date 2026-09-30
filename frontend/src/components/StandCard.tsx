import { keyFacts, topPointSummary } from "../domain/access";
import { barNotes, scoreBars } from "../domain/bars";
import { areaLabel, finite, joinMeta, startDistanceLabel } from "../domain/format";
import { standCentroid } from "../domain/geometry";
import {
  densityLabel, formatDateLong, maskReasonTexts, neighborsSummary, parseStandId, standName, yearsLabel, zakazNote,
} from "../domain/labels";
import { effectiveR } from "../domain/ranking";
import type { Score, StandDetail } from "../data/types";
import { analysis, details, pressure, rankIndex, ranked, start } from "../state/store";
import { BackButton, CardActions, ScoreBadge } from "./CardParts";
import { ScoreBars } from "./ScoreBars";

// undefined = szczegoly jeszcze sie wczytuja; null = wczytane, ale brak tego wydzielenia.
type DetailState = StandDetail | null | undefined;

function TreeSection({ detail }: { detail: DetailState }) {
  if (detail === undefined)
    return <section><h3>Drzewostan</h3><p class="muted">Wczytuję szczegóły…</p></section>;
  if (detail === null)
    return <section><h3>Drzewostan</h3><p class="muted">Brak szczegółów dla tego wydzielenia.</p></section>;
  const rows: [string, string][] = [];
  if (detail.drzew_species.length) rows.push(["Skład", detail.drzew_species.map((s) => `${s.name} (${s.share})`).join(", ")]);
  if (finite(detail.age_years)) rows.push(["Wiek", yearsLabel(detail.age_years)]);
  if (detail.site_type) rows.push(["Siedlisko", `${detail.site_type.label} (${detail.site_type.code})`]);
  if (detail.soil_type) rows.push(["Gleba", detail.soil_type]);
  if (detail.density) rows.push(["Zwarcie", densityLabel(detail.density)]);
  if (detail.veg_cover) rows.push(["Runo", detail.veg_cover]);
  if (detail.podszyt_species.length) rows.push(["Podszyt", detail.podszyt_species.map((s) => s.name).join(", ")]);
  rows.push(["Sąsiedztwo", detail.neighbors.length ? detail.neighbors.join(", ") : (neighborsSummary(detail.neighbors) ?? "")]);
  return (
    <section>
      <h3>Drzewostan</h3>
      <dl class="kv">
        {rows.map(([k, v]) => <div><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
      {detail.searchability_hint && <p class="hint">{detail.searchability_hint}</p>}
    </section>
  );
}

function AccessSection({ score, detail }: { score: Score; detail: DetailState }) {
  const facts = keyFacts(detail?.access ?? null, null, score.d_park_m);
  const zakaz = zakazNote(score.zakaz_status);
  return (
    <section>
      <h3>Dojazd</h3>
      {detail === undefined && <p class="muted">Wczytuję szczegóły…</p>}
      {facts.length > 0 && <ul class="chips">{facts.map((f) => <li class="chip">{f}</li>)}</ul>}
      {detail?.access && <p class="muted small">{topPointSummary(detail.access)}</p>}
      {zakaz && <p class="notice-inline">{zakaz}</p>}
    </section>
  );
}

function DataSection({ score, day }: { score: Score; day: string }) {
  const parsed = parseStandId(score.stand_id);
  const source =
    score.s_host_source === "paczka"
      ? `paczka BDL${score.s_host_package_date ? ` z ${formatDateLong(score.s_host_package_date)}` : ""}`
      : score.s_host_source === "wfs" ? "opis WFS (tylko gatunek panujący)" : null;
  return (
    <section>
      <h3>Dane</h3>
      <dl class="kv">
        <div><dt>Kod</dt><dd class="mono">{score.stand_id}</dd></div>
        {parsed && <div><dt>Adres leśny</dt><dd>{`leśnictwo ${parsed.forestry} · oddział ${parsed.section} · pododdział ${parsed.subsection}`}</dd></div>}
        {source && <div><dt>Skład drzew</dt><dd>{source}</dd></div>}
        <div><dt>Analiza</dt><dd>{formatDateLong(day)}</dd></div>
      </dl>
    </section>
  );
}

export function StandCard({ standId }: { standId: string }) {
  const a = analysis.value;
  const score = a?.scoreById.get(standId);
  const feature = a?.features.get(standId);
  if (!a || !score || !feature)
    return (
      <article class="card">
        <BackButton />
        <p class="empty">Nie ma tego wydzielenia w bieżącej analizie.</p>
      </article>
    );
  const detail: DetailState = details.value === null ? undefined : (details.value.get(standId) ?? null);
  const point = standCentroid(feature);
  const name = standName(standId, detail ?? null);
  const r = effectiveR(score, pressure.value);
  const index = rankIndex.value.get(standId);
  const inModel = score.mask && r !== null && index !== undefined;
  return (
    <article class="card">
      <BackButton />
      <header class="card-head">
        <div>
          <h2>{name}</h2>
          <p class="muted">
            {joinMeta([areaLabel(score.area_ha), startDistanceLabel(start.value, point), inModel ? `#${index + 1} z ${ranked.value.length}` : null])}
          </p>
        </div>
        {inModel && <ScoreBadge value={r} label="wynik" />}
      </header>
      {inModel ? (
        <section>
          <h3>Dlaczego taki wynik</h3>
          <ScoreBars bars={scoreBars(score, pressure.value)} notes={barNotes(score, detail, pressure.value)} />
        </section>
      ) : score.mask ? (
        <section class="notice"><p>Brak wyniku dla tego wydzielenia w tej analizie.</p></section>
      ) : (
        <section class="notice">
          <h3>Nie spełnia filtrów modelu</h3>
          <ul>{maskReasonTexts(score.mask_reason).map((t) => <li>{t}</li>)}</ul>
        </section>
      )}
      <TreeSection detail={detail} />
      <AccessSection score={score} detail={detail} />
      <DataSection score={score} day={a.day} />
      <CardActions point={point} label={name} />
    </article>
  );
}
