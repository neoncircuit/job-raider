/**
 * Resolve company-mission citation sources for the Cover Letter UI.
 */

export interface MissionSourceCitation {
  index: number;
  url: string;
  title?: string | null;
  domain?: string | null;
  snippet?: string | null;
  kind?: string | null;
}

export interface MissionContextLike {
  status?: string;
  source_url?: string | null;
  source_title?: string | null;
  sources?: MissionSourceCitation[] | null;
}

/**
 * Build the display list of mission citations from API mission_context.
 *
 * Prefers `sources` when present. Falls back to a single card from
 * `source_url` when status is pass. Returns empty when mission did not pass
 * or no URL is available.
 *
 * @param mission - Optional mission_context from generate response.
 * @returns Ordered citation cards (max length enforced by backend).
 */
export function resolveMissionSourceCitations(
  mission: MissionContextLike | null | undefined,
): MissionSourceCitation[] {
  if (!mission || mission.status !== "pass") {
    return [];
  }
  if (Array.isArray(mission.sources) && mission.sources.length > 0) {
    return mission.sources
      .filter((item) => Boolean(item?.url))
      .map((item, i) => ({
        index: item.index ?? i + 1,
        url: item.url,
        title: item.title ?? null,
        domain: item.domain ?? hostnameFromUrl(item.url),
        snippet: item.snippet ?? null,
        kind: item.kind ?? "company_mission",
      }));
  }
  if (mission.source_url) {
    return [
      {
        index: 1,
        url: mission.source_url,
        title: mission.source_title ?? null,
        domain: hostnameFromUrl(mission.source_url),
        snippet: null,
        kind: "company_mission",
      },
    ];
  }
  return [];
}

/**
 * Extract a display hostname from a URL.
 *
 * @param url - Absolute URL string.
 * @returns Hostname without leading www, or the raw URL on parse failure.
 */
export function hostnameFromUrl(url: string): string {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return url;
  }
}
