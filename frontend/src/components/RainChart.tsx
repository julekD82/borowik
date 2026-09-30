import { dayMonth, pl } from "../domain/format";
import type { WeatherPanelModel } from "../domain/weather";

const WIDTH = 360;
const TOP = 12;
const BARS = 64;
const AXIS = 14;
const TEMP = 56;

export function RainChart({ model, expanded }: { model: WeatherPanelModel; expanded: boolean }) {
  const n = model.bars.length;
  if (!n) return null;
  const bw = WIDTH / n;
  const maxMm = Math.max(10, ...model.bars.map((b) => b.mm ?? 0));
  const first = model.bars.findIndex((b) => b.inWindow);
  const last = n - 1 - [...model.bars].reverse().findIndex((b) => b.inWindow);
  const todayIndex = model.bars.findIndex((b) => b.isToday);
  const temps = model.temps.filter((t) => t.tmin !== null && t.tmax !== null);
  const showTemp = expanded && temps.length > 1;
  const height = TOP + BARS + AXIS + (showTemp ? TEMP + 6 : 0);
  const labels: [number, string][] = [[0, dayMonth(model.bars[0].date)], [n - 1, dayMonth(model.bars[n - 1].date)]];
  if (first > 0) labels.push([first, dayMonth(model.bars[first].date)]);
  return (
    <svg class="rain-chart" viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={model.chartLabel}>
      {first >= 0 && <rect class="window" x={first * bw} y={0} width={(last - first + 1) * bw} height={TOP + BARS} />}
      {first >= 0 && <text x={first * bw + 3} y={9}>okno 26 dni</text>}
      {model.bars.map((b, i) => {
        const mm = b.mm ?? 0;
        const h = mm > 0 ? Math.max(1.5, (mm / maxMm) * BARS) : 1.5;
        const suffix = b.kind === "forecast" ? " (prognoza)" : b.kind === "model" ? " (model, bez radaru)" : "";
        return (
          <rect class={`bar-${b.kind}${mm > 0 ? "" : " dry"}`} x={i * bw + 0.8} y={TOP + BARS - h} width={Math.max(1, bw - 1.6)} height={h} rx={1}>
            <title>{`${dayMonth(b.date)}: ${b.mm === null ? "brak danych" : `${pl(b.mm, 1)} mm`}${suffix}`}</title>
          </rect>
        );
      })}
      {todayIndex >= 0 && (
        <>
          <line class="today" x1={(todayIndex + 1) * bw} x2={(todayIndex + 1) * bw} y1={0} y2={TOP + BARS + 4} />
          <text class="today-label" x={(todayIndex + 1) * bw + 2} y={9}>dziś</text>
        </>
      )}
      {labels.map(([i, text]) => (
        <text x={i * bw + bw / 2} y={TOP + BARS + 11} text-anchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}>{text}</text>
      ))}
      {showTemp && <TempBand model={model} bw={bw} top={TOP + BARS + AXIS + 6} />}
    </svg>
  );
}

function TempBand({ model, bw, top }: { model: WeatherPanelModel; bw: number; top: number }) {
  const values = model.temps.flatMap((t) => [t.tmin, t.tmax]).filter((v): v is number => v !== null);
  const lo = Math.min(...values, model.optimum ?? Infinity) - 1;
  const hi = Math.max(...values, model.optimum ?? -Infinity) + 1;
  const y = (t: number) => top + TEMP - ((t - lo) / (hi - lo)) * TEMP;
  const upper = model.temps.flatMap((t, i) => (t.tmax === null ? [] : [`${i * bw + bw / 2},${y(t.tmax)}`]));
  const lower = model.temps.flatMap((t, i) => (t.tmin === null ? [] : [`${i * bw + bw / 2},${y(t.tmin)}`])).reverse();
  return (
    <>
      <polygon class="temp-band" points={[...upper, ...lower].join(" ")} />
      {model.optimum !== null && (
        <>
          <line class="optimum" x1={0} x2={WIDTH} y1={y(model.optimum)} y2={y(model.optimum)} />
          <text x={2} y={y(model.optimum) - 2}>{`${pl(model.optimum)} °C`}</text>
        </>
      )}
      <text x={WIDTH - 2} y={top + 8} text-anchor="end">temp. min.–maks.</text>
    </>
  );
}
