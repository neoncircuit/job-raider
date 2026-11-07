"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { applicationsApi } from "@/lib/api/applications";
import { healthApi } from "@/lib/api/health";
import { pipelineApi } from "@/lib/api/pipeline";
import { profileApi } from "@/lib/api/profile";
import { settingsApi } from "@/lib/api/settings";
import { isTrackedApplication } from "@/lib/applications-filters";
import {
  hasReviewedShortlist,
  onboardingSteps,
  readOnboardingDismissed,
  saveOnboardingDismissed,
} from "@/lib/onboarding";

interface OnboardingCardProps {
  /** Called when the user dismisses the card. */
  onDismiss: () => void;
}

/**
 * Read the setup state and show the steps that are open.
 *
 * Each read waits for the backend, so a user with no backend sees the card at
 * once. A failed read leaves its step open.
 *
 * @param onDismiss - Called when the user dismisses the card.
 * @returns The card, or nothing while it loads or when each step is done.
 */
function OnboardingCard({ onDismiss }: OnboardingCardProps) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.getHealth,
    staleTime: 15_000,
  });
  const enabled = health.isSuccess;
  const models = useQuery({
    queryKey: ["onboarding", "models"],
    queryFn: settingsApi.listOllamaModels,
    staleTime: 60_000,
    enabled,
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
    staleTime: 60_000,
    retry: false,
    enabled,
  });
  const history = useQuery({
    queryKey: ["pipeline-history"],
    queryFn: () => pipelineApi.getHistory(5),
    staleTime: 30_000,
    enabled,
  });
  const applications = useQuery({
    queryKey: ["applications", "onboarding"],
    queryFn: () => applicationsApi.getDashboard({ include_hidden: true }),
    staleTime: 30_000,
    enabled,
  });

  if (
    [health, models, profile, history, applications].some(
      (query) => query.isLoading,
    )
  ) {
    return null;
  }

  const rows = applications.data?.applications ?? [];
  const steps = onboardingSteps({
    backend: health.isSuccess,
    model: Boolean(models.data?.reachable && models.data.models.length > 0),
    profile: profile.isSuccess,
    search: (history.data?.runs.length ?? 0) > 0,
    reviewed: hasReviewedShortlist(rows),
    tracked: rows.some(isTrackedApplication),
  });
  const done = steps.filter((step) => step.done).length;
  if (done === steps.length) {
    return null;
  }

  return (
    <section
      aria-label="Getting started"
      className="rounded border border-border bg-card/80 px-4 py-3"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-sm font-semibold text-foreground">
          Getting started
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {done} of {steps.length} done
          </span>
          <Button size="sm" variant="ghost" onClick={onDismiss}>
            Dismiss
          </Button>
        </div>
      </div>
      <ul className="mt-2 space-y-1.5 text-sm">
        {steps.map((step) => (
          <li key={step.id} className="flex items-center gap-2">
            {step.done ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="text-muted-foreground">{step.label}</span>
              </>
            ) : (
              <>
                <Circle className="h-4 w-4 text-muted-foreground" />
                <Link href={step.href} className="underline">
                  {step.label}
                </Link>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Show a new user what to set up next.
 *
 * Render this on the client only, because it reads browser storage on its
 * first render.
 *
 * @returns The checklist, or nothing after the user dismisses it.
 */
export function OnboardingChecklist() {
  const [dismissed, setDismissed] = useState(readOnboardingDismissed);

  if (dismissed) {
    return null;
  }
  return (
    <OnboardingCard
      onDismiss={() => {
        saveOnboardingDismissed();
        setDismissed(true);
      }}
    />
  );
}
