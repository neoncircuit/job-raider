import type { SalaryRange } from "@/lib/types/api";
import {
  formatDateTimeWithPrefs,
  formatDateWithPrefs,
  readDateTimePrefs,
  readProfileLocationCache,
} from "@/lib/datetime-prefs";

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  if (minutes < 60)
    return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

/**
 * Format a millisecond duration for UI metrics (cover letter timing, etc.).
 *
 * @param ms - Elapsed time in milliseconds.
 * @returns Human-readable duration such as ``843 ms`` or ``12.4 s``.
 */
export function formatDurationMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  return formatDuration(seconds);
}

/**
 * Format a token count for UI metrics (cover letter usage, etc.).
 *
 * @param count - Token count.
 * @returns Locale-formatted count such as ``1,234``, or ``—`` when invalid.
 */
export function formatTokenCount(count: number): string {
  if (!Number.isFinite(count) || count < 0) return "—";
  return new Intl.NumberFormat("en-US").format(Math.round(count));
}

/**
 * Format an ISO datetime using Settings → Appearance date/time prefs.
 *
 * @param isoString - ISO timestamp from the API.
 * @returns Formatted datetime, or ``N/A`` when missing/invalid.
 */
export function formatDatetime(isoString: string | null | undefined): string {
  const formatted = formatDateTimeWithPrefs(
    isoString,
    readDateTimePrefs(),
    readProfileLocationCache(),
  );
  return formatted ?? "N/A";
}

/**
 * Format an ISO date (no time) using Settings → Appearance date/time prefs.
 *
 * @param isoString - ISO date or timestamp from the API.
 * @returns Formatted date, or ``N/A`` when missing/invalid.
 */
export function formatDate(isoString: string | null | undefined): string {
  const formatted = formatDateWithPrefs(
    isoString,
    readDateTimePrefs(),
    readProfileLocationCache(),
  );
  return formatted ?? "N/A";
}

export function formatPercentage(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function truncateText(text: string, maxLength = 300): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "…";
}

export function formatSalaryRange(
  range: SalaryRange | string | null | undefined,
): string {
  if (!range) return "Salary not specified";
  if (typeof range === "string") return range;
  const { min_amount, max_amount, currency, period } = range;
  if (!min_amount && !max_amount) return "Salary not specified";
  // Normalize currency to uppercase
  const normalizedCurrency = (currency || "USD").toUpperCase();
  const fmt = (v: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: normalizedCurrency as
        "USD" | "EUR" | "GBP" | "SGD" | "CAD" | "AUD" | "INR",
      maximumFractionDigits: 0,
    }).format(v);
  if (min_amount && max_amount)
    return `${fmt(min_amount)} – ${fmt(max_amount)} / ${period}`;
  if (min_amount) return `From ${fmt(min_amount)} / ${period}`;
  return `Up to ${fmt(max_amount!)} / ${period}`;
}

/**
 * Normalize currency code to uppercase (ISO 4217 standard).
 */
export function normalizeCurrencyCode(currency: string): string {
  return currency?.toUpperCase() || "USD";
}

export function formatScore(score: number): string {
  return `${score.toFixed(1)}/100`;
}
