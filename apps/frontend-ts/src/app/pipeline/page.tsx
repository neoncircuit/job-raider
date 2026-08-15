"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod/v4";
import { toast } from "sonner";
import { Play, Square, Wifi, WifiOff } from "lucide-react";
import { getApiErrorMessage } from "@/lib/api/client";
import { pipelineApi } from "@/lib/api/pipeline";
import { jobsApi } from "@/lib/api/jobs";
import type { WSMessage } from "@/lib/types/websocket";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAppState } from "@/app/providers";
import { formatDatetime } from "@/lib/utils/format";
import {
  PIPELINE_STAGES,
  DISCOVER_PIPELINE_STAGES,
  STATUS_COLORS,
  DEFAULT_SOURCES,
} from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { QueryErrorBanner } from "@/components/layout/QueryErrorBanner";
import { SourceSelector } from "@/components/jobs/source-selector";
import { useProfileTargets } from "@/lib/hooks/use-profile-targets";
import Link from "next/link";

// ── WebSocket hook ─────────────────────────────────────────────────────────────

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

function usePipelineWS(runId: string | null) {
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [wsStatus, setWsStatus] = useState<
    "idle" | "connected" | "error" | "closed"
  >("idle");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages((prev) => (prev.length > 0 ? [] : prev));
    setWsStatus((prev) => (prev !== "idle" ? "idle" : prev));
    const ws = new WebSocket(`${WS_BASE}/api/pipeline/${runId}/progress`);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WSMessage;
        setMessages((prev) => [...prev.slice(-200), msg]);
      } catch {
        /* ignore malformed */
      }
    };
    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => setWsStatus("closed");

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [runId]);

  return { messages, wsStatus };
}

// ── Start form schema ─────────────────────────────────────────────────────────

const schema = z.object({
  keywords: z.string().min(1, "At least one keyword required"),
  locations: z.string(),
  minScore: z.number().int().min(0).max(100),
  maxJobs: z.number().int().min(1).max(500),
  scamThreshold: z.number().min(0).max(1),
  mode: z.enum(["discover", "full"]),
  dryRun: z.boolean(),
  skipSubmission: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

// ── Start form ─────────────────────────────────────────────────────────────────

function StartForm({ onStarted }: { onStarted: (runId: string) => void }) {
  const sources = useQuery({
    queryKey: ["job-sources"],
    queryFn: jobsApi.getSources,
    staleTime: Infinity,
  });

  const { targets, hasKeywords } = useProfileTargets();
  const [applyTargetsEnabled, setApplyTargetsEnabled] = useState(false);

  const availableSources = sources.data?.sources ?? DEFAULT_SOURCES;
  /** Null means “follow whatever sources are available”; set once the user edits. */
  const [selectedSources, setSelectedSources] = useState<string[] | null>(null);
  const effectiveSources = selectedSources ?? availableSources;

  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      keywords: "",
      locations: "Singapore",
      minScore: 60,
      maxJobs: 50,
      scamThreshold: 0.7,
      mode: "discover",
      dryRun: true,
      skipSubmission: true,
    },
  });

  const applyProfileTargets = (enabled: boolean) => {
    setApplyTargetsEnabled(enabled);
    if (!enabled || !targets) return;
    setValue("keywords", (targets.keywords ?? []).join(", "), {
      shouldValidate: true,
    });
    setValue("locations", (targets.locations ?? []).join(", "));
  };

  const start = useMutation({
    mutationFn: (v: FormValues) =>
      pipelineApi.start({
        keywords: v.keywords.split(/[\s,]+/).filter(Boolean),
        locations: v.locations.split(/[\s,]+/).filter(Boolean),
        sources:
          effectiveSources.length > 0 ? effectiveSources : availableSources,
        min_score: v.minScore,
        max_jobs: v.maxJobs,
        scam_threshold: v.scamThreshold,
        mode: v.mode,
        dry_run: v.mode === "discover" ? true : v.dryRun,
        skip_submission: v.mode === "discover" ? true : v.skipSubmission,
      }),
    onSuccess: (data) => onStarted(data.run_id),
    onError: (error) =>
      toast.error(
        getApiErrorMessage(
          error,
          "Failed to start pipeline. Is the backend running?",
        ),
      ),
  });

  const dryRun = useWatch({ control, name: "dryRun" });
  const mode = useWatch({ control, name: "mode" });
  const skipSubmission = useWatch({ control, name: "skipSubmission" });

  return (
    <form onSubmit={handleSubmit((v) => start.mutate(v))} className="space-y-5">
      <div className="rounded-lg border bg-card p-4 space-y-3">
        <div>
          <Label className="text-sm font-medium">Run mode</Label>
          <p className="text-xs text-muted-foreground mt-0.5">
            Discover scrapes and scores only. Review the shortlist on Jobs, then
            apply explicitly.
          </p>
        </div>
        <div className="flex flex-wrap gap-4">
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="radio"
              className="mt-1"
              checked={mode === "discover"}
              onChange={() => setValue("mode", "discover")}
            />
            <span>
              <span className="text-sm font-medium text-foreground">
                Discover (recommended)
              </span>
              <span className="block text-xs text-muted-foreground">
                Scrape through score / RAG — no auto-apply
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="radio"
              className="mt-1"
              checked={mode === "full"}
              onChange={() => setValue("mode", "full")}
            />
            <span>
              <span className="text-sm font-medium text-foreground">
                Full pipeline (advanced)
              </span>
              <span className="block text-xs text-muted-foreground">
                Includes detect / generate / submit stages
              </span>
            </span>
          </label>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Switch
            id="use-profile-targets-pipeline"
            checked={applyTargetsEnabled}
            disabled={!hasKeywords}
            onCheckedChange={applyProfileTargets}
          />
          <Label htmlFor="use-profile-targets-pipeline">
            Use profile targets
          </Label>
        </div>
        {!hasKeywords && (
          <p className="text-xs text-muted-foreground">
            Set keywords on{" "}
            <Link href="/profile" className="underline hover:text-foreground">
              Profile
            </Link>{" "}
            to enable this option.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1">
          <Label>Keywords *</Label>
          <Input
            placeholder="Python, FastAPI, machine learning…"
            {...register("keywords")}
          />
          {errors.keywords && (
            <p className="text-xs text-destructive">
              {errors.keywords.message}
            </p>
          )}
        </div>
        <div className="space-y-1">
          <Label>Locations</Label>
          <Input placeholder="Singapore, Remote…" {...register("locations")} />
        </div>
        <div className="space-y-1">
          <Label>Min Score (0–100)</Label>
          <Input
            type="number"
            min={0}
            max={100}
            {...register("minScore", { valueAsNumber: true })}
          />
        </div>
        <div className="space-y-1">
          <Label>Max Jobs</Label>
          <Input
            type="number"
            min={1}
            max={500}
            {...register("maxJobs", { valueAsNumber: true })}
          />
        </div>
        <div className="space-y-1">
          <Label>Scam Threshold (0–1)</Label>
          <Input
            type="number"
            step="0.1"
            min={0}
            max={1}
            {...register("scamThreshold", { valueAsNumber: true })}
          />
          <p className="text-xs text-muted-foreground">
            Jobs above this score are filtered out.
          </p>
        </div>
        <div className="space-y-1">
          <Label>Sources</Label>
          <div className="pt-0.5">
            <SourceSelector
              available={availableSources}
              selected={effectiveSources}
              onChange={setSelectedSources}
            />
          </div>
          {sources.isError && (
            <p className="text-xs text-muted-foreground">
              Using default sources (could not load source list).
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-6">
        {mode === "full" && (
          <>
            <div className="flex items-center gap-2">
              <Switch
                id="dry_run"
                checked={dryRun}
                onCheckedChange={(v) => setValue("dryRun", v)}
              />
              <Label htmlFor="dry_run">Dry Run (recommended)</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="skip_sub"
                checked={skipSubmission}
                onCheckedChange={(v) => setValue("skipSubmission", v)}
              />
              <Label htmlFor="skip_sub">Skip Submission Stage</Label>
            </div>
          </>
        )}
      </div>

      {mode === "full" && !dryRun && (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-200">
          Dry Run is OFF. Real submissions are best-effort and limited (for
          example LinkedIn Easy Apply only when credentials are configured).
          Prefer Dry Run unless you intend to attempt live submissions.
        </p>
      )}

      <Button
        type="submit"
        disabled={start.isPending}
        className="w-full sm:w-auto"
      >
        <Play className="mr-1.5 h-4 w-4" />
        {start.isPending
          ? "Starting…"
          : mode === "discover"
            ? "Start Discover"
            : "Start Full Pipeline"}
      </Button>
    </form>
  );
}

// ── Live monitor ───────────────────────────────────────────────────────────────

function LiveMonitor({ runId }: { runId: string }) {
  const { messages, wsStatus } = usePipelineWS(runId);
  const logRef = useRef<HTMLDivElement>(null);

  const status = useQuery({
    queryKey: ["pipeline-status", runId],
    queryFn: ({ signal }) => pipelineApi.getStatus(runId, signal),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "completed" || s === "failed" || s === "cancelled"
        ? false
        : 2000;
    },
  });

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  const lastProgress = [...messages]
    .reverse()
    .find((m) => m.type === "stage_progress");
  const progressPct =
    lastProgress?.type === "stage_progress" ? lastProgress.progress : 0;

  const completeMsg = [...messages]
    .reverse()
    .find(
      (m) => m.type === "pipeline_complete" || m.type === "pipeline_failed",
    );
  const isComplete =
    Boolean(completeMsg) ||
    status.data?.status === "completed" ||
    status.data?.status === "failed" ||
    status.data?.status === "cancelled";

  const summaryMode =
    completeMsg?.type === "pipeline_complete" &&
    completeMsg.summary &&
    typeof completeMsg.summary.mode === "string"
      ? completeMsg.summary.mode
      : null;
  const stageList =
    summaryMode === "full" ? PIPELINE_STAGES : DISCOVER_PIPELINE_STAGES;

  const jobsScraped = status.data?.jobs_scraped ?? 0;
  const jobsScored = status.data?.jobs_scored ?? 0;
  const jobsSelected = status.data?.jobs_selected ?? 0;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
      {/* Left — status + progress + stages */}
      <div className="space-y-4 lg:col-span-1">
        {/* Status bar */}
        <div className="flex items-center justify-between rounded-lg border bg-card p-3">
          <div className="flex items-center gap-2">
            {wsStatus === "connected" && !isComplete ? (
              <Wifi className="h-4 w-4 text-success animate-pulse" />
            ) : (
              <WifiOff
                className={cn(
                  "h-4 w-4",
                  wsStatus === "error"
                    ? "text-red-500"
                    : "text-muted-foreground",
                )}
              />
            )}
            <span className="text-sm font-medium text-foreground">
              <code className="font-mono text-xs">{runId.slice(0, 12)}…</code>
            </span>
          </div>
          <Badge
            className={cn(
              "text-xs",
              isComplete
                ? "bg-green-100 text-green-800"
                : "bg-info/10 text-info",
            )}
          >
            {isComplete ? "Complete" : wsStatus}
          </Badge>
        </div>

        <div className="rounded-lg border bg-card p-3 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Counts
          </p>
          <p className="text-sm text-foreground">
            {jobsScraped} scraped · {jobsScored} scored
            {jobsSelected > 0 ? ` · ${jobsSelected} shortlisted` : ""}
          </p>
        </div>

        {isComplete && status.data?.status === "completed" && (
          <Link
            href="/jobs"
            className={cn(
              "inline-flex h-8 w-full items-center justify-center rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/80",
            )}
          >
            Review on Jobs
          </Link>
        )}

        {/* Progress bar */}
        <Progress
          value={isComplete ? 100 : progressPct * 100}
          className="h-2"
        />

        {/* Stage indicators */}
        <div className="rounded-lg border bg-card p-3 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Stages
          </p>
          <div className="flex flex-col gap-1.5">
            {stageList.map((s) => {
              const completed = messages.some(
                (m) => m.type === "stage_completed" && m.stage === s.key,
              );
              const active =
                messages.some(
                  (m) => m.type === "stage_started" && m.stage === s.key,
                ) && !completed;
              return (
                <div key={s.key} className="flex items-center gap-2">
                  <div
                    className={cn(
                      "h-2 w-2 rounded-full shrink-0",
                      completed
                        ? "bg-success"
                        : active
                          ? "bg-info animate-pulse"
                          : "bg-muted",
                    )}
                  />
                  <span
                    className={cn(
                      "text-sm",
                      completed
                        ? "text-success font-medium"
                        : active
                          ? "text-info font-medium"
                          : "text-muted-foreground",
                    )}
                  >
                    {s.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right — event log (wider) */}
      <div className="lg:col-span-3">
        <div
          ref={logRef}
          className="h-full min-h-[400px] overflow-y-auto rounded-lg border bg-card p-4 font-mono text-xs text-muted-foreground space-y-0.5"
        >
          {messages.map((m, i) => (
            <div key={i} className="flex gap-2">
              <span className="shrink-0 text-muted-foreground">
                {"timestamp" in m
                  ? new Date(m.timestamp).toLocaleTimeString()
                  : ""}
              </span>
              <span
                className={cn(
                  m.type === "pipeline_failed" && "text-destructive",
                  m.type === "pipeline_complete" && "text-success",
                  m.type === "stage_completed" && "text-info",
                  m.type === "stage_started" && "text-primary",
                )}
              >
                <span className="text-muted-foreground">[{m.type}]</span>{" "}
                {"stage" in m && m.stage ? `${m.stage} ` : ""}
                {"count" in m ? `count=${m.count} ` : ""}
                {"progress" in m
                  ? `${((m as { progress: number }).progress * 100).toFixed(0)}% `
                  : ""}
                {"error" in m ? (m as { error: string }).error : ""}
              </span>
            </div>
          ))}
          {messages.length === 0 && (
            <span className="text-muted-foreground">Waiting for events…</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── History ───────────────────────────────────────────────────────────────────

function HistoryPanel({ onResume }: { onResume: (id: string) => void }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["pipeline-history"],
    queryFn: () => pipelineApi.getHistory(20),
    staleTime: 30_000,
  });

  if (isLoading)
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (isError)
    return (
      <QueryErrorBanner
        title="Could not load history"
        message={error instanceof Error ? error.message : "Unknown error"}
      />
    );
  if (!data?.runs.length)
    return (
      <EmptyState
        title="No runs yet"
        description="Start a pipeline to see history here."
      />
    );

  return (
    <div className="space-y-2">
      {data.runs.map((r) => (
        <div
          key={r.run_id}
          className="flex items-center justify-between rounded-lg border bg-card p-3 transition-all duration-150 hover:border-ring hover:ring-2 hover:ring-ring/40"
        >
          <div>
            <p className="text-sm font-mono text-foreground">
              {r.run_id.slice(0, 12)}…
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDatetime(r.created_at)}
            </p>
            <p className="text-xs text-muted-foreground">
              {r.jobs_scraped ?? 0} scraped · {r.jobs_scored ?? 0} scored
              {(r.jobs_applied ?? 0) > 0 ? ` · ${r.jobs_applied} applied` : ""}
              {r.mode ? ` · ${r.mode}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              className={cn(
                "text-xs",
                STATUS_COLORS[r.status] ?? "bg-muted text-foreground",
              )}
            >
              {r.status}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              className="text-xs"
              onClick={() => onResume(r.run_id)}
            >
              View
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const { activeRunId, setActiveRunId } = useAppState();
  const [tab, setTab] = useState<string>("start");

  const handleStarted = (runId: string) => {
    setActiveRunId(runId);
    setTab("monitor");
    toast.success(`Pipeline started: ${runId.slice(0, 8)}…`);
  };

  const cancel = useMutation({
    mutationFn: () => {
      if (!activeRunId) throw new Error("No active run");
      return pipelineApi.cancel(activeRunId);
    },
    onSuccess: () => {
      toast.success(
        "Cancel requested. The run may still finish stages already in progress.",
      );
      setActiveRunId(null);
      setTab("history");
    },
    onError: () => toast.error("Cancel request failed."),
  });

  return (
    <PageContainer variant="full-bleed" cinematic>
      <PageHeader
        title="Pipeline"
        subtitle="Discover jobs (scrape and score), then review on Jobs before applying."
        actions={
          activeRunId && tab === "monitor" ? (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
            >
              <Square className="mr-1.5 h-3.5 w-3.5" />
              Request Cancel
            </Button>
          ) : undefined
        }
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="start">Start</TabsTrigger>
          <TabsTrigger value="monitor" disabled={!activeRunId}>
            Live Monitor{" "}
            {activeRunId && (
              <span className="ml-1.5 h-2 w-2 rounded-full bg-success inline-block animate-pulse" />
            )}
          </TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="start" className="mt-6">
          <section className="space-y-3">
            <h2 className="font-heading text-sm font-semibold text-foreground">
              Configure pipeline run
            </h2>
            <StartForm onStarted={handleStarted} />
          </section>
        </TabsContent>

        <TabsContent value="monitor" className="mt-6">
          {activeRunId ? (
            <LiveMonitor runId={activeRunId} />
          ) : (
            <EmptyState
              title="No active run"
              description="Start a pipeline first to open the live monitor."
            />
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-6">
          <HistoryPanel
            onResume={(id) => {
              setActiveRunId(id);
              setTab("monitor");
            }}
          />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
