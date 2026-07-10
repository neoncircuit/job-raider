"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { Search } from "lucide-react";
import { jobsApi } from "@/lib/api/jobs";
import type { JobSearchRequest } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { SourceSelector } from "./source-selector";
import { DEFAULT_SOURCES } from "@/lib/utils/constants";
import { createLogger } from "@/lib/logger";

const logger = createLogger("SearchBar");

export interface SearchValues {
  keywords: string;
  location: string;
  remoteOnly: boolean;
  limit: number;
}

interface SearchBarProps {
  /** Called with a backend search request when sources are selected. */
  onSearch: (request: JobSearchRequest) => void;
  /** Called with a Google query string when no sources are selected. */
  onGoogleSearch: (query: string) => void;
}

/**
 * Job search form with source selection and remote-only toggle.
 *
 * The form only collects inputs and delegates execution to the parent page,
 * which owns the TanStack Query search state.
 */
export function SearchBar({ onSearch, onGoogleSearch }: SearchBarProps) {
  const { register, handleSubmit, control, setValue } = useForm<SearchValues>({
    defaultValues: { keywords: "", location: "", remoteOnly: false, limit: 50 },
  });

  const sourcesQuery = useQuery({
    queryKey: ["job-sources"],
    queryFn: jobsApi.getSources,
    staleTime: Infinity,
  });

  const available = sourcesQuery.data?.sources ?? DEFAULT_SOURCES;
  const [manualSources, setManualSources] = useState<string[] | null>(null);
  const initializedRef = useRef(false);

  // Initialize the manual selection to the resolved available sources exactly
  // once, preventing the selection from drifting back to defaults after the
  // query loads.
  useEffect(() => {
    if (!initializedRef.current && available.length > 0) {
      initializedRef.current = true;
      setManualSources(available);
    }
  }, [available]);

  const selectedSources = manualSources ?? available;
  const noSources = selectedSources.length === 0;

  const remoteOnly = useWatch({ control, name: "remoteOnly" });

  const handleFormSubmit = handleSubmit((values) => {
    const keywordsArray = values.keywords.split(/[\s,]+/).filter(Boolean);
    if (keywordsArray.length === 0) {
      toast.error("Please enter at least one keyword");
      return;
    }

    if (noSources) {
      const q = [values.keywords, values.location, "jobs"]
        .filter(Boolean)
        .join(" ");
      logger.info(`No sources selected, falling back to Google search: ${q}`);
      onGoogleSearch(q);
      return;
    }

    const request: JobSearchRequest = {
      keywords: keywordsArray,
      locations: values.location ? [values.location] : [],
      sources: selectedSources,
      limit: values.limit,
      remote_only: values.remoteOnly,
    };

    logger.info(`Submitting search request: ${JSON.stringify(request)}`);
    onSearch(request);
  });

  return (
    <form
      onSubmit={handleFormSubmit}
      className="flex flex-wrap gap-3 items-end"
    >
      <div className="flex-1 min-w-[280px] space-y-1">
        <Label htmlFor="keywords">Keywords</Label>
        <Input
          id="keywords"
          placeholder="Python, FastAPI, remote…"
          {...register("keywords")}
        />
      </div>
      <div className="w-56 space-y-1">
        <Label htmlFor="location">Location</Label>
        <Input
          id="location"
          placeholder="Singapore"
          {...register("location")}
        />
      </div>
      <div className="space-y-1">
        <Label>Sources</Label>
        <SourceSelector
          available={available}
          selected={selectedSources}
          onChange={setManualSources}
        />
      </div>
      <div className="flex items-center gap-2 pb-0.5">
        <Switch
          id="remote"
          checked={remoteOnly}
          onCheckedChange={(v) => setValue("remoteOnly", v)}
        />
        <Label htmlFor="remote" className="cursor-pointer">
          Remote only
        </Label>
      </div>
      <Button type="submit" variant={noSources ? "outline" : "default"}>
        <Search className="mr-1.5 h-4 w-4" />
        {noSources ? "Search Google" : "Search"}
      </Button>
    </form>
  );
}
