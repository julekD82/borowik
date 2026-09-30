export const finite = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

export function distanceLabel(value?: number | null): string {
  if (!finite(value) || value < 0) return "Brak danych";
  return value < 1000
    ? `${Math.round(value)} m`
    : `${(value / 1000).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} km`;
}

export function navigationUrl([lon, lat]: [number, number]): string {
  if (!finite(lon) || !finite(lat) || Math.abs(lon) > 180 || Math.abs(lat) > 90)
    throw new Error("Niepoprawne współrzędne");
  return `https://www.google.com/maps?q=${lat},${lon}`;
}

export const pl = (value: number, digits = 0) =>
  value.toLocaleString("pl-PL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const finiteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export const dayMonth = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export const pln = (value: number, digits = 2) =>
  value.toLocaleString("pl-PL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const formatValue = (value: number | null | undefined, digits = 2) =>
  finite(value) ? pln(value, digits) : "—";

export const roundedDistance = (v: number | null | undefined) =>
  finite(v) ? (v < 1000 ? `${Math.round(v / 10) * 10} m` : `${pln(v / 1000, 1)} km`) : null;

/** Odleglosc w linii prostej (km) miedzy punktami [lon, lat]. */
export function haversineKm(a: [number, number], b: [number, number]): number {
  const rad = (x: number) => (x * Math.PI) / 180;
  const dLat = rad(b[1] - a[1]);
  const dLon = rad(b[0] - a[0]);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function startDistanceLabel(
  start: [number, number] | null | undefined,
  point: [number, number],
): string | null {
  if (!start) return null;
  return `${pln(haversineKm(start, point), 1)} km od startu`;
}

export function areaLabel(areaHa: number | null | undefined): string | null {
  return finite(areaHa) ? `${pln(areaHa, areaHa < 10 ? 1 : 0)} ha` : null;
}
