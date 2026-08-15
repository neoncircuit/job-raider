/**
 * Local datetime display preferences (format + timezone).
 *
 * Stored in localStorage; used for Profile parse timestamps and other UI clocks.
 */

export type DateTimeFormatId = "system" | "iso" | "dmy" | "mdy" | "long";

export type TimeZoneMode = "system" | "profile_location" | "manual";

export interface DateTimePrefs {
  format: DateTimeFormatId;
  timeZoneMode: TimeZoneMode;
  /** IANA zone used when ``timeZoneMode`` is ``manual``. */
  manualTimeZone: string;
}

export const DATE_TIME_FORMAT_OPTIONS: ReadonlyArray<{
  id: DateTimeFormatId;
  label: string;
  exampleHint: string;
}> = [
  { id: "system", label: "System locale", exampleHint: "Browser default" },
  { id: "iso", label: "ISO-like", exampleHint: "2026-08-12 14:13" },
  { id: "dmy", label: "Day / month / year", exampleHint: "12/08/2026 14:13" },
  { id: "mdy", label: "Month / day / year", exampleHint: "08/12/2026 2:13 PM" },
  { id: "long", label: "Long", exampleHint: "12 August 2026 at 2:13 pm" },
];

export const TIME_ZONE_MODE_OPTIONS: ReadonlyArray<{
  id: TimeZoneMode;
  label: string;
  description: string;
}> = [
  {
    id: "system",
    label: "System time zone",
    description: "Use this device’s current time zone.",
  },
  {
    id: "profile_location",
    label: "From profile location",
    description: "Infer from Profile contact location when possible.",
  },
  {
    id: "manual",
    label: "Choose time zone",
    description: "Pick an explicit IANA time zone.",
  },
];

/** Curated IANA zones for the manual picker (common job-search regions). */
export const MANUAL_TIME_ZONES: ReadonlyArray<{ id: string; label: string }> = [
  { id: "Asia/Singapore", label: "Singapore (UTC+8)" },
  { id: "Asia/Kuala_Lumpur", label: "Kuala Lumpur (UTC+8)" },
  { id: "Asia/Jakarta", label: "Jakarta (UTC+7)" },
  { id: "Asia/Bangkok", label: "Bangkok (UTC+7)" },
  { id: "Asia/Hong_Kong", label: "Hong Kong (UTC+8)" },
  { id: "Asia/Tokyo", label: "Tokyo (UTC+9)" },
  { id: "Asia/Seoul", label: "Seoul (UTC+9)" },
  { id: "Asia/Shanghai", label: "Shanghai (UTC+8)" },
  { id: "Asia/Kolkata", label: "India (UTC+5:30)" },
  { id: "Australia/Sydney", label: "Sydney (UTC+10/+11)" },
  { id: "Europe/London", label: "London (UTC+0/+1)" },
  { id: "Europe/Paris", label: "Paris (UTC+1/+2)" },
  { id: "Europe/Berlin", label: "Berlin (UTC+1/+2)" },
  { id: "America/New_York", label: "New York (UTC−5/−4)" },
  { id: "America/Chicago", label: "Chicago (UTC−6/−5)" },
  { id: "America/Denver", label: "Denver (UTC−7/−6)" },
  { id: "America/Los_Angeles", label: "Los Angeles (UTC−8/−7)" },
  { id: "America/Toronto", label: "Toronto (UTC−5/−4)" },
  { id: "UTC", label: "UTC" },
];

export const DEFAULT_DATE_TIME_PREFS: DateTimePrefs = {
  format: "system",
  timeZoneMode: "system",
  manualTimeZone: "Asia/Singapore",
};

export const DATE_TIME_PREFS_STORAGE_KEY = "job-raider-datetime-prefs";
export const DATE_TIME_PREFS_CHANGE_EVENT = "job-raider-datetime-prefs-change";

const FORMAT_IDS = new Set<DateTimeFormatId>(
  DATE_TIME_FORMAT_OPTIONS.map((option) => option.id),
);
const TIME_ZONE_MODES = new Set<TimeZoneMode>(
  TIME_ZONE_MODE_OPTIONS.map((option) => option.id),
);

/** Heuristic location fragment → IANA zone. */
const LOCATION_TIME_ZONE_RULES: ReadonlyArray<{ pattern: RegExp; tz: string }> =
  [
    { pattern: /\bsingapore\b/i, tz: "Asia/Singapore" },
    { pattern: /\bkuala\s*lumpur\b|\bmalaysia\b/i, tz: "Asia/Kuala_Lumpur" },
    { pattern: /\bjakarta\b|\bindonesia\b/i, tz: "Asia/Jakarta" },
    { pattern: /\bbangkok\b|\bthailand\b/i, tz: "Asia/Bangkok" },
    { pattern: /\bhong\s*kong\b/i, tz: "Asia/Hong_Kong" },
    { pattern: /\btokyo\b|\bjapan\b/i, tz: "Asia/Tokyo" },
    { pattern: /\bseoul\b|\bkorea\b/i, tz: "Asia/Seoul" },
    { pattern: /\bshanghai\b|\bbeijing\b|\bchina\b/i, tz: "Asia/Shanghai" },
    {
      pattern: /\bmumbai\b|\bdelhi\b|\bbengaluru\b|\bindia\b/i,
      tz: "Asia/Kolkata",
    },
    {
      pattern: /\bsydney\b|\bmelbourne\b|\baustralia\b/i,
      tz: "Australia/Sydney",
    },
    {
      pattern: /\blondon\b|\bunited\s*kingdom\b|\bengland\b|\buk\b/i,
      tz: "Europe/London",
    },
    { pattern: /\bparis\b|\bfrance\b/i, tz: "Europe/Paris" },
    { pattern: /\bberlin\b|\bgermany\b/i, tz: "Europe/Berlin" },
    {
      pattern: /\bnew\s*york\b|\bnyc\b|\bboston\b|\bwashington\b/i,
      tz: "America/New_York",
    },
    { pattern: /\bchicago\b/i, tz: "America/Chicago" },
    { pattern: /\bdenver\b|\bcolorado\b/i, tz: "America/Denver" },
    {
      pattern:
        /\blos\s*angeles\b|\bsan\s*francisco\b|\bseattle\b|\bcalifornia\b/i,
      tz: "America/Los_Angeles",
    },
    { pattern: /\btoronto\b|\bcanada\b/i, tz: "America/Toronto" },
  ];

/**
 * Return whether a value is a known datetime format id.
 *
 * @param value - Candidate format id.
 * @returns True when the id is supported.
 */
export function isDateTimeFormatId(value: unknown): value is DateTimeFormatId {
  return typeof value === "string" && FORMAT_IDS.has(value as DateTimeFormatId);
}

/**
 * Return whether a value is a known timezone mode.
 *
 * @param value - Candidate mode.
 * @returns True when the mode is supported.
 */
export function isTimeZoneMode(value: unknown): value is TimeZoneMode {
  return (
    typeof value === "string" && TIME_ZONE_MODES.has(value as TimeZoneMode)
  );
}

/**
 * Normalize a partial prefs object into a full valid prefs record.
 *
 * @param raw - Stored or partial prefs.
 * @returns Complete prefs with defaults for missing/invalid fields.
 */
export function normalizeDateTimePrefs(raw: unknown): DateTimePrefs {
  if (!raw || typeof raw !== "object") {
    return DEFAULT_DATE_TIME_PREFS;
  }
  const record = raw as Record<string, unknown>;
  const format = isDateTimeFormatId(record.format)
    ? record.format
    : DEFAULT_DATE_TIME_PREFS.format;
  const timeZoneMode = isTimeZoneMode(record.timeZoneMode)
    ? record.timeZoneMode
    : DEFAULT_DATE_TIME_PREFS.timeZoneMode;
  const manualTimeZone =
    typeof record.manualTimeZone === "string" && record.manualTimeZone.trim()
      ? record.manualTimeZone.trim()
      : DEFAULT_DATE_TIME_PREFS.manualTimeZone;

  if (
    format === DEFAULT_DATE_TIME_PREFS.format &&
    timeZoneMode === DEFAULT_DATE_TIME_PREFS.timeZoneMode &&
    manualTimeZone === DEFAULT_DATE_TIME_PREFS.manualTimeZone
  ) {
    return DEFAULT_DATE_TIME_PREFS;
  }
  return { format, timeZoneMode, manualTimeZone };
}

/** Cached snapshot for ``useSyncExternalStore`` (must be referentially stable). */
let cachedPrefsRaw: string | null | undefined = undefined;
let cachedPrefsSnapshot: DateTimePrefs = DEFAULT_DATE_TIME_PREFS;

/**
 * Return whether two prefs records are equal by value.
 *
 * @param a - First prefs.
 * @param b - Second prefs.
 * @returns True when all fields match.
 */
function prefsEqual(a: DateTimePrefs, b: DateTimePrefs): boolean {
  return (
    a.format === b.format &&
    a.timeZoneMode === b.timeZoneMode &&
    a.manualTimeZone === b.manualTimeZone
  );
}

/**
 * Read datetime prefs from localStorage (browser only).
 *
 * Returns a referentially stable snapshot so ``useSyncExternalStore`` does
 * not enter an infinite update loop.
 *
 * @returns Normalized prefs, or defaults when unavailable.
 */
export function readDateTimePrefs(): DateTimePrefs {
  if (typeof window === "undefined") {
    return DEFAULT_DATE_TIME_PREFS;
  }
  try {
    const raw = window.localStorage.getItem(DATE_TIME_PREFS_STORAGE_KEY);
    if (raw === cachedPrefsRaw) {
      return cachedPrefsSnapshot;
    }
    const next = raw
      ? normalizeDateTimePrefs(JSON.parse(raw))
      : DEFAULT_DATE_TIME_PREFS;
    cachedPrefsRaw = raw;
    cachedPrefsSnapshot = prefsEqual(next, cachedPrefsSnapshot)
      ? cachedPrefsSnapshot
      : next;
    return cachedPrefsSnapshot;
  } catch {
    cachedPrefsRaw = null;
    cachedPrefsSnapshot = DEFAULT_DATE_TIME_PREFS;
    return DEFAULT_DATE_TIME_PREFS;
  }
}

/**
 * Persist datetime prefs and notify subscribers.
 *
 * @param prefs - Prefs to store (normalized before write).
 */
export function writeDateTimePrefs(prefs: DateTimePrefs): void {
  if (typeof window === "undefined") {
    return;
  }
  const normalized = normalizeDateTimePrefs(prefs);
  const serialized = JSON.stringify(normalized);
  window.localStorage.setItem(DATE_TIME_PREFS_STORAGE_KEY, serialized);
  cachedPrefsRaw = serialized;
  cachedPrefsSnapshot = prefsEqual(normalized, cachedPrefsSnapshot)
    ? cachedPrefsSnapshot
    : normalized;
  window.dispatchEvent(new Event(DATE_TIME_PREFS_CHANGE_EVENT));
}

/**
 * Infer an IANA time zone from a free-text profile location.
 *
 * @param location - Profile contact location (e.g. ``Singapore, Singapore``).
 * @returns IANA zone when matched, otherwise null.
 */
export function timeZoneFromLocation(
  location: string | null | undefined,
): string | null {
  const text = (location ?? "").trim();
  if (!text) {
    return null;
  }
  for (const rule of LOCATION_TIME_ZONE_RULES) {
    if (rule.pattern.test(text)) {
      return rule.tz;
    }
  }
  return null;
}

/**
 * Resolve the effective IANA time zone for formatting.
 *
 * @param prefs - User datetime preferences.
 * @param location - Optional profile location for ``profile_location`` mode.
 * @returns IANA zone string, or undefined to use the runtime default.
 */
export function resolveTimeZone(
  prefs: DateTimePrefs,
  location?: string | null,
): string | undefined {
  if (prefs.timeZoneMode === "manual") {
    return prefs.manualTimeZone || undefined;
  }
  if (prefs.timeZoneMode === "profile_location") {
    return timeZoneFromLocation(location) ?? undefined;
  }
  return undefined;
}

/**
 * Build Intl options for a format preset.
 *
 * @param format - Selected format id.
 * @param dateOnly - When true, omit time fields.
 * @returns Locale tag and DateTimeFormat options.
 */
function intlForFormat(
  format: DateTimeFormatId,
  dateOnly = false,
): { locale: string | undefined; options: Intl.DateTimeFormatOptions } {
  if (dateOnly) {
    switch (format) {
      case "iso":
        return {
          locale: "sv-SE",
          options: {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
          },
        };
      case "dmy":
        return {
          locale: "en-GB",
          options: {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
          },
        };
      case "mdy":
        return {
          locale: "en-US",
          options: {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
          },
        };
      case "long":
        return {
          locale: undefined,
          options: { dateStyle: "long" },
        };
      case "system":
      default:
        return {
          locale: undefined,
          options: { dateStyle: "medium" },
        };
    }
  }

  switch (format) {
    case "iso":
      return {
        locale: "sv-SE",
        options: {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        },
      };
    case "dmy":
      return {
        locale: "en-GB",
        options: {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        },
      };
    case "mdy":
      return {
        locale: "en-US",
        options: {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        },
      };
    case "long":
      return {
        locale: undefined,
        options: {
          dateStyle: "long",
          timeStyle: "short",
        },
      };
    case "system":
    default:
      return {
        locale: undefined,
        options: {
          dateStyle: "medium",
          timeStyle: "short",
        },
      };
  }
}

/**
 * Format an ISO value with preferences (shared by date and datetime helpers).
 *
 * @param iso - ISO-8601 timestamp or date.
 * @param prefs - Datetime display preferences.
 * @param location - Profile location when using location-based timezone.
 * @param dateOnly - Format date without time.
 * @returns Formatted string, or null when input is missing/invalid.
 */
function formatWithPrefs(
  iso: string | null | undefined,
  prefs: DateTimePrefs,
  location: string | null | undefined,
  dateOnly: boolean,
): string | null {
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  const { locale, options } = intlForFormat(prefs.format, dateOnly);
  const timeZone = resolveTimeZone(prefs, location);
  try {
    return date.toLocaleString(locale, {
      ...options,
      ...(timeZone ? { timeZone } : {}),
    });
  } catch {
    return dateOnly
      ? date.toLocaleDateString(undefined, { dateStyle: "medium" })
      : date.toLocaleString(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        });
  }
}

/**
 * Format an ISO datetime using local display preferences.
 *
 * @param iso - ISO-8601 timestamp from the API.
 * @param prefs - Datetime display preferences.
 * @param location - Profile location when using location-based timezone.
 * @returns Formatted string, or null when input is missing/invalid.
 */
export function formatDateTimeWithPrefs(
  iso: string | null | undefined,
  prefs: DateTimePrefs = DEFAULT_DATE_TIME_PREFS,
  location?: string | null,
): string | null {
  return formatWithPrefs(iso, prefs, location, false);
}

/**
 * Format an ISO date (no time) using local display preferences.
 *
 * @param iso - ISO-8601 date or timestamp from the API.
 * @param prefs - Datetime display preferences.
 * @param location - Profile location when using location-based timezone.
 * @returns Formatted string, or null when input is missing/invalid.
 */
export function formatDateWithPrefs(
  iso: string | null | undefined,
  prefs: DateTimePrefs = DEFAULT_DATE_TIME_PREFS,
  location?: string | null,
): string | null {
  return formatWithPrefs(iso, prefs, location, true);
}

export const PROFILE_LOCATION_STORAGE_KEY = "job-raider-profile-location";

/**
 * Cache the active profile location for timezone inference across pages.
 *
 * @param location - Profile contact location, or null to clear.
 */
export function writeProfileLocationCache(
  location: string | null | undefined,
): void {
  if (typeof window === "undefined") {
    return;
  }
  const cleaned = (location ?? "").trim();
  if (!cleaned) {
    window.localStorage.removeItem(PROFILE_LOCATION_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(PROFILE_LOCATION_STORAGE_KEY, cleaned);
}

/**
 * Read the cached profile location for timezone inference.
 *
 * @returns Cached location string, or null when unset.
 */
export function readProfileLocationCache(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(PROFILE_LOCATION_STORAGE_KEY);
  } catch {
    return null;
  }
}
