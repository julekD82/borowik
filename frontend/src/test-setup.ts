import { afterEach } from "vitest";

// Testy komponentow (// @vitest-environment jsdom) sprzataja DOM po kazdym tescie;
// testy w srodowisku node nie importuja biblioteki DOM.
afterEach(async () => {
  if (typeof document === "undefined") return;
  const { cleanup } = await import("@testing-library/preact");
  cleanup();
});
