"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ExternalLink, FlaskConical } from "lucide-react";
import { evaluationApi } from "@/lib/api/evaluation";
import { getApiErrorMessage } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";

const STATUS_KEY = ["compare-status"] as const;
const LATEST_KEY = ["compare-latest"] as const;

/**
 * Metrics card to run the safe cover-letter model compare and show results.
 *
 * The backend runs the allow-listed models one at a time, unloads each, waits
 * a cool-down, and logs the run to MLflow. Only one compare runs at a time.
 *
 * @returns The Model comparison section.
 */
export function ModelCompareCard() {
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const status = useQuery({
    queryKey: STATUS_KEY,
    queryFn: ({ signal }) => evaluationApi.getCompareStatus(signal),
    refetchInterval: (q) =>
      q.state.data?.status === "running" ? 2_000 : false,
  });
  const latest = useQuery({
    queryKey: LATEST_KEY,
    queryFn: ({ signal }) => evaluationApi.getLatestCompare(signal),
  });

  const state = status.data;
  const running = state?.status === "running";

  const lastStatus = useRef(state?.status);
  useEffect(() => {
    const prev = lastStatus.current;
    lastStatus.current = state?.status;
    if (prev !== "running" || !state) return;
    if (state.status === "completed") {
      toast.success(`Compare done. Winner: ${state.report?.winner ?? "none"}`);
      qc.invalidateQueries({ queryKey: LATEST_KEY });
    } else if (state.status === "failed") {
      toast.error(`Compare failed: ${state.error ?? "unknown error"}`);
    }
  }, [state, qc]);

  const start = useMutation({
    mutationFn: evaluationApi.startCompare,
    onSuccess: (next) => qc.setQueryData(STATUS_KEY, next),
    onError: (error) =>
      toast.error(getApiErrorMessage(error, "Could not start the compare.")),
  });

  const report = latest.data?.report;
  const percent =
    running && state?.total ? ((state.done ?? 0) / state.total) * 100 : 0;

  return (
    <section
      className="space-y-3 rounded-lg border bg-card p-4"
      aria-label="Model comparison"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-semibold uppercase tracking-wide text-foreground">
            Model comparison
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Cover-letter A/B of qwen2.5:7b and qwen3.5:4b on fixed fixtures. One
            model loads at a time. Results go to MLflow.
          </p>
        </div>
        <Button
          onClick={() => setConfirmOpen(true)}
          disabled={running || start.isPending}
        >
          <FlaskConical className="mr-1.5 h-4 w-4" />
          Run compare
        </Button>
      </div>

      {running && state && (
        <div className="space-y-1" aria-live="polite">
          <p className="text-xs text-muted-foreground">
            {state.current_model
              ? `Running ${state.current_model}, case ${state.current_case} (${(state.done ?? 0) + 1} of ${state.total})`
              : "Starting…"}
          </p>
          <Progress value={percent} className="h-2" />
        </div>
      )}

      {state?.status === "failed" && (
        <QueryErrorBanner
          title="Last compare failed"
          message={state.error ?? "Unknown error"}
        />
      )}

      {latest.isError && (
        <QueryErrorBanner
          title="Could not load the last compare"
          message={getApiErrorMessage(latest.error, "Backend unreachable.")}
        />
      )}

      {latest.isSuccess && !report && (
        <p className="text-sm text-muted-foreground">No compare has run yet.</p>
      )}

      {report && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-foreground">
              Winner:{" "}
              <span className="font-mono">{report.winner ?? "none"}</span>
            </span>
            <span className="text-xs text-muted-foreground">
              {new Date(report.generated_at).toLocaleString()}
            </span>
            {report.mlflow?.ui_url && (
              <a
                href={report.mlflow.ui_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
              >
                Open in MLflow
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4">Model</th>
                  <th className="pb-2 pr-4">Mean score</th>
                  <th className="pb-2 pr-4">Cases valid</th>
                  <th className="pb-2">Avg time</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {report.reports.map((r) => {
                  const valid = r.cases.filter((c) => c.is_valid).length;
                  const avgMs = r.cases.length
                    ? r.cases.reduce((s, c) => s + c.elapsed_ms, 0) /
                      r.cases.length
                    : 0;
                  return (
                    <tr key={r.model}>
                      <td className="py-2 pr-4 font-mono text-xs text-foreground">
                        {r.model}
                        {r.model === report.winner && (
                          <Badge className="ml-2 bg-success/10 text-xs text-success">
                            Winner
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {r.mean_score?.toFixed(1) ?? "—"}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {valid} of {r.cases.length}
                      </td>
                      <td className="py-2 text-muted-foreground">
                        {(avgMs / 1000).toFixed(1)} s
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Run the model compare?</AlertDialogTitle>
            <AlertDialogDescription>
              This loads each model on the Ollama host GPU in turn and takes
              several minutes. Do not run other heavy GPU work at the same time.
              Both models must be installed (Settings, Local models).
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => start.mutate()}>
              Run compare
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
