"use client";

import { useState, useEffect, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Search, Bookmark, BookmarkCheck, ExternalLink, MapPin, Building2, Clock, ChevronDown } from "lucide-react";
import { jobsApi } from "@/lib/api/jobs";
import { applicationsApi } from "@/lib/api/applications";
import type { JobListing, JobSearchResponse } from "@/lib/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAppState } from "@/app/providers";
import { cn } from "@/lib/utils/cn";
import { formatDate, formatSalaryRange } from "@/lib/utils/format";
import { formatJobDescription, isBulletPoint, cleanBulletPoint } from "@/lib/utils/job-description";
import { SOURCE_COLORS, DEFAULT_SOURCES, PAGE_SIZE } from "@/lib/utils/constants";
import { JobClassificationDisplay } from "@/components/job-classification";
import { TrustAnalysisDisplay, TrustTierBadge } from "@/components/trust-analysis";

// ── Experience/Job Type selector dropdown ────────────────────────────────────────

const EXPERIENCE_OPTIONS = [
  { value: "Entry Level", label: "Entry Level" },
  { value: "Mid Level", label: "Mid Level" },
  { value: "Senior", label: "Senior" },
  { value: "Lead", label: "Lead" },
  { value: "Principal", label: "Principal" },
  { value: "Executive", label: "Executive" },
  { value: "Internship", label: "Internship" },
  { value: "Full-time", label: "Full-time" },
  { value: "Part-time", label: "Part-time" },
  { value: "Contract", label: "Contract" },
  { value: "Freelance", label: "Freelance" },
  { value: "Temporary", label: "Temporary" },
] as const;

function ExperienceSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (s: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const toggle = (val: string) =>
    onChange(selected.includes(val) ? selected.filter((s) => s !== val) : [...selected, val]);

  const label = selected.length === 0 ? "All levels" : `${selected.length} selected`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors",
          selected.length === 0
            ? "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
            : "border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
        )}
      >
        <ChevronDown className={cn("h-3.5 w-3.5 text-gray-400 transition-transform", open && "rotate-180")} />
        {label}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 min-w-[200px] rounded-lg border bg-white p-2 shadow-lg">
          <div className="max-h-[300px] overflow-y-auto space-y-0.5">
            {EXPERIENCE_OPTIONS.map((opt) => {
              const checked = selected.includes(opt.value);
              return (
                <label
                  key={opt.value}
                  className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(opt.value)}
                    className="h-3.5 w-3.5 accent-indigo-600"
                  />
                  <span className={cn("flex-1 text-sm", checked ? "font-medium text-gray-900" : "text-gray-500")}>
                    {opt.label}
                  </span>
                </label>
              );
            })}
          </div>
          <div className="mt-1 flex gap-1 border-t pt-1">
            <button
              type="button"
              onClick={() => { onChange(EXPERIENCE_OPTIONS.map(o => o.value)); setOpen(false); }}
              className="flex-1 rounded px-2 py-1 text-center text-xs text-indigo-600 hover:bg-indigo-50"
            >
              All
            </button>
            <button
              type="button"
              onClick={() => { onChange([]); setOpen(false); }}
              className="flex-1 rounded px-2 py-1 text-center text-xs text-gray-500 hover:bg-gray-50"
            >
              None
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Source selector dropdown ──────────────────────────────────────────────────

function SourceSelector({
  available,
  selected,
  onChange,
}: {
  available: string[];
  selected: string[];
  onChange: (s: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const toggle = (src: string) =>
    onChange(selected.includes(src) ? selected.filter((s) => s !== src) : [...selected, src]);

  const label =
    selected.length === 0
      ? "No sources"
      : selected.length === available.length
      ? "All sources"
      : `${selected.length} source${selected.length > 1 ? "s" : ""}`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors",
          selected.length === 0
            ? "border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100"
            : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
        )}
      >
        <ChevronDown className={cn("h-3.5 w-3.5 text-gray-400 transition-transform", open && "rotate-180")} />
        {label}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 min-w-[180px] rounded-lg border bg-white p-2 shadow-lg">
          {available.map((src) => {
            const checked = selected.includes(src);
            return (
              <label
                key={src}
                className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(src)}
                  className="h-3.5 w-3.5 accent-indigo-600"
                />
                <span className={cn("flex-1 text-sm capitalize", checked ? "font-medium text-gray-900" : "text-gray-500")}>
                  {src}
                </span>
                <Badge className={cn("text-[10px] px-1.5 py-0", SOURCE_COLORS[src.toLowerCase()] ?? "bg-gray-500 text-white")}>
                  {src}
                </Badge>
              </label>
            );
          })}
          <div className="mt-1 flex gap-1 border-t pt-1">
            <button
              type="button"
              onClick={() => { onChange(available); setOpen(false); }}
              className="flex-1 rounded px-2 py-1 text-center text-xs text-indigo-600 hover:bg-indigo-50"
            >
              All
            </button>
            <button
              type="button"
              onClick={() => { onChange([]); setOpen(false); }}
              className="flex-1 rounded px-2 py-1 text-center text-xs text-gray-500 hover:bg-gray-50"
            >
              None
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Search form ───────────────────────────────────────────────────────────────

interface SearchValues {
  keywords: string;
  location: string;
  remoteOnly: boolean;
  limit: number;
}

function SearchBar({ onSearch, onGoogleSearch }: {
  onSearch: (results: { total: number; jobs: JobListing[] }) => void;
  onGoogleSearch: (query: string) => void;
}) {
  const { register, handleSubmit, watch, setValue } = useForm<SearchValues>({
    defaultValues: { keywords: "", location: "", remoteOnly: false, limit: 50 },
  });

  const sourcesQuery = useQuery({
    queryKey: ["job-sources"],
    queryFn: jobsApi.getSources,
    staleTime: Infinity,
  });

  const available = sourcesQuery.data?.sources ?? DEFAULT_SOURCES;
  const [selectedSources, setSelectedSources] = useState<string[]>(DEFAULT_SOURCES);
  const [initialized, setInitialized] = useState(false);
  const [selectedExperience, setSelectedExperience] = useState<string[]>([]);

  // Sync selected to full source list once backend responds
  useEffect(() => {
    if (!initialized && sourcesQuery.data?.sources) {
      setSelectedSources(sourcesQuery.data.sources);
      setInitialized(true);
    }
  }, [sourcesQuery.data, initialized]);

  const noSources = selectedSources.length === 0;

  const search = useMutation({
    mutationFn: (v: SearchValues) =>
      jobsApi.search({
        keywords: v.keywords.split(/[\s,]+/).filter(Boolean),
        locations: v.location ? [v.location] : [],
        sources: selectedSources,
        limit: v.limit,
        remote_only: v.remoteOnly,
        experience_levels: selectedExperience.length > 0 ? selectedExperience as any : undefined,
      }),
    onSuccess: (data) => onSearch({ total: data.total, jobs: data.jobs }),
    onError: () => toast.error("Search failed. Is the backend running?"),
  });

  const remoteOnly = watch("remoteOnly");

  const handleSubmit_ = handleSubmit((v) => {
    if (noSources) {
      // No sources selected — trigger Google search inline
      const q = [v.keywords, v.location, "jobs"].filter(Boolean).join(" ");
      onGoogleSearch(q);
      return;
    }
    search.mutate(v);
  });

  return (
    <form onSubmit={handleSubmit_} className="flex flex-wrap gap-3 items-end">
      <div className="flex-1 min-w-[200px] space-y-1">
        <Label>Keywords</Label>
        <Input placeholder="Python, FastAPI, remote…" {...register("keywords")} />
      </div>
      <div className="w-40 space-y-1">
        <Label>Location</Label>
        <Input placeholder="Singapore" {...register("location")} />
      </div>
      <div className="space-y-1">
        <Label>Sources</Label>
        <SourceSelector available={available} selected={selectedSources} onChange={setSelectedSources} />
      </div>
      <div className="space-y-1">
        <Label>Experience</Label>
        <ExperienceSelector selected={selectedExperience} onChange={setSelectedExperience} />
      </div>
      <div className="flex items-center gap-2 pb-0.5">
        <Switch
          id="remote"
          checked={remoteOnly}
          onCheckedChange={(v) => setValue("remoteOnly", v)}
        />
        <Label htmlFor="remote" className="cursor-pointer">Remote only</Label>
      </div>
      <Button
        type="submit"
        disabled={search.isPending}
        variant={noSources ? "outline" : "default"}
      >
        {noSources ? (
          <><Search className="mr-1.5 h-4 w-4" />Search Google</>
        ) : search.isPending ? (
          <><Search className="mr-1.5 h-4 w-4" />Searching…</>
        ) : (
          <><Search className="mr-1.5 h-4 w-4" />Search</>
        )}
      </Button>
    </form>
  );
}

// ── Job list item ─────────────────────────────────────────────────────────────

function JobListItem({
  job,
  isSelected,
  isSaved,
  isAppliedExternally,
  onClick,
  onSave,
  onMarkAppliedExternally,
}: {
  job: JobListing;
  isSelected: boolean;
  isSaved: boolean;
  isAppliedExternally: boolean;
  onClick: () => void;
  onSave: (e: React.MouseEvent) => void;
  onMarkAppliedExternally: (e: React.MouseEvent) => void;
}) {
  const sourceColor = SOURCE_COLORS[job.source.toLowerCase()] ?? "bg-gray-500 text-white";

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors hover:border-blue-300 hover:bg-blue-50",
        isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900 text-sm">{job.title}</p>
          <p className="truncate text-xs text-gray-500">{job.company}</p>
        </div>
        <button
          onClick={onSave}
          className="shrink-0 text-gray-400 hover:text-blue-600"
          aria-label={isSaved ? "Unsave" : "Save"}
        >
          {isSaved ? (
            <BookmarkCheck className="h-4 w-4 text-blue-600" />
          ) : (
            <Bookmark className="h-4 w-4" />
          )}
        </button>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        <Badge className={cn("text-[10px] px-1.5 py-0", sourceColor)}>
          {job.source}
        </Badge>
        {job.is_remote && (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">Remote</Badge>
        )}
        {isAppliedExternally && (
          <Badge className="text-[10px] px-1.5 py-0 bg-gray-500 text-white">
            Applied Elsewhere
          </Badge>
        )}
        {job.already_applied && (
          <Badge className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-800">
            Applied
          </Badge>
        )}
        {job.relevance_score != null && (
          <Badge
            className={cn(
              "text-[10px] px-1.5 py-0",
              job.relevance_score >= 80 ? "bg-green-100 text-green-800" :
              job.relevance_score >= 60 ? "bg-yellow-100 text-yellow-800" :
              "bg-red-100 text-red-800"
            )}
          >
            {job.relevance_score}/100
          </Badge>
        )}
      </div>
    </button>
  );
}

// ── Job detail panel ──────────────────────────────────────────────────────────

function JobDetail({ job, isSaved, isAppliedExternally, onSave, onApply, onMarkAppliedExternally, onClassify, isClassifying, onAnalyzeTrust, isAnalyzingTrust }: {
  job: JobListing;
  isSaved: boolean;
  isAppliedExternally: boolean;
  onSave: () => void;
  onApply: () => void;
  onMarkAppliedExternally: () => void;
  onClassify: () => void;
  isClassifying: boolean;
  onAnalyzeTrust: () => void;
  isAnalyzingTrust: boolean;
}) {
  return (
    <div className="flex flex-col h-full rounded-lg border bg-white">
      {/* Fixed header section */}
      <div className="p-5 space-y-4 border-b">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-gray-900 truncate">{job.title}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                {job.company}
              </span>
              {job.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {job.location}
                </span>
              )}
              {job.posted_date && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {formatDate(job.posted_date)}
                </span>
              )}
            </div>
          </div>
          {job.source_url && (
            <a
              href={job.source_url}
              target="_blank"
              rel="noreferrer"
              className="shrink-0 text-blue-600 hover:text-blue-800"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>

        {/* Salary */}
        {job.salary_range && (
          <p className="text-sm font-medium text-green-700">{formatSalaryRange(job.salary_range)}</p>
        )}

        {/* Job metadata badges */}
        <div className="flex flex-wrap gap-2">
          {/* Source */}
          <Badge className={cn("text-xs", SOURCE_COLORS[job.source.toLowerCase()] ?? "bg-gray-500 text-white")}>
            {job.source}
          </Badge>

          {/* Already Applied (scraper-detected) */}
          {job.already_applied && (
            <Badge className="text-xs bg-emerald-100 text-emerald-800">
              Applied
            </Badge>
          )}

          {/* Work Mode */}
          {job.work_mode && job.work_mode !== "On-site" && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                job.work_mode === "Remote" ? "border-green-200 bg-green-50 text-green-700" :
                job.work_mode === "Hybrid" ? "border-blue-200 bg-blue-50 text-blue-700" :
                "border-gray-200 text-gray-600"
              )}
            >
              {job.work_mode}
            </Badge>
          )}

          {/* Job Type */}
          {job.job_type && job.job_type !== "Full-time" && (
            <Badge variant="outline" className="text-xs border-purple-200 bg-purple-50 text-purple-700">
              {job.job_type}
            </Badge>
          )}

          {/* Experience Level */}
          {job.experience_level && job.experience_level !== "Not Specified" && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                job.experience_level === "Internship" ? "border-yellow-200 bg-yellow-50 text-yellow-700" :
                job.experience_level === "Entry Level" ? "border-sky-200 bg-sky-50 text-sky-700" :
                job.experience_level === "Mid Level" ? "border-indigo-200 bg-indigo-50 text-indigo-700" :
                job.experience_level === "Senior" ? "border-violet-200 bg-violet-50 text-violet-700" :
                job.experience_level === "Lead" ? "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700" :
                "border-gray-200 text-gray-600"
              )}
            >
              {job.experience_level}
            </Badge>
          )}

          {/* Trust Tier Badge */}
          {job.trust_analysis && (
            <TrustTierBadge tier={job.trust_analysis.tier} />
          )}
          {!job.trust_analysis && job.scam_score != null && job.scam_score > 0.5 && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                job.scam_score > 0.7
                  ? "border-red-300 bg-red-50 text-red-700"
                  : "border-amber-300 bg-amber-50 text-amber-700"
              )}
            >
              {job.scam_score > 0.7 ? "High Risk" : "Review"}
            </Badge>
          )}
        </div>
      </div>

      {/* Scrollable content section */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {/* Skills */}
        {(job.skills?.length ?? 0) > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Skills</p>
            <div className="flex flex-wrap gap-1.5">
              {(job.skills ?? []).slice(0, 12).map((s) => (
                <Badge key={s.name} variant={s.is_required ? "default" : "secondary"} className="text-xs">
                  {s.name}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* LLM-based Classification */}
        {job.classification && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Job Analysis</p>
            <JobClassificationDisplay classification={job.classification} />
          </div>
        )}

        {/* Trust Analysis */}
        {job.trust_analysis && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Trust Analysis</p>
            <TrustAnalysisDisplay analysis={job.trust_analysis} />
          </div>
        )}

        {/* Description */}
        {job.description && (
          <div className="flex-1 overflow-y-auto">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Job Description</p>
            <div className="space-y-4">
              {formatJobDescription(job.description).map((section, idx) => (
                <div key={idx} className="space-y-2">
                  {section.title && (
                    <h3 className="text-sm font-semibold text-gray-900 capitalize">
                      {section.title}
                    </h3>
                  )}
                  <div className="space-y-1.5">
                    {section.content.map((line, lineIdx) => {
                      const isBullet = isBulletPoint(line);
                      const cleanText = cleanBulletPoint(line);

                      return (
                        <div
                          key={lineIdx}
                          className={cn(
                            "text-sm text-gray-600",
                            isBullet ? "flex gap-2" : "leading-relaxed"
                          )}
                        >
                          {isBullet && (
                            <span className="shrink-0 text-gray-400 mt-0.5">•</span>
                          )}
                          <span>{cleanText}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Fixed footer with actions */}
      <div className="p-4 border-t bg-gray-50 space-y-3">
        <div className="flex gap-2">
          {job.already_applied ? (
            <Button size="sm" disabled className="flex-1" variant="secondary">
              Applied
            </Button>
          ) : job.apply_method === "external_site" && job.source_url ? (
            <div className="flex gap-2 flex-1">
              <a
                href={job.source_url}
                target="_blank"
                rel="noreferrer"
                className="flex-1"
              >
                <Button size="sm" className="w-full">
                  Apply on {job.source === "jsearch" ? "Job Board" : job.source}
                </Button>
              </a>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  navigator.clipboard.writeText(job.source_url!);
                  toast.success("Link copied to clipboard");
                }}
              >
                Copy Link
              </Button>
            </div>
          ) : (
            <Button size="sm" onClick={onApply} className="flex-1">
              Auto Apply
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={onSave}>
            {isSaved ? "Unsave" : "Save"}
          </Button>
          <Button
            size="sm"
            variant={isAppliedExternally ? "secondary" : "outline"}
            onClick={onMarkAppliedExternally}
            disabled={isAppliedExternally}
          >
            {isAppliedExternally ? "Applied Elsewhere" : "Applied Elsewhere?"}
          </Button>
        </div>
        {!job.classification && (
          <Button
            size="sm"
            variant="outline"
            onClick={onClassify}
            disabled={isClassifying}
            className="w-full"
          >
            {isClassifying ? "Analyzing..." : "Analyze with AI"}
          </Button>
        )}
        {!job.trust_analysis && (
          <Button
            size="sm"
            variant="outline"
            onClick={onAnalyzeTrust}
            disabled={isAnalyzingTrust}
            className="w-full"
          >
            {isAnalyzingTrust ? "Analyzing Trust..." : "Analyze Trust"}
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const { selectedJobId, setSelectedJobId, jobsPage, setJobsPage, searchResults, setSearchResults, savedJobIds, addSavedJobId, removeSavedJobId } =
    useAppState();

  const [googleQuery, setGoogleQuery] = useState<string | null>(null);

  const jobs = searchResults?.jobs ?? [];
  const totalPages = Math.ceil(jobs.length / PAGE_SIZE);
  const pageJobs = jobs.slice(jobsPage * PAGE_SIZE, (jobsPage + 1) * PAGE_SIZE);
  const selectedJob = jobs.find((j) => j.job_id === selectedJobId) ?? null;
  const isSaved = (id: string) => savedJobIds.has(id);

  const save = useMutation({
    mutationFn: ({ id, saved }: { id: string; saved: boolean }) =>
      applicationsApi.action(id, saved ? "unsave" : "save"),
    onSuccess: (_, { id, saved }) => {
      saved ? removeSavedJobId(id) : addSavedJobId(id);
      toast.success(saved ? "Removed from saved" : "Job saved");
    },
    onError: () => toast.error("Action failed"),
  });

  const apply = useMutation({
    mutationFn: async (id: string) => {
      console.log("[Auto Apply] Starting application for job:", id);
      try {
        const result = await jobsApi.apply(id, true);
        console.log("[Auto Apply] Application result:", result);
        return result;
      } catch (error) {
        console.error("[Auto Apply] Application failed:", error);
        throw error;
      }
    },
    onSuccess: (data) => {
      console.log("[Auto Apply] Application successful:", data);
      toast.success(data.message || "Application submitted (dry run)");
    },
    onError: (error) => {
      console.error("[Auto Apply] Error callback:", error);
      if (error instanceof Error) {
        toast.error(`Apply failed: ${error.message}`);
      } else {
        toast.error("Apply failed. Check console for details.");
      }
    },
  });

  // Track externally applied jobs
  const [externallyAppliedJobIds, setExternallyAppliedJobIds] = useState<Set<string>>(new Set());

  const markAppliedExternally = useMutation({
    mutationFn: (id: string) => applicationsApi.markAppliedExternally(id),
    onSuccess: (_, id) => {
      setExternallyAppliedJobIds((prev) => new Set(prev).add(id));
      toast.success("Marked as applied externally");
    },
    onError: () => toast.error("Failed to mark as applied externally"),
  });

  const classify = useMutation({
    mutationFn: ({ id, job }: { id: string; job: JobListing }) =>
      jobsApi.classify(id, {
        title: job.title,
        company: job.company,
        description: job.description ?? undefined,
        location: job.location ?? undefined,
        source: job.source,
      }),
    onSuccess: (data, { id }) => {
      // Update the job in search results with classification
      setSearchResults((prev: JobSearchResponse | null) => {
        if (!prev) return prev;
        return {
          ...prev,
          jobs: prev.jobs.map((j: JobListing) =>
            j.job_id === id ? { ...j, classification: data.classification } : j
          ),
        };
      });
      toast.success("Job classified successfully");
    },
    onError: () => toast.error("Failed to classify job"),
  });

  const analyzeTrust = useMutation({
    mutationFn: ({ id, job }: { id: string; job: JobListing }) =>
      jobsApi.trustAnalysis(id, {
        title: job.title,
        company: job.company,
        description: job.description ?? undefined,
        location: job.location ?? undefined,
        source: job.source,
      }),
    onSuccess: (data, { id }) => {
      setSearchResults((prev: JobSearchResponse | null) => {
        if (!prev) return prev;
        return {
          ...prev,
          jobs: prev.jobs.map((j: JobListing) =>
            j.job_id === id ? { ...j, trust_analysis: data.trust_analysis } : j
          ),
        };
      });
      toast.success("Trust analysis complete");
    },
    onError: () => toast.error("Failed to analyze trust"),
  });

  const isAppliedExternally = (id: string) => externallyAppliedJobIds.has(id);

  const handleSearch = (results: { total: number; jobs: JobListing[] }) => {
    setSearchResults(results);
    setJobsPage(0);
    setSelectedJobId(null);
    setGoogleQuery(null); // Clear Google search when doing backend search
  };

  const handleGoogleSearch = (query: string) => {
    setGoogleQuery(query);
    setSearchResults(null); // Clear backend results
    setSelectedJobId(null);
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
        <p className="mt-0.5 text-sm text-gray-500">Search and browse job listings.</p>
      </div>

      <SearchBar onSearch={handleSearch} onGoogleSearch={handleGoogleSearch} />

      {googleQuery ? (
        <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed bg-gray-50">
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <div className="rounded-full bg-blue-100 p-4">
                <Search className="h-8 w-8 text-blue-600" />
              </div>
            </div>
            <div>
              <p className="text-lg font-medium text-gray-900">Google Jobs Search</p>
              <p className="mt-1 text-sm text-gray-600">
                Searching for: <span className="font-medium">{googleQuery}</span>
              </p>
            </div>
            <a
              href={`https://www.google.com/search?q=${encodeURIComponent(googleQuery + " jobs")}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <ExternalLink className="h-4 w-4" />
              Open Google Jobs Search
            </a>
            <p className="text-xs text-gray-500">
              No job sources selected — using Google as the default search engine
            </p>
          </div>
        </div>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-gray-400">Run a search to see results.</p>
      ) : (
        <div className="flex flex-1 gap-4 min-h-0 overflow-hidden">
          {/* Left panel — job list */}
          <div className="flex w-80 shrink-0 flex-col gap-2 overflow-y-auto">
            <p className="text-xs text-gray-400">
              {jobs.length} results · page {jobsPage + 1}/{totalPages || 1}
            </p>

            <div className="space-y-1.5">
              {pageJobs.map((j) => (
                <JobListItem
                  key={j.job_id}
                  job={j}
                  isSelected={j.job_id === selectedJobId}
                  isSaved={isSaved(j.job_id)}
                  isAppliedExternally={isAppliedExternally(j.job_id)}
                  onClick={() => setSelectedJobId(j.job_id)}
                  onSave={(e) => {
                    e.stopPropagation();
                    save.mutate({ id: j.job_id, saved: isSaved(j.job_id) });
                  }}
                  onMarkAppliedExternally={(e) => {
                    e.stopPropagation();
                    markAppliedExternally.mutate(j.job_id);
                  }}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={jobsPage === 0}
                  onClick={() => setJobsPage(jobsPage - 1)}
                  className="flex-1"
                >
                  Prev
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={jobsPage >= totalPages - 1}
                  onClick={() => setJobsPage(jobsPage + 1)}
                  className="flex-1"
                >
                  Next
                </Button>
              </div>
            )}
          </div>

          {/* Right panel — detail */}
          <div className="flex-1 min-h-0">
            {selectedJob ? (
              <JobDetail
                job={selectedJob}
                isSaved={isSaved(selectedJob.job_id)}
                isAppliedExternally={isAppliedExternally(selectedJob.job_id)}
                onSave={() => save.mutate({ id: selectedJob.job_id, saved: isSaved(selectedJob.job_id) })}
                onApply={() => apply.mutate(selectedJob.job_id)}
                onMarkAppliedExternally={() => markAppliedExternally.mutate(selectedJob.job_id)}
                onClassify={() => classify.mutate({ id: selectedJob.job_id, job: selectedJob })}
                isClassifying={classify.isPending}
                onAnalyzeTrust={() => analyzeTrust.mutate({ id: selectedJob.job_id, job: selectedJob })}
                isAnalyzingTrust={analyzeTrust.isPending}
              />
            ) : (
              <div className="flex h-full items-center justify-center rounded-lg border border-dashed text-sm text-gray-400">
                Select a job to see details
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
