// @vitest-environment jsdom
import { render } from "@testing-library/preact";
import { describe, expect, it } from "vitest";
import { Icon } from "./icons";

describe("Icon", () => {
  it("renders a decorative svg with the requested shape", () => {
    const { container } = render(<Icon name="map" />);
    const svg = container.querySelector("svg.icon");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.querySelector("path")).not.toBeNull();
  });
});
