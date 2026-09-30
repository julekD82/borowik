import { pressure, pressureAvailable, setPressure } from "../state/store";

export function PressureToggle() {
  const available = pressureAvailable.value;
  const on = pressure.value;
  const hint = !available
    ? "Niedostępne w tej migawce — starszy eksport nie ma wyników bez presji."
    : on
      ? "Ranking uwzględnia, ilu innych grzybiarzy można spotkać."
      : "Ranking tylko z siedliska i pogody.";
  return (
    <label class={`switch${available ? "" : " is-disabled"}`}>
      <input
        type="checkbox"
        role="switch"
        checked={on}
        disabled={!available}
        onChange={(event) => setPressure((event.currentTarget as HTMLInputElement).checked)}
      />
      <span class="switch-text">
        <strong>Uwzględniaj presję grzybiarzy</strong>
        <small>{hint}</small>
      </span>
    </label>
  );
}
