"use client";

import { useState } from "react";
import { Search, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { useAppState } from "@/app/providers";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { SearchBar } from "@/components/jobs/search-bar";
import { JobListItem } from "@/components/jobs/job-list-item";
import { JobDetail } from "@/components/jobs/job-detail";
import { PAGE_SIZE } from "@/lib/utils/constants";
import { createLogger } from "@/lib/logger";
import { formatDatetime } from "@/lib/utils/format";
import type { JobSearchRequest } from "@/lib/api/jobs";
import {
  useJobSearch,
  useLatestShortlist,
  useSavedAndExternalJobIds,
  useSaveJob,
  useMarkAppliedElsewhere,
  useApplyJob,
} from "@/lib/hooks/use-jobs";
import { useMediaQuery } from "@/lib/hooks/use-media-query";
import type { JobListing } from "@/lib/types/api";
import Link from "next/link";

/** Tailwind ``lg`` breakpoint: below this, job detail opens in a sheet. */
const MOBILE_JOBS_QUERY = "(max-width: 1023px)";

const logger = createLogger("JobsPage");

/**
 * Jobs search and browse page.
 *
 * Defaults to the latest discover shortlist from Pipeline. A committed search
 * replaces that feed until cleared. Apply remains an explicit per-job action.
 */
export default function JobsPage() {
  const { selectedJobId, setSelectedJobId, jobsPage, setJobsPage } =
    useAppState();
  const isCompact = useMediaQuery(MOBILE_JOBS_QUERY);

  const [searchParams, setSearchParams] = useState<JobSearchRequest | null>(
    null,
  );
  const [googleQuery, setGoogleQuery] = useState<string | null>(null);
  /** When true, ignore shortlist and wait for a live search. */
  const [preferSearch, setPreferSearch] = useState(false);

  const shortlist = useLatestShortlist();
  const search = useJobSearch(searchParams);
  const { savedIds, externalIds } = useSavedAndExternalJobIds();
  const save = useSaveJob();
  const markApplied = useMarkAppliedElsewhere();
  const apply = useApplyJob();

  const showingShortlist =
    !preferSearch && searchParams == null && !googleQuery;
  const shortlistJobs = shortlist.data?.jobs ?? [];
  const hasShortlist = showingShortlist && shortlistJobs.length > 0;

  const jobs =
    preferSearch || searchParams != null
      ? (search.data?.jobs ?? [])
      : shortlistJobs;
  const totalPages = Math.ceil(jobs.length / PAGE_SIZE);
  const pageJobs = jobs.slice(jobsPage * PAGE_SIZE, (jobsPage + 1) * PAGE_SIZE);
  const selectedJob = jobs.find((j) => j.job_id === selectedJobId) ?? null;

  const listLoading = showingShortlist ? shortlist.isLoading : search.isLoading;
  const listError = showingShortlist ? shortlist.error : search.error;

  const isSaved = (id: string) => savedIds.has(id);
  const isAppliedExternally = (id: string) => externalIds.has(id);

  /**
   * Shared JobDetail actions for desktop panel and mobile sheet.
   *
   * @param job - Currently selected listing.
   */
  const renderJobDetail = (job: JobListing) => (
    <JobDetail
      job={job}
      isSaved={isSaved(job.job_id)}
      isAppliedExternally={isAppliedExternally(job.job_id)}
      onSave={() =>
        save.mutate({
          id: job.job_id,
          saved: isSaved(job.job_id),
        })
      }
      onApply={() => apply.mutate(job.job_id)}
      onMarkAppliedExternally={() =>
        markApplied.mutate({
          id: job.job_id,
          title: job.title,
          company: job.company,
        })
      }
    />
  );

  /**
   * Commit a structured job search and reset pagination/selection.
   *
   * @param request - Search request payload from the search bar.
   */
  const handleSearch = (request: JobSearchRequest) => {
    logger.info(`Committed search request: ${JSON.stringify(request)}`);
    setPreferSearch(true);
    setSearchParams(request);
    setGoogleQuery(null);
    setJobsPage(0);
    setSelectedJobId(null);
  };

  /**
   * Switch to the Google Jobs fallback panel for a free-text query.
   *
   * @param query - Google search query string.
   */
  const handleGoogleSearch = (query: string) => {
    logger.info(`Google search triggered - query: ${query}`);
    setPreferSearch(true);
    setGoogleQuery(query);
    setSearchParams(null);
    setSelectedJobId(null);
  };

  /**
   * Return to the latest discover shortlist feed.
   */
  const showShortlist = () => {
    setPreferSearch(false);
    setSearchParams(null);
    setGoogleQuery(null);
    setJobsPage(0);
    setSelectedJobId(null);
    shortlist.refetch();
  };

  const renderJobBrowser = () => (
    <div className="flex flex-1 flex-col gap-4 min-h-0 overflow-hidden lg:flex-row">
      <div className="flex w-full shrink-0 flex-col gap-2 overflow-y-auto lg:w-96">
        <p className="text-xs text-muted-foreground">
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
            />
          ))}
        </div>

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

      {isCompact ? (
        <Sheet
          open={selectedJob != null}
          onOpenChange={(open) => {
            if (!open) setSelectedJobId(null);
          }}
        >
          <SheetContent
            side="bottom"
            className="flex h-[90vh] max-h-[90vh] w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-none"
          >
            <SheetHeader className="shrink-0 border-b border-border pr-12">
              <SheetTitle className="truncate">
                {selectedJob?.title ?? "Job details"}
              </SheetTitle>
              <SheetDescription className="truncate">
                {selectedJob?.company ?? "Selected listing"}
              </SheetDescription>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {selectedJob ? renderJobDetail(selectedJob) : null}
            </div>
          </SheetContent>
        </Sheet>
      ) : (
        <div className="hidden min-h-0 flex-1 lg:block">
          {selectedJob ? (
            renderJobDetail(selectedJob)
          ) : (
            <EmptyState
              title="Select a job"
              description="Choose a listing from the left to see full details. Apply is only when you choose it."
              className="h-full"
            />
          )}
        </div>
      )}
    </div>
  );

  return (
    <PageContainer
      variant="full-bleed"
      className="h-full flex flex-col gap-4 space-y-0"
    >
      <PageHeader
        title="Jobs"
        subtitle="Review the latest discover shortlist, or run a live search."
      />

      {showingShortlist && shortlist.data?.run_id && (
        <div className="rounded-lg border bg-card px-4 py-3 text-sm">
          <p className="text-foreground">
            Showing {shortlist.data.total} jobs from pipeline run{" "}
            <code className="font-mono text-xs">
              {shortlist.data.run_id.slice(0, 12)}…
            </code>
            {shortlist.data.jobs_scraped > 0
              ? ` (${shortlist.data.jobs_scraped} scraped)`
              : ""}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {shortlist.data.created_at
              ? `Saved ${formatDatetime(shortlist.data.created_at)}`
              : "Latest discover shortlist"}
            {shortlist.data.keywords?.length
              ? ` · ${shortlist.data.keywords.join(", ")}`
              : ""}
            {" · "}
            <Link href="/pipeline" className="underline underline-offset-2">
              Run discover again
            </Link>
          </p>
        </div>
      )}

      {!showingShortlist && shortlistJobs.length > 0 && (
        <div className="flex items-center justify-between rounded-lg border bg-muted/40 px-4 py-2 text-sm">
          <span className="text-muted-foreground">
            Live search active — shortlist still available
          </span>
          <Button size="sm" variant="outline" onClick={showShortlist}>
            Show shortlist
          </Button>
        </div>
      )}

      <SearchBar onSearch={handleSearch} onGoogleSearch={handleGoogleSearch} />

      {listLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          {showingShortlist ? "Loading shortlist…" : "Searching…"}
        </div>
      )}

      {listError && (
        <QueryErrorBanner
          title={
            showingShortlist ? "Could not load shortlist" : "Search failed"
          }
          message={listError.message}
        />
      )}

      {googleQuery ? (
        <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed bg-muted/30">
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <div className="rounded-full bg-primary/10 p-4">
                <Search className="h-8 w-8 text-primary" />
              </div>
            </div>
            <div>
              <p className="text-lg font-medium text-foreground">
                Google Jobs Search
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Searching for:{" "}
                <span className="font-medium">{googleQuery}</span>
              </p>
            </div>
            <a
              href={`https://www.google.com/search?q=${encodeURIComponent(`${googleQuery} jobs`)}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <ExternalLink className="h-4 w-4" />
              Open Google Jobs Search
            </a>
            <p className="text-xs text-muted-foreground">
              No job sources selected — using Google as the default search
              engine
            </p>
          </div>
        </div>
      ) : showingShortlist && !listLoading && !listError && !hasShortlist ? (
        <EmptyState
          title="No discover shortlist yet"
          description="Run Discover on Pipeline to scrape and score jobs, then review them here before applying."
          icon={<Search className="h-8 w-8" />}
          action={{ label: "Open Pipeline", href: "/pipeline" }}
        />
      ) : preferSearch &&
        searchParams == null &&
        !search.isLoading &&
        !googleQuery ? (
        <EmptyState
          title="Run a search…"
          description="Enter keywords and filters above to browse matching job listings."
          icon={<Search className="h-8 w-8" />}
        />
      ) : (preferSearch || searchParams != null) &&
        jobs.length === 0 &&
        !listLoading &&
        !listError ? (
        <EmptyState
          title="No jobs found"
          description="Try different keywords, locations, or sources and search again."
          icon={<Search className="h-8 w-8" />}
        />
      ) : jobs.length > 0 && !listLoading ? (
        renderJobBrowser()
      ) : null}
    </PageContainer>
  );
}
