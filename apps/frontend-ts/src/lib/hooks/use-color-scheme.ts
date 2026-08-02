"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

/** Supported local color schemes (orthogonal to light/dark). */
export type ColorScheme = "default" | "neon" | "retrowave";

export const COLOR_SCHEMES: readonly ColorScheme[] = [
  "default",
  "neon",
  "retrowave",
] as const;

export const COLOR_SCHEME_LABELS: Record<ColorScheme, string> = {
  default: "Raid (default)",
  neon: "Neon",
  retrowave: "Retrowave",
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
  return value === "default" || value === "neon" || value === "retrowave";
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
