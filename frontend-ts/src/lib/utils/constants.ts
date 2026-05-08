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

export const SOURCE_COLORS: Record<string, string> = {
  linkedin: "bg-blue-600 text-white",
  jsearch: "bg-indigo-600 text-white",
  manual: "bg-gray-500 text-white",
};

export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
  healthy: "bg-green-100 text-green-800",
  degraded: "bg-yellow-100 text-yellow-800",
  unhealthy: "bg-red-100 text-red-800",
  unknown: "bg-gray-100 text-gray-800",
};

export const DEFAULT_SOURCES = ["linkedin", "jsearch"];

export const PAGE_SIZE = 20;
