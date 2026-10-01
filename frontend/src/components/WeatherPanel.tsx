import { useState } from "preact/hooks";
import { pl } from "../domain/format";
import { WEATHER_NOTE, type WeatherPanelModel } from "../domain/weather";
import { weatherModel } from "../state/store";
import { RainChart } from "./RainChart";

const mm = (v: number | null) => (v === null ? "—" : v === 0 ? "0" : `${pl(v, 1)} mm`);
const temp = (v: number | null) => (v === null ? "—" : `${pl(v)}°`);

function Details({ model }: { model: WeatherPanelModel }) {
  const uncertain = model.forecast.some((r) => r.uncertainty !== "ok");
  return (
    <div class="weather-details">
      {model.forecast.length > 0 && (
        <table class="forecast">
          <thead>
            <tr><th scope="col">Dzień</th><th scope="col">Opad</th><th scope="col">Maks.</th><th scope="col">Min.</th></tr>
          </thead>
          <tbody>
            {model.forecast.map((r) => (
              <tr class={r.uncertainty !== "ok" ? "uncertain" : undefined}>
                <th scope="row">{r.label}{r.uncertainty === "uncertain" ? " ?" : r.uncertainty === "indicative" ? " ~" : ""}</th>
                <td>{mm(r.mm)}</td>
                <td>{temp(r.tmax)}</td>
                <td>{temp(r.tmin)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {uncertain && <p class="muted small">? prognoza niepewna · ~ orientacyjnie</p>}
      <p class="muted small">{WEATHER_NOTE}</p>
    </div>
  );
}

export function WeatherPanel() {
  const [open, setOpen] = useState(false);
  const model = weatherModel.value;
  if (!model) return null;
  const activeChecks = model.checks.filter((c) => c.active);
  const checks = open ? model.checks : activeChecks;
  return (
    <section class="weather" aria-label="Pogoda">
      <h2 class="weather-headline">{model.headline}</h2>
      {model.facts.length > 0 && (
        <dl class="facts">
          {model.facts.map((f) => (
            <div>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
              {f.note && <dd class="fact-note">{f.note}</dd>}
            </div>
          ))}
        </dl>
      )}
      {model.normalLine && <p class="muted small">{model.normalLine}</p>}
      {checks.length > 0 && (
        <ul class="chips">
          {checks.map((c) => <li class={`chip ${c.active ? "warn" : "ok"}`}>{c.label}</li>)}
        </ul>
      )}
      <RainChart model={model} expanded={open} />
      {open && <Details model={model} />}
      {!model.legacy && (
        <button type="button" class="link-button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Zwiń" : "Szczegóły: temperatura, prognoza"}
        </button>
      )}
    </section>
  );
}
