import { isTrackedApplication } from "@/lib/applications-filters";
import type { ApplicationSummary } from "@/lib/types/api";

const STORAGE_KEY = "job-raider-onboarding-dismissed";

/** What the app knows about a new user's setup. */
export interface OnboardingState {
  /** The backend answered a health request. */
  backend: boolean;
  /** Ollama answered and has at least one model. */
  model: boolean;
  /** The user has an active profile. */
  profile: boolean;
  /** At least one pipeline run exists. */
  search: boolean;
  /** The user saved, hid, or tracked a job. */
  reviewed: boolean;
  /** At least one application is tracked. */
  tracked: boolean;
}

/** One line of the checklist. */
export interface OnboardingStep {
  /** The field of the state that this step reads. */
  id: keyof OnboardingState;
  /** The action for the user. */
  label: string;
  /** The page where the user does the action. */
  href: string;
  /** Whether the state shows that the action is done. */
  done: boolean;
}

/**
 * Build the checklist from the current state.
 *
 * @param state - What the app knows about the setup.
 * @returns The steps, in the order that a new user does them.
 */
export function onboardingSteps(state: OnboardingState): OnboardingStep[] {
  const steps: Omit<OnboardingStep, "done">[] = [
    { id: "backend", label: "Start the local backend", href: "/settings" },
    { id: "model", label: "Pull a local model", href: "/settings" },
    { id: "profile", label: "Upload your resume", href: "/profile" },
    { id: "search", label: "Run a first discover", href: "/pipeline" },
    {
      id: "reviewed",
      label: "Review the shortlist: save or hide a job",
      href: "/jobs",
    },
    {
      id: "tracked",
      label: "Track a first application",
      href: "/applications",
    },
  ];
  return steps.map((step) => ({ ...step, done: state[step.id] }));
}

/**
 * Tell whether the user acted on a job.
 *
 * The backend does not record that a user read the shortlist, so a saved,
 * hidden, or tracked job is the proof of a review.
 *
 * @param applications - The rows of the applications dashboard.
 * @returns True when at least one job has an action.
 */
export function hasReviewedShortlist(
  applications: readonly ApplicationSummary[],
): boolean {
  return applications.some(
    (row) => row.is_bookmarked || row.is_hidden || isTrackedApplication(row),
  );
}

/**
 * Read whether the user dismissed the checklist.
 *
 * @returns True when dismissed. False when the browser blocks storage.
 */
export function readOnboardingDismissed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * Remember that the user dismissed the checklist.
 *
 * With blocked storage, the checklist comes back on the next visit.
 */
export function saveOnboardingDismissed(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // Dismissing still works for this visit.
  }
}
