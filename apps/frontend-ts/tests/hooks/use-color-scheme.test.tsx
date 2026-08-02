/**
 * ColorSchemeDocumentSync applies data-scheme on the document root.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import {
  ColorSchemeDocumentSync,
  useColorSchemePreference,
} from "@/lib/hooks/use-color-scheme";

/**
 * Test harness that exposes the scheme setter as a button.
 */
function SchemeSetter() {
  const [, setScheme] = useColorSchemePreference();
  return (
    <button type="button" onClick={() => setScheme("retrowave")}>
      Set retrowave
    </button>
  );
}

describe("ColorSchemeDocumentSync", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-scheme");
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-scheme");
  });

  it("leaves data-scheme unset for the default Raid scheme", async () => {
    render(<ColorSchemeDocumentSync />);
    await waitFor(() => {
      expect(document.documentElement.hasAttribute("data-scheme")).toBe(false);
    });
  });

  it("sets data-scheme=neon when preference is neon", async () => {
    window.localStorage.setItem("job-raider-color-scheme", "neon");
    render(<ColorSchemeDocumentSync />);
    await waitFor(() => {
      expect(document.documentElement.getAttribute("data-scheme")).toBe("neon");
    });
  });

  it("updates data-scheme when preference changes", async () => {
    render(
      <>
        <ColorSchemeDocumentSync />
        <SchemeSetter />
      </>,
    );
    await waitFor(() => {
      expect(document.documentElement.hasAttribute("data-scheme")).toBe(false);
    });

    fireEvent.click(screen.getByRole("button", { name: "Set retrowave" }));

    await waitFor(() => {
      expect(document.documentElement.getAttribute("data-scheme")).toBe(
        "retrowave",
      );
    });
  });
});
