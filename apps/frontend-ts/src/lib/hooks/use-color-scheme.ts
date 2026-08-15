"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

/** Supported local color schemes (orthogonal to light/dark). */
export type ColorScheme =
  | "default"
  | "neon"
  | "retrowave"
  | "gunmetal"
  | "terminal"
  | "hackerman"
  | "midnight"
  | "paper"
  | "forest"
  | "ocean"
  | "copper"
  | "stained-glass";

export const COLOR_SCHEMES: readonly ColorScheme[] = [
  "default",
  "neon",
  "retrowave",
  "gunmetal",
  "terminal",
  "hackerman",
  "midnight",
  "paper",
  "forest",
  "ocean",
  "copper",
  "stained-glass",
] as const;

export const COLOR_SCHEME_LABELS: Record<ColorScheme, string> = {
  default: "Raid",
  neon: "Neon",
  retrowave: "Retrowave",
  gunmetal: "Gunmetal",
  terminal: "Terminal",
  hackerman: "Hackerman",
  midnight: "Midnight",
  paper: "Paper",
  forest: "Forest",
  ocean: "Ocean",
  copper: "Copper",
  "stained-glass": "Stained glass",
};

/**
 * Preview swatches for Settings cards (background, primary, accent).
 *
 * Colors are representative dark-mode tokens so the grid stays readable
 * regardless of the page's current light/dark class. Paper uses a light
 * preview so it stays recognizable.
 */
export const COLOR_SCHEME_SWATCHES: Record<
  ColorScheme,
  readonly [string, string, string]
> = {
  default: ["#0f0f0f", "#ff6b6b", "#c5303e"],
  neon: ["#050510", "#00f0ff", "#ff2bd6"],
  retrowave: ["#12081f", "#ff2a6d", "#05d9e8"],
  gunmetal: ["#12151a", "#8b9bb4", "#c5d0e0"],
  terminal: ["#0a0f0a", "#33ff66", "#1a7a3a"],
  hackerman: ["#000000", "#00ff41", "#003b00"],
  midnight: ["#0b1220", "#7aa2ff", "#3d5a80"],
  paper: ["#f7f3ea", "#1a1a1a", "#a67c52"],
  forest: ["#0c1410", "#3d9b6a", "#a7d7b5"],
  ocean: ["#061018", "#3db8e8", "#0e4d6e"],
  copper: ["#1a1210", "#d4894a", "#8c5a3c"],
  "stained-glass": ["#14081c", "#e8b923", "#7b2cbf"],
};

const STORAGE_KEY = "job-raider-color-scheme";
const CHANGE_EVENT = "job-raider-color-scheme-change";

/**
 * Return whether a value is a known color scheme.
 *
 * @param value - Candidate scheme id from storage or UI.
 * @returns True when the value is a supported scheme.
 */
export function isColorScheme(
  value: string | null | undefined,
): value is ColorScheme {
  return (
    typeof value === "string" &&
    (COLOR_SCHEMES as readonly string[]).includes(value)
  );
}

/**
 * Read the persisted color scheme from localStorage.
 *
 * @returns Stored scheme, or ``default`` when missing or invalid.
 */
function readColorScheme(): ColorScheme {
  if (typeof window === "undefined") return "default";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return isColorScheme(raw) ? raw : "default";
  } catch {
    return "default";
  }
}

/**
 * Persist the color scheme and notify subscribers.
 *
 * @param scheme - Scheme to store.
 */
function writeColorScheme(scheme: ColorScheme): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, scheme);
  } catch {
    // Ignore quota / private-mode failures.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onStoreChange: () => void): () => void {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(CHANGE_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(CHANGE_EVENT, onStoreChange);
  };
}

/**
 * Subscribe to the local color-scheme preference (default: Raid).
 *
 * @returns Tuple of current scheme and setter.
 */
export function useColorSchemePreference(): [
  ColorScheme,
  (scheme: ColorScheme) => void,
] {
  const scheme = useSyncExternalStore(
    subscribe,
    readColorScheme,
    () => "default" as ColorScheme,
  );

  const setScheme = useCallback((next: ColorScheme) => {
    writeColorScheme(next);
  }, []);

  return [scheme, setScheme];
}

/**
 * Sync ``data-scheme`` on ``document.documentElement`` with preference.
 *
 * Renders nothing; mount once under the app shell.
 */
export function ColorSchemeDocumentSync(): null {
  const [scheme] = useColorSchemePreference();

  useEffect(() => {
    const root = document.documentElement;
    if (scheme === "default") {
      root.removeAttribute("data-scheme");
    } else {
      root.setAttribute("data-scheme", scheme);
    }
  }, [scheme]);

  return null;
}
