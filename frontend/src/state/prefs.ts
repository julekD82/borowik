// Te same klucze co stary interfejs -- zapamietane ustawienia przechodza do nowego.
export const KEYS = {
  pressure: "borowik.pressure.v1",
  mapMode: "borowik.map-color.v1",
  layers: "borowik.access-layers.v1",
  tab: "borowik.view-mode.v1",
} as const;

export function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Bez zapisu: ustawienie dziala tylko w tej sesji.
  }
}
