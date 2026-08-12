"use client";

import { useCallback, useSyncExternalStore } from "react";
import {
  DATE_TIME_PREFS_CHANGE_EVENT,
  DEFAULT_DATE_TIME_PREFS,
  readDateTimePrefs,
  writeDateTimePrefs,
  type DateTimePrefs,
} from "@/lib/datetime-prefs";

/**
 * Subscribe to localStorage datetime-pref changes (same-tab + cross-tab).
 *
 * @param onStoreChange - Callback when prefs may have changed.
 * @returns Unsubscribe function.
 */
function subscribe(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === "job-raider-datetime-prefs") {
      onStoreChange();
    }
  };
  window.addEventListener(DATE_TIME_PREFS_CHANGE_EVENT, onStoreChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(DATE_TIME_PREFS_CHANGE_EVENT, onStoreChange);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * Subscribe to local datetime display preferences.
 *
 * @returns Current prefs and a setter that persists to localStorage.
 */
export function useDateTimePrefs(): [
  DateTimePrefs,
  (next: DateTimePrefs | ((prev: DateTimePrefs) => DateTimePrefs)) => void,
] {
  const prefs = useSyncExternalStore(
    subscribe,
    readDateTimePrefs,
    () => DEFAULT_DATE_TIME_PREFS,
  );

  const setPrefs = useCallback(
    (next: DateTimePrefs | ((prev: DateTimePrefs) => DateTimePrefs)) => {
      const resolved = typeof next === "function" ? next(readDateTimePrefs()) : next;
      writeDateTimePrefs(resolved);
    },
    [],
  );

  return [prefs, setPrefs];
}
