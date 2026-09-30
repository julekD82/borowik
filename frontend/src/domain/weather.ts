import type { ConditionsTimeline, DailyWeather, ForecastUncertainty } from "../data/types";
import { dayMonth, finite, pl } from "./format";

const WEEKDAYS = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];

export function dayLabel(dateIso: string, position: number): string {
  if (position === 0) return "dziś";
  return WEEKDAYS[new Date(`${dateIso}T12:00:00`).getDay()];
}

/** Oznaczenie dnia prognozy: "prognoza niepewna" (od progu 1) i "orientacyjnie" (od progu 2). */
export function uncertaintyLabel(level: ForecastUncertainty | undefined): string | null {
  if (level === "uncertain") return "prognoza niepewna";
  if (level === "indicative") return "orientacyjnie";
  return null;
}

export type RainBarKind = "measured" | "model" | "forecast";
export type RainBar = { date: string; mm: number | null; kind: RainBarKind; inWindow: boolean; isToday: boolean };
export type TempPoint = { date: string; tmin: number | null; tmax: number | null };
export type ForecastRow = {
  date: string;
  label: string;
  mm: number | null;
  tmax: number | null;
  tmin: number | null;
  uncertainty: ForecastUncertainty;
};
export type WeatherFact = { label: string; value: string; note: string };
export type WeatherCheck = { label: string; active: boolean };
export type WeatherPanelModel = {
  legacy: boolean;
  headline: string;
  facts: WeatherFact[];
  normalLine: string | null;
  bars: RainBar[];
  temps: TempPoint[];
  optimum: number | null;
  forecast: ForecastRow[];
  checks: WeatherCheck[];
  chartLabel: string;
};

export const WEATHER_NOTE =
  "Słupki: opad dzienny (mediana obszaru). Ciemne — pomiar z radaru IMGW, pośrednie — model bez radaru, jasne — prognoza. " +
  "Wg danych z Bielefeld liczy się deszcz z ok. 3 tygodni wstecz, mniej więcej po równo. " +
  "Pomiar opadu i norma (E-OBS, sieć stacji) to różne źródła — porównanie jest przybliżone.";

export function dayRangeLabel(start: string, end: string): string {
  const [, sm, sd] = start.split("-").map(Number);
  const [, em, ed] = end.split("-").map(Number);
  const two = (n: number) => String(n).padStart(2, "0");
  if (start === end) return `${sd}.${two(sm)}`;
  if (sm === em) return `${sd}–${ed}.${two(em)}`;
  return `${sd}.${two(sm)}–${ed}.${two(em)}`;
}

export function daysAgoLabel(n: number): string {
  return n <= 0 ? "dziś" : n === 1 ? "wczoraj" : `${n} dni temu`;
}

const afterRain = (daysAgo: number) =>
  daysAgo <= 0 ? "Dziś większy deszcz" : daysAgo === 1 ? "1 dzień po większym deszczu" : `${daysAgo} dni po większym deszczu`;

const barKind = (d: DailyWeather): RainBarKind => (d.forecast ? "forecast" : d.radar_share >= 0.5 ? "measured" : "model");

const CHECKS: Record<string, { active: string; quiet: string }> = {
  frost: { active: "Przymrozek", quiet: "bez przymrozku" },
  heat_drought: { active: "Upał bez deszczu", quiet: "bez upału z suszą" },
};

/** Tresc panelu pogody z conditions.json: same fakty; stara migawka = zdanie o deszczu + temperatura. */
export function buildWeatherPanel(c: ConditionsTimeline | null): WeatherPanelModel | null {
  if (!c) return null;
  const today = c.generated_for;
  const t20 = c.days[0]?.components?.tmean20_c;
  const optimum = c.days[0]?.components?.temp_optimum_c;
  const tempFact: WeatherFact | null = finite(t20)
    ? { label: "Temperatura, średnio 20 dni", value: `${pl(t20, 1)} °C`, note: finite(optimum) ? `optimum ok. ${pl(optimum)} °C` : "" }
    : null;
  const r26 = c.rain26;
  if (!c.daily?.length || !r26)
    return {
      legacy: true, headline: c.summary, facts: tempFact ? [tempFact] : [], normalLine: null,
      bars: [], temps: [], optimum: null, forecast: [], checks: [], chartLabel: "",
    };
  const last = c.rains[0] ?? null;
  const lookback = c.lookback_days;
  const rainPart = last
    ? afterRain(last.days_ago)
    : finite(lookback) ? `Brak większego deszczu od ${lookback} dni` : "Brak większego deszczu w ostatnich tygodniach";
  const normal = r26.normal_mm;
  const facts: WeatherFact[] = [
    { label: "Opad, 26 dni", value: `${pl(r26.sum_mm)} mm`, note: finite(normal) ? `norma ${pl(normal)} mm` : "bez normy" },
    last
      ? { label: "Ostatni większy deszcz", value: daysAgoLabel(last.days_ago), note: `${dayRangeLabel(last.start, last.end)} · ${pl(last.rain_mm, 1)} mm` }
      : { label: "Ostatni większy deszcz", value: "brak", note: finite(lookback) ? `od ${lookback} dni` : "" },
  ];
  if (tempFact) facts.push(tempFact);
  const pct = r26.pct;
  const normalLine = finite(pct)
    ? pct >= 0.5
      ? `Więcej deszczu niż w ${Math.round(pct * 100)}% lat 1991–2020 o tej porze (E-OBS).`
      : `Mniej deszczu niż w ${Math.round((1 - pct) * 100)}% lat 1991–2020 o tej porze (E-OBS).`
    : null;
  const uncertaintyOf = (date: string): ForecastUncertainty => c.days.find((d) => d.date === date)?.uncertainty ?? "ok";
  const checks: WeatherCheck[] = (c.warnings ?? []).flatMap((w) => {
    const text = CHECKS[w.type];
    if (!text) return [];
    return [w.dates.length
      ? { label: `${text.active}: ${w.dates.map(dayMonth).join(", ")}`, active: true }
      : { label: text.quiet, active: false }];
  });
  return {
    legacy: false,
    headline: `${rainPart} · ${pl(r26.sum_mm)} mm w 26 dni${finite(normal) ? ` (norma ${pl(normal)})` : ""}`,
    facts,
    normalLine,
    bars: c.daily.map((d) => ({
      date: d.date, mm: d.precip_mm, kind: barKind(d),
      inWindow: d.date >= r26.window_start && d.date <= r26.window_end, isToday: d.date === today,
    })),
    temps: c.daily.map((d) => ({ date: d.date, tmin: d.tmin_c, tmax: d.tmax_c })),
    optimum: finite(optimum) ? optimum : null,
    forecast: c.daily
      .filter((d) => d.date >= today)
      .slice(0, c.horizon_days)
      .map((d, i) => ({ date: d.date, label: dayLabel(d.date, i), mm: d.precip_mm, tmax: d.tmax_c, tmin: d.tmin_c, uncertainty: uncertaintyOf(d.date) })),
    checks,
    chartLabel: `Opad dzienny od ${dayMonth(c.daily[0].date)} do ${dayMonth(c.daily[c.daily.length - 1].date)}; suma z 26 dni ${pl(r26.sum_mm)} mm.`,
  };
}
