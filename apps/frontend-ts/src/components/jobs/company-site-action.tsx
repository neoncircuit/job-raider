"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { jobsApi } from "@/lib/api/jobs";
import type { CompanySiteResult, JobListing } from "@/lib/types/api";

interface CompanySiteActionProps {
  /** Job whose company site is searched. */
  job: JobListing;
}

/**
 * Job detail action: find the job on the company's own site or ATS.
 *
 * Shows a working state while the search runs, then a labelled link for a
 * verified posting or careers page, or a short message when none was found.
 *
 * @param props - The job to search for.
 * @returns The search button, the company site link, or a status message.
 */
export function CompanySiteAction({ job }: CompanySiteActionProps) {
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<CompanySiteResult | null>(null);

  const search = async (refresh: boolean) => {
    setSearching(true);
    try {
      setResult(await jobsApi.getCompanySite(job.job_id, refresh));
    } catch {
      toast.error("Company site search failed. Try again.");
    } finally {
      setSearching(false);
    }
  };

  if (searching) {
    return (
      <Button size="sm" variant="outline" disabled>
        Searching company site...
      </Button>
    );
  }

  if (!result) {
    return (
      <Button size="sm" variant="outline" onClick={() => search(false)}>
        Find company site
      </Button>
    );
  }

  if (result.level === "disabled") {
    return (
      <p className="flex-1 text-xs text-muted-foreground self-center">
        Company site search is off. Turn it on in Settings.
      </p>
    );
  }

  const searchAgain = (
    <Button size="sm" variant="ghost" onClick={() => search(true)}>
      Search again
    </Button>
  );

  if (result.url && (result.level === "exact" || result.level === "careers")) {
    const label =
      result.level === "exact"
        ? "Apply on company site"
        : "Company careers page";
    return (
      <div className="flex flex-1 gap-2">
        <a
          href={result.url}
          target="_blank"
          rel="noreferrer"
          className="flex-1"
        >
          <Button size="sm" variant="outline" className="w-full">
            {label}
          </Button>
        </a>
        {searchAgain}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-wrap items-center gap-2">
      <p className="text-xs text-muted-foreground">
        No company page was verified. Use the portal link.
      </p>
      {searchAgain}
    </div>
  );
}
