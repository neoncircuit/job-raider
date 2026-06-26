"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod/v4";
import { toast } from "sonner";
import { Play, Square, Wifi, WifiOff } from "lucide-react";
import { pipelineApi } from "@/lib/api/pipeline";
import { jobsApi } from "@/lib/api/jobs";
import type { WSMessage } from "@/lib/types/websocket";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAppState } from "@/app/providers";
import { formatDatetime } from "@/lib/utils/format";
import { PIPELINE_STAGES, STATUS_COLORS, DEFAULT_SOURCES } from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";

// ── WebSocket hook ─────────────────────────────────────────────────────────────

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

function usePipelineWS(runId: string | null) {
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [wsStatus, setWsStatus] = useState<"idle" | "connected" | "error" | "closed">("idle");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages(prev => prev.length > 0 ? [] : prev);
    setWsStatus(prev => prev !== "idle" ? "idle" : prev);
    const ws = new WebSocket(`${WS_BASE}/api/pipeline/${runId}/progress`);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WSMessage;
        setMessages((prev) => [...prev.slice(-200), msg]);
      } catch { /* ignore malformed */ }
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

  const { register, handleSubmit, control, setValue, formState: { errors } } =
    useForm<FormValues>({
      resolver: zodResolver(schema),
      defaultValues: {
        keywords: "",
        locations: "",
        minScore: 60,
        maxJobs: 50,
        scamThreshold: 0.7,
        dryRun: true,
        skipSubmission: false,
      },
    });

  const start = useMutation({
    mutationFn: (v: FormValues) =>
      pipelineApi.start({
        keywords: v.keywords.split(/[\s,]+/).filter(Boolean),
        locations: v.locations.split(/[\s,]+/).filter(Boolean),
        sources: sources.data?.sources ?? DEFAULT_SOURCES,
        min_score: v.minScore,
        max_jobs: v.maxJobs,
        scam_threshold: v.scamThreshold,
        dry_run: v.dryRun,
        skip_submission: v.skipSubmission,
      }),
    onSuccess: (data) => onStarted(data.run_id),
    onError: () => toast.error("Failed to start pipeline. Is the backend running?"),
  });

  const dryRun = useWatch({ control, name: "dryRun" });

  return (
    <form onSubmit={handleSubmit((v) => start.mutate(v))} className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <Label>Keywords *</Label>
          <Input placeholder="Python, FastAPI, machine learning…" {...register("keywords")} />
          {errors.keywords && <p className="text-xs text-red-500">{errors.keywords.message}</p>}
        </div>
        <div className="space-y-1">
          <Label>Locations</Label>
          <Input placeholder="Singapore, Remote…" {...register("locations")} />
        </div>
        <div className="space-y-1">
          <Label>Min Score (0–100)</Label>
          <Input type="number" min={0} max={100} {...register("minScore", { valueAsNumber: true })} />
        </div>
        <div className="space-y-1">
          <Label>Max Jobs</Label>
          <Input type="number" min={1} max={500} {...register("maxJobs", { valueAsNumber: true })} />
        </div>
        <div className="space-y-1">
          <Label>Scam Threshold (0–1)</Label>
          <Input type="number" step="0.1" min={0} max={1} {...register("scamThreshold", { valueAsNumber: true })} />
          <p className="text-xs text-gray-400">Jobs above this score are filtered out.</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-6">
        <div className="flex items-center gap-2">
          <Switch
            id="dry_run"
            checked={dryRun}
            onCheckedChange={(v) => setValue("dryRun", v)}
          />
          <Label htmlFor="dry_run">Dry Run (no actual applications)</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="skip_sub"
            checked={useWatch({ control, name: "skipSubmission" })}
            onCheckedChange={(v) => setValue("skipSubmission", v)}
          />
          <Label htmlFor="skip_sub">Skip Submission Stage</Label>
        </div>
      </div>

      {!dryRun && (
        <p className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-700">
          Dry Run is OFF — the pipeline will submit real applications.
        </p>
      )}

      <Button type="submit" disabled={start.isPending} className="w-full sm:w-auto">
        <Play className="mr-1.5 h-4 w-4" />
        {start.isPending ? "Starting…" : "Start Pipeline"}
      </Button>
    </form>
  );
}

// ── Live monitor ───────────────────────────────────────────────────────────────

function LiveMonitor({ runId }: { runId: string }) {
  const { messages, wsStatus } = usePipelineWS(runId);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  const lastProgress = [...messages].reverse().find((m) => m.type === "stage_progress");
  const progressPct = lastProgress?.type === "stage_progress" ? lastProgress.progress : 0;

  const isComplete = messages.some(
    (m) => m.type === "pipeline_complete" || m.type === "pipeline_failed"
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Left — status + progress + stages */}
      <div className="space-y-4">
        {/* Status bar */}
        <div className="flex items-center justify-between rounded-lg border bg-white p-3">
          <div className="flex items-center gap-2">
            {wsStatus === "connected" && !isComplete ? (
              <Wifi className="h-4 w-4 text-green-500 animate-pulse" />
            ) : (
              <WifiOff className={cn("h-4 w-4", wsStatus === "error" ? "text-red-500" : "text-gray-400")} />
            )}
            <span className="text-sm font-medium text-gray-700">
              <code className="font-mono text-xs">{runId.slice(0, 12)}…</code>
            </span>
          </div>
          <Badge className={cn("text-xs", isComplete ? "bg-green-100 text-green-800" : "bg-blue-100 text-blue-800")}>
            {isComplete ? "Complete" : wsStatus}
          </Badge>
        </div>

        {/* Progress bar */}
        <Progress value={isComplete ? 100 : progressPct * 100} className="h-2" />

        {/* Stage indicators */}
        <div className="rounded-lg border bg-white p-3 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Stages</p>
          <div className="flex flex-col gap-1.5">
            {PIPELINE_STAGES.map((s) => {
              const completed = messages.some(
                (m) => m.type === "stage_completed" && m.stage === s.key
              );
              const active = messages.some(
                (m) => m.type === "stage_started" && m.stage === s.key
              ) && !completed;
              return (
                <div key={s.key} className="flex items-center gap-2">
                  <div className={cn(
                    "h-2 w-2 rounded-full shrink-0",
                    completed ? "bg-green-500" : active ? "bg-blue-500 animate-pulse" : "bg-gray-200"
                  )} />
                  <span className={cn(
                    "text-sm",
                    completed ? "text-green-700 font-medium" : active ? "text-blue-700 font-medium" : "text-gray-400"
                  )}>
                    {s.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right — event log (wider) */}
      <div className="lg:col-span-2">
        <div
          ref={logRef}
          className="h-full min-h-[400px] overflow-y-auto rounded-lg border bg-gray-950 p-4 font-mono text-xs text-gray-300 space-y-0.5"
        >
          {messages.map((m, i) => (
            <div key={i} className="flex gap-2">
              <span className="shrink-0 text-gray-600">
                {"timestamp" in m ? new Date(m.timestamp).toLocaleTimeString() : ""}
              </span>
              <span className={cn(
                m.type === "pipeline_failed" && "text-red-400",
                m.type === "pipeline_complete" && "text-green-400",
                m.type === "stage_completed" && "text-blue-300",
                m.type === "stage_started" && "text-indigo-300",
              )}>
                <span className="text-gray-500">[{m.type}]</span>{" "}
                {"stage" in m && m.stage ? `${m.stage} ` : ""}
                {"count" in m ? `count=${m.count} ` : ""}
                {"progress" in m ? `${((m as { progress: number }).progress * 100).toFixed(0)}% ` : ""}
                {"error" in m ? (m as { error: string }).error : ""}
              </span>
            </div>
          ))}
          {messages.length === 0 && (
            <span className="text-gray-600">Waiting for events…</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── History ───────────────────────────────────────────────────────────────────

function HistoryPanel({ onResume }: { onResume: (id: string) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["pipeline-history"],
    queryFn: () => pipelineApi.getHistory(20),
    staleTime: 30_000,
  });

  if (isLoading) return <p className="text-sm text-gray-400">Loading…</p>;
  if (!data?.runs.length) return <p className="text-sm text-gray-400">No runs yet.</p>;

  return (
    <div className="space-y-2">
      {data.runs.map((r) => (
        <div key={r.run_id} className="flex items-center justify-between rounded-lg border bg-white p-3">
          <div>
            <p className="text-sm font-mono text-gray-700">{r.run_id.slice(0, 12)}…</p>
            <p className="text-xs text-gray-400">{formatDatetime(r.created_at)}</p>
            <p className="text-xs text-gray-500">
              {r.jobs_scraped ?? 0} scraped · {r.jobs_applied ?? 0} applied
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={cn("text-xs", STATUS_COLORS[r.status] ?? "bg-gray-100 text-gray-700")}>
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
      toast.success("Pipeline cancelled.");
      setActiveRunId(null);
      setTab("history");
    },
    onError: () => toast.error("Cancel failed."),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pipeline</h1>
          <p className="mt-1 text-sm text-gray-500">Start, monitor, and review pipeline runs.</p>
        </div>
        {activeRunId && tab === "monitor" && (
          <Button
            size="sm"
            variant="destructive"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
          >
            <Square className="mr-1.5 h-3.5 w-3.5" />
            Cancel Run
          </Button>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="start">Start</TabsTrigger>
          <TabsTrigger value="monitor" disabled={!activeRunId}>
            Live Monitor {activeRunId && <span className="ml-1.5 h-2 w-2 rounded-full bg-green-500 inline-block animate-pulse" />}
          </TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="start" className="mt-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Configure Pipeline Run</CardTitle>
            </CardHeader>
            <CardContent>
              <StartForm onStarted={handleStarted} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="monitor" className="mt-5">
          {activeRunId ? (
            <LiveMonitor runId={activeRunId} />
          ) : (
            <p className="text-sm text-gray-400">No active run. Start a pipeline first.</p>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-5">
          <HistoryPanel onResume={(id) => { setActiveRunId(id); setTab("monitor"); }} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
