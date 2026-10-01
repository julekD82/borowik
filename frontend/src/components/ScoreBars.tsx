import type { Bar, BarNotes } from "../domain/bars";
import { formatValue } from "../domain/format";

export function ScoreBars({ bars, notes }: { bars: Bar[]; notes?: BarNotes }) {
  return (
    <ul class="bars">
      {bars.map((b) => (
        <li class={`bar bar-${b.key}${b.muted ? " is-muted" : ""}`}>
          <span class="bar-label">{b.label}</span>
          <span class="bar-track"><i style={{ width: `${Math.round((b.value ?? 0) * 100)}%` }} /></span>
          <span class="bar-word">{b.word}{b.value !== null && !b.muted ? ` · ${formatValue(b.value)}` : ""}</span>
          {notes?.[b.key] && <span class="bar-note">{notes[b.key]}</span>}
        </li>
      ))}
    </ul>
  );
}
