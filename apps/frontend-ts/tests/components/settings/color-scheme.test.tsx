/**
 * Appearance settings surfaces the color scheme control.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CinematicAtmosphereToggle } from "@/components/settings/cinematic-atmosphere-toggle";
import {
  COLOR_SCHEME_LABELS,
  useColorSchemePreference,
} from "@/lib/hooks/use-color-scheme";

/**
 * Harness that drives the color-scheme setter without Base UI Select quirks.
 */
function SchemeHarness() {
  const [scheme, setScheme] = useColorSchemePreference();
  return (
    <div>
      <span data-testid="scheme-label">{COLOR_SCHEME_LABELS[scheme]}</span>
      <button type="button" onClick={() => setScheme("neon")}>
        Choose neon
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

  it("renders the color scheme control in Appearance", () => {
    render(<CinematicAtmosphereToggle />);
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Color scheme")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(
      screen.getByText(/Neon and Retrowave remap accent colors/),
    ).toBeInTheDocument();
  });

  it("persists neon selection to localStorage via preference API", async () => {
    render(<SchemeHarness />);
    expect(screen.getByTestId("scheme-label")).toHaveTextContent(
      COLOR_SCHEME_LABELS.default,
    );
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
