import { describe, expect, it } from "vitest";
import {
  DEFAULT_DATE_TIME_PREFS,
  formatDateTimeWithPrefs,
  formatDateWithPrefs,
  normalizeDateTimePrefs,
  readDateTimePrefs,
  resolveTimeZone,
  timeZoneFromLocation,
} from "@/lib/datetime-prefs";

describe("datetime-prefs", () => {
  it("maps Singapore location to Asia/Singapore", () => {
    expect(timeZoneFromLocation("Singapore, Singapore")).toBe("Asia/Singapore");
  });

  it("returns null for unknown locations", () => {
    expect(timeZoneFromLocation("Atlantis")).toBeNull();
  });

  it("resolves system mode without a fixed zone", () => {
    expect(
      resolveTimeZone({
        ...DEFAULT_DATE_TIME_PREFS,
        timeZoneMode: "system",
      }),
    ).toBeUndefined();
  });

  it("resolves profile location mode from contact location", () => {
    expect(
      resolveTimeZone(
        {
          ...DEFAULT_DATE_TIME_PREFS,
          timeZoneMode: "profile_location",
        },
        "London, UK",
      ),
    ).toBe("Europe/London");
  });

  it("falls back when profile location cannot be mapped", () => {
    expect(
      resolveTimeZone(
        {
          ...DEFAULT_DATE_TIME_PREFS,
          timeZoneMode: "profile_location",
        },
        "Somewhere Unknown",
      ),
    ).toBeUndefined();
  });

  it("uses manual IANA zone when selected", () => {
    expect(
      resolveTimeZone({
        format: "system",
        timeZoneMode: "manual",
        manualTimeZone: "UTC",
      }),
    ).toBe("UTC");
  });

  it("formats ISO-like datetimes in a fixed zone", () => {
    const formatted = formatDateTimeWithPrefs("2026-08-12T06:00:00.000Z", {
      format: "iso",
      timeZoneMode: "manual",
      manualTimeZone: "UTC",
    });
    expect(formatted).toMatch(/2026-08-12/);
    expect(formatted).toMatch(/06:00/);
  });

  it("formats date-only values without a time component", () => {
    const formatted = formatDateWithPrefs("2026-08-12T06:00:00.000Z", {
      format: "iso",
      timeZoneMode: "manual",
      manualTimeZone: "UTC",
    });
    expect(formatted).toBe("2026-08-12");
  });

  it("normalizes invalid stored prefs to defaults", () => {
    expect(normalizeDateTimePrefs({ format: "nope", timeZoneMode: 1 })).toBe(
      DEFAULT_DATE_TIME_PREFS,
    );
  });

  it("returns a stable snapshot across repeated reads", () => {
    const first = readDateTimePrefs();
    const second = readDateTimePrefs();
    expect(first).toBe(second);
  });
});
