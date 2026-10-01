import { navigationUrl } from "../domain/format";
import { back, notify } from "../state/store";
import { Icon } from "./icons";

export function BackButton() {
  return (
    <button type="button" class="link-button back" onClick={back}>
      <Icon name="arrowLeft" />Wróć
    </button>
  );
}

export function ScoreBadge({ value, label }: { value: number; label: string }) {
  return (
    <div class="score-badge">
      <strong>{Math.round(value)}</strong>
      <small>{label}</small>
    </div>
  );
}

export function CardActions({ point, label }: { point: [number, number]; label: string }) {
  const [lon, lat] = point;
  const coords = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(coords);
      notify(`Skopiowano współrzędne: ${coords}`);
    } catch {
      notify(`Współrzędne: ${coords}`);
    }
  };
  return (
    <div class="card-actions">
      <a class="button primary" href={navigationUrl(point)} target="_blank" rel="noopener noreferrer" aria-label={`Nawiguj: ${label} (Google Maps)`}>
        <Icon name="navigate" />Nawiguj
      </a>
      <button type="button" class="button" onClick={() => void copy()}>
        <Icon name="copy" />Kopiuj współrzędne
      </button>
    </div>
  );
}
