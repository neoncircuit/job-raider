/**
 * Appearance settings: Odysseus-inspired scheme swatch grid.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CinematicAtmosphereToggle } from "@/components/settings/cinematic-atmosphere-toggle";
import {
  COLOR_SCHEME_LABELS,
  COLOR_SCHEMES,
  isColorScheme,
  useColorSchemePreference,
} from "@/lib/hooks/use-color-scheme";

/**
 * Harness that drives the color-scheme setter without UI.
 */
function SchemeHarness() {
  const [scheme, setScheme] = useColorSchemePreference();
  return (
    <div>
      <span data-testid="scheme-label">{COLOR_SCHEME_LABELS[scheme]}</span>
      <button type="button" onClick={() => setScheme("neon")}>
        Choose neon
      </button>
      <button type="button" onClick={() => setScheme("gunmetal")}>
        Choose gunmetal
      </button>
    </div>
  );
}

describe("Appearance color scheme UI", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("accepts curated scheme ids and rejects unknown values", () => {
    expect(isColorScheme("default")).toBe(true);
    expect(isColorScheme("hackerman")).toBe(true);
    expect(isColorScheme("stained-glass")).toBe(true);
    expect(isColorScheme("not-a-scheme")).toBe(false);
    expect(COLOR_SCHEMES).toHaveLength(12);
  });

  it("renders a swatch-card radiogroup for every curated scheme", () => {
    render(<CinematicAtmosphereToggle />);
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Color scheme")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    for (const id of COLOR_SCHEMES) {
      expect(
        screen.getByRole("radio", { name: COLOR_SCHEME_LABELS[id] }),
      ).toBeInTheDocument();
    }
    expect(screen.getByRole("radio", { name: "Raid" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("persists neon when a swatch card is selected", async () => {
    render(<CinematicAtmosphereToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Neon" }));
    await waitFor(() => {
      expect(window.localStorage.getItem("job-raider-color-scheme")).toBe(
        "neon",
      );
      expect(screen.getByRole("radio", { name: "Neon" })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
  });

  it("persists gunmetal selection to localStorage via preference API", async () => {
    render(<SchemeHarness />);
    expect(screen.getByTestId("scheme-label")).toHaveTextContent(
      COLOR_SCHEME_LABELS.default,
    );
    fireEvent.click(screen.getByRole("button", { name: "Choose gunmetal" }));
    await waitFor(() => {
      expect(window.localStorage.getItem("job-raider-color-scheme")).toBe(
        "gunmetal",
      );
      expect(screen.getByTestId("scheme-label")).toHaveTextContent(
        COLOR_SCHEME_LABELS.gunmetal,
      );
    });
  });

  it("persists neon selection to localStorage via preference API", async () => {
    render(<SchemeHarness />);
    fireEvent.click(screen.getByRole("button", { name: "Choose neon" }));
    await waitFor(() => {
      expect(window.localStorage.getItem("job-raider-color-scheme")).toBe(
        "neon",
      );
      expect(screen.getByTestId("scheme-label")).toHaveTextContent(
        COLOR_SCHEME_LABELS.neon,
      );
    });
  });
});
