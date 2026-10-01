import { formatTripLabel } from "../domain/labels";
import { basePathFor, openAnalysis } from "../state/loader";
import { tripId, trips } from "../state/store";

export function AnalysisPicker() {
  if (!trips.value.length) return null;
  return (
    <label class="picker">
      <span>Analiza</span>
      <select
        value={tripId.value ?? ""}
        onChange={(event) => {
          const id = (event.currentTarget as HTMLSelectElement).value || null;
          void openAnalysis(basePathFor(id), id);
        }}
      >
        <option value="">Aktualna</option>
        {trips.value.map((t) => (
          <option key={t.id} value={t.id}>{formatTripLabel(t)}</option>
        ))}
      </select>
    </label>
  );
}
