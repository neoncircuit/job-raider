"use client";

import { useDateTimePrefs } from "@/lib/hooks/use-datetime-prefs";

/**
 * Re-render page content when Appearance date/time prefs change.
 *
 * formatDate/formatDatetime read prefs from localStorage; this subscription
 * makes open pages refresh labels without a hard reload.
 *
 * @param children - Main page content.
 */
export function DatetimePrefsRefresh({
  children,
}: {
  children: React.ReactNode;
}) {
  useDateTimePrefs();
  return <>{children}</>;
}
