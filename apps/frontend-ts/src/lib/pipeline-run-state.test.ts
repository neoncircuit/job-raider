/**
 * Tests for the pipeline Live Monitor state helpers.
 *
 * Before 2026-10-19 a failed or cancelled run showed a green "Complete"
 * badge, progress was multiplied by 100 a second time, and the stage list
 * never moved during a run.
 */

import { describe, expect, it } from "vitest";

import {
  overallProgress,
  plannedStages,
  resolveRunState,
  runError,
  stageRows,
} from "@/lib/pipeline-run-state";
import type { PipelineStatusResponse } from "@/lib/types/api";
import type { WSMessage } from "@/lib/types/websocket";

const TS = "2026-10-19T00:00:00Z";

/**
 * Build a status poll response.
 *
 * @param overrides - Fields to change from a running run.
 * @returns A status response.
 */
function status(
  overrides: Partial<PipelineStatusResponse> = {},
): PipelineStatusResponse {
  return {
    run_id: "run_1",
    status: "running",
    stage_progress: 0,
    jobs_scraped: 0,
    jobs_scored: 0,
    jobs_selected: 0,
    applications_submitted: 0,
    ...overrides,
  };
}

describe("resolveRunState", () => {
  it("uses a terminal status from the poll", () => {
    expect(resolveRunState("failed", [])).toBe("failed");
    expect(resolveRunState("cancelled", [])).toBe("cancelled");
  });

  it("uses the final WebSocket event before the poll catches up", () => {
    const failed: WSMessage[] = [
      { type: "pipeline_failed", error: "boom", timestamp: TS },
    ];
    expect(resolveRunState("running", failed)).toBe("failed");
  });

  it("is running without a terminal signal", () => {
    expect(resolveRunState(undefined, [])).toBe("running");
  });
});

describe("plannedStages", () => {
  it("lists the backend plan with labels, including full-only stages", () => {
    expect(plannedStages(["linkedin_auth", "present_selection"], null)).toEqual(
      [
        { key: "linkedin_auth", label: "LinkedIn Check" },
        { key: "present_selection", label: "Select Jobs" },
      ],
    );
  });

  it("falls back to the discover list without a plan", () => {
    const keys = plannedStages(undefined, null).map((s) => s.key);
    expect(keys.at(-1)).toBe("rag_rank");
  });
});

describe("stageRows", () => {
  const stages = plannedStages(["scrape", "deduplicate", "filter_scams"], null);

  it("marks completed and running stages from the poll alone", () => {
    const rows = stageRows(
      stages,
      status({ stages_completed: ["scrape"], current_stage: "deduplicate" }),
      [],
      "running",
    );
    expect(rows.map((r) => r.state)).toEqual(["done", "active", "pending"]);
  });

  it("marks the stage that was running as failed when the run failed", () => {
    const rows = stageRows(
      stages,
      status({
        status: "failed",
        stages_completed: ["scrape"],
        current_stage: "deduplicate",
      }),
      [],
      "failed",
    );
    expect(rows.map((r) => r.state)).toEqual(["done", "failed", "pending"]);
  });

  it("uses WebSocket events between polls", () => {
    const messages: WSMessage[] = [
      { type: "stage_completed", stage: "scrape", result: {}, timestamp: TS },
      {
        type: "stage_started",
        stage: "deduplicate",
        metadata: {},
        timestamp: TS,
      },
    ];
    const rows = stageRows(stages, undefined, messages, "running");
    expect(rows.map((r) => r.state)).toEqual(["done", "active", "pending"]);
  });
});

describe("overallProgress", () => {
  it("uses the 0-100 value from the backend without scaling it again", () => {
    expect(overallProgress("running", status({ stage_progress: 40 }), [])).toBe(
      40,
    );
  });

  it("takes the newer WebSocket progress when it is ahead of the poll", () => {
    const messages: WSMessage[] = [
      {
        type: "stage_progress",
        stage: "deduplicate",
        progress: 67,
        metadata: {},
        timestamp: TS,
      },
    ];
    expect(
      overallProgress("running", status({ stage_progress: 33 }), messages),
    ).toBe(67);
  });

  it("is 100 when the run completed", () => {
    expect(overallProgress("completed", status(), [])).toBe(100);
  });
});

describe("runError", () => {
  it("shows the backend error for a failed run", () => {
    expect(
      runError(
        "failed",
        status({ error_message: "Stage 'scrape' failed: timeout" }),
        [],
      ),
    ).toBe("Stage 'scrape' failed: timeout");
  });

  it("is null when the run did not fail", () => {
    expect(runError("completed", status(), [])).toBeNull();
  });
});
