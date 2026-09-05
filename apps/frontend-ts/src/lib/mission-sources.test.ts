import { describe, expect, it } from "vitest";
import {
  hostnameFromUrl,
  resolveMissionSourceCitations,
} from "@/lib/mission-sources";

describe("resolveMissionSourceCitations", () => {
  it("returns empty when mission is missing or not pass", () => {
    expect(resolveMissionSourceCitations(null)).toEqual([]);
    expect(resolveMissionSourceCitations({ status: "skip" })).toEqual([]);
    expect(resolveMissionSourceCitations({ status: "disabled" })).toEqual([]);
  });

  it("prefers sources array when present", () => {
    const sources = resolveMissionSourceCitations({
      status: "pass",
      source_url: "https://fallback.example/about",
      sources: [
        {
          index: 1,
          url: "https://www.goldenagri.com.sg/about",
          title: "About",
          domain: "goldenagri.com.sg",
        },
      ],
    });
    expect(sources).toHaveLength(1);
    expect(sources[0].url).toContain("goldenagri.com.sg");
  });

  it("falls back to source_url when sources missing", () => {
    const sources = resolveMissionSourceCitations({
      status: "pass",
      source_url: "https://www.example.com/mission",
      source_title: "Mission",
    });
    expect(sources).toEqual([
      {
        index: 1,
        url: "https://www.example.com/mission",
        title: "Mission",
        domain: "example.com",
        snippet: null,
        kind: "company_mission",
      },
    ]);
  });
});

describe("hostnameFromUrl", () => {
  it("strips www", () => {
    expect(hostnameFromUrl("https://www.example.com/path")).toBe("example.com");
  });
});
