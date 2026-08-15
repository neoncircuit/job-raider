export const PIPELINE_STAGES = [
  { key: "scrape", label: "Scrape Jobs" },
  { key: "deduplicate", label: "Deduplicate" },
  { key: "filter_scams", label: "Filter Scams" },
  { key: "filter_by_profile", label: "Filter by Profile" },
  { key: "score_and_rank", label: "Score & Rank" },
  { key: "rag_rank", label: "Semantic Re-rank" },
  { key: "detect_auto_submit", label: "Detect Auto-Submit" },
  { key: "generate_resumes", label: "Generate Resumes" },
  { key: "submit_applications", label: "Submit Applications" },
] as const;

/** Stages shown for the default discover-only pipeline mode. */
export const DISCOVER_PIPELINE_STAGES = PIPELINE_STAGES.filter((s) =>
  [
    "scrape",
    "deduplicate",
    "filter_scams",
    "filter_by_profile",
    "score_and_rank",
    "rag_rank",
  ].includes(s.key),
);

/**
 * Theme-aware Tailwind classes for job-source badges.
 *
 * Tinted chips (not solid fills) keep 10px labels readable in light and dark.
 */
export const SOURCE_COLORS: Record<string, string> = {
  linkedin: "border-info/30 bg-info/10 text-info",
  jsearch: "border-primary/30 bg-primary/10 text-primary",
  mycareersfuture: "border-success/30 bg-success/10 text-success",
  jobstreet: "border-warning/30 bg-warning/10 text-warning",
  careersatgov: "border-accent/30 bg-accent/10 text-accent",
  manual: "border-border bg-muted text-muted-foreground",
};

/**
 * Theme-aware Tailwind classes for status badges.
 *
 * applied_elsewhere is secondary so it does not collide with applied (info)
 * or completed (success).
 */
export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-warning/10 text-warning border-warning/30",
  running: "bg-info/10 text-info border-info/30",
  completed: "bg-success/10 text-success border-success/30",
  failed: "bg-destructive/10 text-destructive border-destructive/30",
  cancelled: "border-border bg-muted text-muted-foreground",
  healthy: "bg-success/10 text-success border-success/30",
  degraded: "bg-warning/10 text-warning border-warning/30",
  unhealthy: "bg-destructive/10 text-destructive border-destructive/30",
  unknown: "border-border bg-muted text-muted-foreground",
  applied: "bg-info/10 text-info border-info/30",
  applied_elsewhere: "border-border bg-secondary text-secondary-foreground",
  saved_bookmarked: "bg-info/10 text-info border-info/30",
  not_interested: "border-border bg-muted text-muted-foreground",
  rejected: "bg-destructive/10 text-destructive border-destructive/30",
  under_review: "bg-info/10 text-info border-info/30",
  screening_scheduled: "bg-info/10 text-info border-info/30",
  screening_completed: "bg-info/10 text-info border-info/30",
  technical_scheduled: "bg-info/10 text-info border-info/30",
  technical_completed: "bg-info/10 text-info border-info/30",
  onsite_scheduled: "bg-info/10 text-info border-info/30",
  onsite_completed: "bg-info/10 text-info border-info/30",
  final: "bg-success/10 text-success border-success/30",
  offer: "bg-success/10 text-success border-success/30",
};

export const DEFAULT_SOURCES = ["linkedin", "jsearch"];

export const PAGE_SIZE = 20;
