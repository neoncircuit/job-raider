/**
 * Pipeline Live Monitor state.
 *
 * Combines the status poll (`GET /api/pipeline/status/{id}`) with WebSocket
 * events. The poll is the source of truth for the final status and for the
 * stage plan, because the WebSocket can connect after early events were sent.
 * WebSocket events make the display update between polls.
 */

import type { PipelineStatus, PipelineStatusResponse } from "@/lib/types/api";
import type { WSMessage } from "@/lib/types/websocket";
import {
  DISCOVER_PIPELINE_STAGES,
  PIPELINE_STAGES,
} from "@/lib/utils/constants";

/** Display state of a run. */
export type RunState = "running" | "completed" | "failed" | "cancelled";

/** Display state of one stage in the stage list. */
export type StageState = "pending" | "active" | "done" | "failed";

/** One row of the stage list. */
export interface StageRow {
  key: string;
  label: string;
  state: StageState;
}

/** Badge text and classes for each run state (theme tokens only). */
export const RUN_STATE_BADGE: Record<
  RunState,
  { label: string; className: string }
> = {
  running: { label: "Running", className: "bg-info/10 text-info" },
  completed: { label: "Complete", className: "bg-success/10 text-success" },
  failed: { label: "Failed", className: "bg-destructive/10 text-destructive" },
  cancelled: {
    label: "Cancelled",
    className: "bg-muted text-muted-foreground",
  },
};

const TERMINAL: ReadonlySet<PipelineStatus> = new Set([
  "completed",
  "failed",
  "cancelled",
]);

/**
 * Resolve the run state from the status poll and the WebSocket events.
 *
 * @param apiStatus - Status from the last poll, if any.
 * @param messages - WebSocket messages received for the run.
 * @returns The terminal status from the poll when there is one; otherwise
 *   the state implied by a final WebSocket event; otherwise "running".
 */
export function resolveRunState(
  apiStatus: PipelineStatus | undefined,
  messages: readonly WSMessage[],
): RunState {
  if (apiStatus && TERMINAL.has(apiStatus)) {
    return apiStatus as RunState;
  }
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const type = messages[i].type;
    if (type === "pipeline_complete") return "completed";
    if (type === "pipeline_failed") return "failed";
  }
  return "running";
}

/**
 * Return the display label for a stage key.
 *
 * @param key - Backend stage value, for example "score_and_rank".
 * @returns The label from `PIPELINE_STAGES`, or the key itself.
 */
export function stageLabel(key: string): string {
  return PIPELINE_STAGES.find((stage) => stage.key === key)?.label ?? key;
}

/**
 * Choose the stages to list for a run.
 *
 * @param stagesPlanned - Stage plan from the status poll, if known.
 * @param mode - Pipeline mode from the final event, if known.
 * @returns The planned stages when the backend sent them; otherwise the
 *   full or discover list.
 */
export function plannedStages(
  stagesPlanned: readonly string[] | undefined,
  mode: string | null,
): { key: string; label: string }[] {
  if (stagesPlanned && stagesPlanned.length > 0) {
    return stagesPlanned.map((key) => ({ key, label: stageLabel(key) }));
  }
  const fallback = mode === "full" ? PIPELINE_STAGES : DISCOVER_PIPELINE_STAGES;
  return fallback.map(({ key, label }) => ({ key, label }));
}

/**
 * Build the stage list with a state for each stage.
 *
 * @param stages - Stages to show, in order.
 * @param status - Last status poll, if any.
 * @param messages - WebSocket messages received for the run.
 * @param runState - Resolved run state.
 * @returns One row per stage. The stage that was running when the run
 *   failed is marked "failed".
 */
export function stageRows(
  stages: readonly { key: string; label: string }[],
  status: PipelineStatusResponse | undefined,
  messages: readonly WSMessage[],
  runState: RunState,
): StageRow[] {
  const done = new Set<string>(status?.stages_completed ?? []);
  const started = new Set<string>();
  for (const message of messages) {
    if (message.type === "stage_completed") done.add(message.stage);
    if (message.type === "stage_started") started.add(message.stage);
  }
  if (status?.current_stage) started.add(status.current_stage);

  return stages.map(({ key, label }) => {
    let state: StageState = "pending";
    if (done.has(key)) {
      state = "done";
    } else if (started.has(key)) {
      if (runState === "failed") state = "failed";
      else if (runState === "running") state = "active";
    }
    return { key, label, state };
  });
}

/**
 * Compute overall progress for the progress bar.
 *
 * @param runState - Resolved run state.
 * @param status - Last status poll, if any.
 * @param messages - WebSocket messages received for the run.
 * @returns Progress from 0 to 100. The backend already sends 0 to 100.
 */
export function overallProgress(
  runState: RunState,
  status: PipelineStatusResponse | undefined,
  messages: readonly WSMessage[],
): number {
  if (runState === "completed") return 100;
  let fromEvents = 0;
  for (const message of messages) {
    if (message.type === "stage_progress") fromEvents = message.progress;
  }
  return Math.min(100, Math.max(status?.stage_progress ?? 0, fromEvents));
}

/**
 * Find the error to show for a failed run.
 *
 * @param runState - Resolved run state.
 * @param status - Last status poll, if any.
 * @param messages - WebSocket messages received for the run.
 * @returns The error message, or null when the run did not fail.
 */
export function runError(
  runState: RunState,
  status: PipelineStatusResponse | undefined,
  messages: readonly WSMessage[],
): string | null {
  if (runState !== "failed") return null;
  if (status?.error_message) return status.error_message;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.type === "pipeline_failed") return message.error;
  }
  return "The pipeline failed. Check the Logs page for details.";
}
