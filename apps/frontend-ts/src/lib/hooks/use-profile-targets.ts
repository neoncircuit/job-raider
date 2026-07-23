"use client";

import { useQuery } from "@tanstack/react-query";
import { profileApi } from "@/lib/api/profile";
import type { TargetJob } from "@/lib/types/api";

/**
 * Load the active profile's job targets for optional Pipeline/Jobs prefill.
 *
 * @returns Targets, loading flag, and whether keywords are available to apply.
 */
export function useProfileTargets() {
  const query = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
    staleTime: 60_000,
    retry: false,
  });

  const targets: TargetJob | null = query.data?.target_job ?? null;
  const hasKeywords = (targets?.keywords?.length ?? 0) > 0;

  return {
    targets,
    hasKeywords,
    isLoading: query.isLoading || query.isPending,
    isError: query.isError,
  };
}
