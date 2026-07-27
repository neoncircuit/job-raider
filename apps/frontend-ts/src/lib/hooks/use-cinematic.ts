"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

const STORAGE_KEY = "job-raider-cinematic";

/**
 * Read whether cinematic atmosphere is enabled from localStorage.
 *
 * @returns True when the user opted in.
 */
function readCinematicEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

/**
 * Persist cinematic preference and notify subscribers.
 *
 * @param enabled - Whether cinematic atmosphere is on.
 */
function writeCinematicEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
  } catch {
    // Ignore quota / private-mode failures.
  }
  window.dispatchEvent(new Event("job-raider-cinematic-change"));
}

function subscribe(onStoreChange: () => void): () => void {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener("job-raider-cinematic-change", onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener("job-raider-cinematic-change", onStoreChange);
  };
}

/**
 * Subscribe to the cinematic atmosphere preference (default off).
 *
 * @returns Tuple of enabled flag and setter.
 */
export function useCinematicPreference(): [
  boolean,
  (enabled: boolean) => void,
] {
  const enabled = useSyncExternalStore(
    subscribe,
    readCinematicEnabled,
    () => false,
  );

  const setEnabled = useCallback((next: boolean) => {
    writeCinematicEnabled(next);
  }, []);

  return [enabled, setEnabled];
}

/**
 * Sync ``data-cinematic`` on ``document.documentElement`` with preference.
 *
 * Renders nothing; mount once under the app shell.
 */
export function CinematicDocumentSync(): null {
  const [enabled] = useCinematicPreference();
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncMotion = () => setReducedMotion(mq.matches);
    syncMotion();
    mq.addEventListener("change", syncMotion);
    return () => mq.removeEventListener("change", syncMotion);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (enabled) {
      root.setAttribute("data-cinematic", "on");
    } else {
      root.removeAttribute("data-cinematic");
    }
    if (reducedMotion) {
      root.setAttribute("data-reduced-motion", "on");
    } else {
      root.removeAttribute("data-reduced-motion");
    }
  }, [enabled, reducedMotion]);

  return null;
}
