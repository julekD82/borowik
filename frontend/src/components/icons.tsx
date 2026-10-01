import type { JSX } from "preact";

export type IconName =
  | "mushroom" | "map" | "list" | "arrowLeft" | "info" | "target" | "layers" | "close" | "copy" | "navigate";

// Styl kreski (fill, stroke, szerokosc) w CSS klasy .icon.
const SHAPES: Record<IconName, () => JSX.Element> = {
  mushroom: () => (<><path d="M3 12a9 9 0 0 1 18 0Z" /><path d="M9 12v7a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-7" /></>),
  map: () => <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Zm6-3v15m6-12v15" />,
  list: () => <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
  arrowLeft: () => <path d="M19 12H5m6-6-6 6 6 6" />,
  info: () => (<><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.01" /></>),
  target: () => (<><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3" /></>),
  layers: () => (<><path d="m12 3 9 5-9 5-9-5Z" /><path d="m3 13 9 5 9-5" /></>),
  close: () => <path d="m6 6 12 12M6 18 18 6" />,
  copy: () => (<><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M4 16V6a2 2 0 0 1 2-2h10" /></>),
  navigate: () => <path d="m21 3-7 18-3-8-8-3Z" />,
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      {SHAPES[name]()}
    </svg>
  );
}
