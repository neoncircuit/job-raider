"use client";

import { useState } from "react";
import { Search, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
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
import type { JobSearchRequest } from "@/lib/api/jobs";
import {
  useJobSearch,
  useSavedAndExternalJobIds,
  useSaveJob,
  useMarkAppliedElsewhere,
  useApplyJob,
} from "@/lib/hooks/use-jobs";

const logger = createLogger("JobsPage");

/**
 * Jobs search and browse page.
 *
 * Server state lives in TanStack Query; the page only keeps UI state such as
 * the committed search parameters, selected job, pagination, and Google fallback
 * query in React state and Context.
 */
export default function JobsPage() {
  const { selectedJobId, setSelectedJobId, jobsPage, setJobsPage } =
    useAppState();

  const [searchParams, setSearchParams] = useState<JobSearchRequest | null>(
    null,
  );
  const [googleQuery, setGoogleQuery] = useState<string | null>(null);

  const search = useJobSearch(searchParams);
  const { savedIds, externalIds } = useSavedAndExternalJobIds();
  const save = useSaveJob();
  const markApplied = useMarkAppliedElsewhere();
  const apply = useApplyJob();

  const jobs = search.data?.jobs ?? [];
  const totalPages = Math.ceil(jobs.length / PAGE_SIZE);
  const pageJobs = jobs.slice(jobsPage * PAGE_SIZE, (jobsPage + 1) * PAGE_SIZE);
  const selectedJob = jobs.find((j) => j.job_id === selectedJobId) ?? null;

  const isSaved = (id: string) => savedIds.has(id);
  const isAppliedExternally = (id: string) => externalIds.has(id);

  /**
   * Commit a structured job search and reset pagination/selection.
   *
   * @param request - Search request payload from the search bar.
   */
  const handleSearch = (request: JobSearchRequest) => {
    logger.info(`Committed search request: ${JSON.stringify(request)}`);
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
    setGoogleQuery(query);
    setSearchParams(null);
    setSelectedJobId(null);
  };

  return (
    <PageContainer
      variant="full-bleed"
      className="h-full flex flex-col gap-4 space-y-0"
    >
      <PageHeader
        title="Jobs"
        subtitle="Search and browse job listings."
      />

      <SearchBar onSearch={handleSearch} onGoogleSearch={handleGoogleSearch} />

      {search.isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Searching…
        </div>
      )}

      {search.error && (
        <QueryErrorBanner
          title="Search failed"
          message={search.error.message}
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
      ) : searchParams == null && !search.isLoading ? (
        <EmptyState
          title="Run a search…"
          description="Enter keywords and filters above to browse matching job listings."
          icon={<Search className="h-8 w-8" />}
        />
      ) : searchParams != null &&
        jobs.length === 0 &&
        !search.isLoading &&
        !search.error ? (
        <EmptyState
          title="No jobs found"
          description="Try different keywords, locations, or sources and search again."
          icon={<Search className="h-8 w-8" />}
        />
      ) : searchParams != null && jobs.length > 0 ? (
        <div className="flex flex-1 flex-col gap-4 min-h-0 overflow-hidden lg:flex-row">
          {/* Left panel — job list */}
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
                onSave={() =>
                  save.mutate({
                    id: selectedJob.job_id,
                    saved: isSaved(selectedJob.job_id),
                  })
                }
                onApply={() => apply.mutate(selectedJob.job_id)}
                onMarkAppliedExternally={() =>
                  markApplied.mutate({
                    id: selectedJob.job_id,
                    title: selectedJob.title,
                    company: selectedJob.company,
                  })
                }
              />
            ) : (
              <EmptyState
                title="Select a job"
                description="Choose a listing from the left to see full details."
                className="h-full"
              />
            )}
          </div>
        </div>
      ) : null}
    </PageContainer>
  );
}
