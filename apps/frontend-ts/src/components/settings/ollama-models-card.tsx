"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Trash2 } from "lucide-react";
import { settingsApi } from "@/lib/api/settings";
import { getApiErrorMessage } from "@/lib/api/client";
import type { OllamaPullState } from "@/lib/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

const MODELS_KEY = ["ollama-models"] as const;
const PULL_KEY = ["ollama-pull-status"] as const;

/**
 * Format a byte count as gigabytes.
 *
 * @param bytes - Size in bytes.
 * @returns Size such as ``1.9 GB``.
 */
function formatGb(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

/**
 * Percent complete for a pull, or 0 before Ollama reports a total.
 *
 * @param state - Current pull state.
 * @returns Percent from 0 to 100.
 */
function pullPercent(state: OllamaPullState): number {
  if (!state.total) return 0;
  return Math.min(100, ((state.completed ?? 0) / state.total) * 100);
}

/**
 * Settings card to list, pull, and delete local Ollama models.
 *
 * The backend allows one pull at a time, refuses models of 9B parameters or
 * more, and refuses to delete models that routing or RAG embedding uses.
 *
 * @returns The Local models card.
 */
export function OllamaModelsCard() {
  const qc = useQueryClient();
  const [modelInput, setModelInput] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const models = useQuery({
    queryKey: MODELS_KEY,
    queryFn: settingsApi.listOllamaModels,
  });
  const pull = useQuery({
    queryKey: PULL_KEY,
    queryFn: settingsApi.getOllamaPullStatus,
    refetchInterval: (q) =>
      q.state.data?.status === "pulling" ? 1_000 : false,
  });

  const pullState = pull.data;
  const pulling = pullState?.status === "pulling";

  const lastStatus = useRef(pullState?.status);
  useEffect(() => {
    const prev = lastStatus.current;
    lastStatus.current = pullState?.status;
    if (prev !== "pulling" || !pullState) return;
    if (pullState.status === "success") {
      toast.success(`Pulled ${pullState.model}`);
      qc.invalidateQueries({ queryKey: MODELS_KEY });
      qc.invalidateQueries({ queryKey: ["settings-models"] });
    } else if (pullState.status === "error") {
      toast.error(`Pull failed: ${pullState.error ?? "unknown error"}`);
    }
  }, [pullState, qc]);

  const startPull = useMutation({
    mutationFn: (model: string) => settingsApi.pullOllamaModel(model),
    onSuccess: (state) => {
      qc.setQueryData(PULL_KEY, state);
      setModelInput("");
    },
    onError: (error) =>
      toast.error(getApiErrorMessage(error, "Could not start the pull.")),
  });

  const remove = useMutation({
    mutationFn: (model: string) => settingsApi.deleteOllamaModel(model),
    onSuccess: (data) => {
      toast.success(`Deleted ${data.deleted}`);
      qc.invalidateQueries({ queryKey: MODELS_KEY });
      qc.invalidateQueries({ queryKey: ["settings-models"] });
    },
    onError: (error) =>
      toast.error(getApiErrorMessage(error, "Could not delete the model.")),
  });

  const list = models.data;

  return (
    <section
      className="rounded-lg border bg-card p-4 space-y-4"
      aria-label="Local models"
    >
      <div>
        <h2 className="text-sm font-semibold text-foreground">Local models</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Ollama models on {list?.host ?? "the Ollama host"}. Models of 9B
          parameters or more are blocked. Models in use by routing or RAG cannot
          be deleted.
        </p>
      </div>

      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const name = modelInput.trim();
          if (name) startPull.mutate(name);
        }}
      >
        <div className="min-w-[220px] flex-1 space-y-1">
          <Label htmlFor="ollama-pull-model">Pull a model</Label>
          <Input
            id="ollama-pull-model"
            placeholder="qwen2.5:3b"
            value={modelInput}
            onChange={(e) => setModelInput(e.target.value)}
            disabled={pulling}
          />
        </div>
        <Button
          type="submit"
          disabled={pulling || startPull.isPending || !modelInput.trim()}
        >
          <Download className="mr-1.5 h-4 w-4" />
          Pull
        </Button>
      </form>

      {pulling && pullState && (
        <div className="space-y-1" aria-live="polite">
          <p className="text-xs text-muted-foreground">
            Pulling {pullState.model}: {pullState.message}
            {pullState.total
              ? ` (${formatGb(pullState.completed ?? 0)} of ${formatGb(pullState.total)})`
              : ""}
          </p>
          <Progress value={pullPercent(pullState)} className="h-2" />
        </div>
      )}

      {models.isLoading && (
        <p className="text-sm text-muted-foreground">Loading models…</p>
      )}
      {models.isError && (
        <QueryErrorBanner
          title="Could not load models"
          message={getApiErrorMessage(models.error, "Backend unreachable.")}
        />
      )}
      {list && !list.reachable && (
        <QueryErrorBanner
          title="Ollama is not reachable"
          message={`${list.host}. Start Ollama on the host, then reload.`}
        />
      )}

      {list?.reachable &&
        (list.models.length === 0 ? (
          <p className="text-sm text-muted-foreground">No models installed.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4">Model</th>
                  <th className="pb-2 pr-4">Parameters</th>
                  <th className="pb-2 pr-4">Size</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {list.models.map((m) => (
                  <tr key={m.name}>
                    <td className="py-2 pr-4 font-mono text-xs text-foreground">
                      {m.name}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">
                      {m.parameter_size ?? "—"}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">
                      {formatGb(m.size)}
                    </td>
                    <td className="py-2 text-right">
                      {m.in_use ? (
                        <Badge className="bg-success/10 text-success text-xs">
                          In use
                        </Badge>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Delete ${m.name}`}
                          disabled={remove.isPending}
                          onClick={() => setPendingDelete(m.name)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {pendingDelete}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the model files from the Ollama host. You can pull it
              again later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (pendingDelete) remove.mutate(pendingDelete);
                setPendingDelete(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
