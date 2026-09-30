import { retry } from "../state/loader";
import { toast } from "../state/store";

export function LoadingState() {
  return (
    <div class="status" role="status">
      <span class="spinner" aria-hidden="true" />
      <p>Wczytuję analizę…</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div class="status status-error" role="alert">
      <h2>Nie udało się wczytać analizy</h2>
      <p>{message}</p>
      <button type="button" class="button primary" onClick={() => void retry()}>Spróbuj ponownie</button>
    </div>
  );
}

export function Toast() {
  return toast.value ? <div class="toast" role="status">{toast.value}</div> : null;
}
