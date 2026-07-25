"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  BookOpen,
  Compass,
  Flag,
  Lightbulb,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { agentsApi } from "@/lib/api/agents";
import { profileApi } from "@/lib/api/profile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { formatDatetime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import type {
  CareerAnalysisResult,
  CareerAnalysisRequest,
  CareerGoalsResult,
  GapAnalysisResult,
  GapAnalysisRequest,
  TaskRecord,
  TaskSubmissionResponse,
  UpskillingRoadmapResult,
  UpskillingRoadmapRequest,
  UserProfile,
} from "@/lib/types/api";

// ── Shared polling hook ───────────────────────────────────────────────────────

/**
 * Manage the lifecycle of a single asynchronous agent task.
 *
 * Submissions return a task ID that is polled until the backend reports the
 * task as ``completed`` or ``failed``.
 *
 * @param taskType Human-readable label used in toast notifications.
 * @param getTask Function that fetches the task record for a given task ID.
 * @returns Task state, submission mutation, and a reset callback.
 */
function useAgentTask<T>(
  taskType: string,
  getTask: (
    taskId: string,
    signal?: AbortSignal,
  ) => Promise<{ data: TaskRecord<T> }>,
) {
  const [taskId, setTaskId] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: async (
      runSubmit: () => Promise<{ data: TaskSubmissionResponse }>,
    ) => {
      const res = await runSubmit();
      setTaskId(res.data.task_id);
      return res;
    },
    onSuccess: () => toast.info(`${taskType} analysis started`),
    onError: () => toast.error(`Failed to start ${taskType} analysis`),
  });

  const task = useQuery({
    queryKey: ["agent-task", taskType, taskId],
    queryFn: ({ signal }) => getTask(taskId!, signal).then((res) => res.data),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" ? 1500 : false;
    },
    staleTime: 0,
  });

  const reset = () => setTaskId(null);

  return { taskId, submit, task, reset };
}

// ── Status badge ──────────────────────────────────────────────────────────────

/**
 * Render a status badge for an agent task.
 *
 * @param status Task status from the task record.
 * @returns A styled ``Badge`` component.
 */
function StatusBadge({ status }: { status?: string | null }) {
  const normalized = status ?? "idle";
  return (
    <Badge
      variant="outline"
      className={cn(
        "capitalize",
        normalized === "completed" && "border-green-200 text-green-700",
        normalized === "failed" && "border-red-200 text-red-700",
        normalized === "pending" && "border-info/30 text-info animate-pulse",
      )}
    >
      {normalized}
    </Badge>
  );
}

// ── Result displays ───────────────────────────────────────────────────────────

/**
 * Render a career-path analysis result.
 *
 * @param result Career analysis result payload.
 * @returns JSX for positioning, trajectory, and recommendations.
 */
function CareerAnalysisResultView({
  result,
}: {
  result: CareerAnalysisResult;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm">Current Positioning</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm">
              <span className="text-muted-foreground">Experience:</span>{" "}
              {result.current_positioning.experience_level}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">Skills:</span>{" "}
              {result.current_positioning.skill_count}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">Positioning score:</span>{" "}
              {result.current_positioning.positioning_score}
            </p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm">Career Trajectory</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm">
              <span className="text-muted-foreground">Current stage:</span>{" "}
              {result.career_trajectory.current_stage}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">Next stage:</span>{" "}
              {result.career_trajectory.next_stage}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">Timeline:</span>{" "}
              {result.career_trajectory.estimated_timeline}
            </p>
          </CardContent>
        </Card>
      </div>
      <div>
        <h4 className="mb-2 text-sm font-medium">Strategic Recommendations</h4>
        <div className="space-y-2">
          {result.strategic_recommendations.map((rec, idx) => (
            <Card key={idx} size="sm">
              <CardContent className="space-y-1">
                <p className="text-sm font-medium">
                  {rec.title}{" "}
                  <span className="text-xs text-muted-foreground">
                    ({rec.category}, priority: {rec.priority})
                  </span>
                </p>
                <p className="text-sm text-muted-foreground">
                  {rec.description}
                </p>
                {rec.actions.length > 0 && (
                  <ul className="list-disc pl-4 text-sm text-muted-foreground">
                    {rec.actions.map((action, aidx) => (
                      <li key={aidx}>{action}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Render a skill-gap analysis result.
 *
 * @param result Gap analysis result payload.
 * @returns JSX for skill gaps and recommendations.
 */
function GapAnalysisResultView({ result }: { result: GapAnalysisResult }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="mb-2 text-sm font-medium">Skill Gaps by Job</h4>
        <div className="space-y-2">
          {Object.entries(result.skills_gap).map(([job, data]) => (
            <Card key={job} size="sm">
              <CardContent className="space-y-1">
                <p className="text-sm font-medium">{job}</p>
                <p className="text-xs text-muted-foreground">
                  Coverage: {data.coverage} · Matched {data.total_matched} of{" "}
                  {data.total_required}
                </p>
                {data.missing.length > 0 && (
                  <p className="text-xs text-red-600">
                    Missing: {data.missing.join(", ")}
                  </p>
                )}
                {data.overlap.length > 0 && (
                  <p className="text-xs text-green-600">
                    Overlap: {data.overlap.join(", ")}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
      <div>
        <h4 className="mb-2 text-sm font-medium">Recommendations</h4>
        <div className="space-y-2">
          {result.recommendations.map((rec, idx) => (
            <Card key={idx} size="sm">
              <CardContent className="space-y-1">
                <p className="text-sm font-medium">
                  {rec.skill}{" "}
                  <span className="text-xs text-muted-foreground">
                    ({rec.severity}, {rec.type})
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">{rec.job}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Render an upskilling roadmap result.
 *
 * @param result Upskilling roadmap result payload.
 * @returns JSX for priority skills, learning paths, and timeline.
 */
function UpskillingRoadmapResultView({
  result,
}: {
  result: UpskillingRoadmapResult;
}) {
  const stats = [
    { label: "Total timeline", value: `${result.timeline.total_weeks} weeks` },
    { label: "Learning paths", value: result.learning_paths.length },
    { label: "Priority skills", value: result.priority_skills.length },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label} size="sm">
            <CardContent className="py-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {stat.label}
              </p>
              <p className="text-xl font-semibold">{stat.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {result.priority_skills.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium">Priority Skills</h4>
          <div className="flex flex-wrap gap-2">
            {result.priority_skills.map((skill, idx) => (
              <Badge key={idx} variant="outline">
                {skill.skill} ({skill.priority})
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div>
        <h4 className="mb-2 text-sm font-medium">Learning Paths</h4>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {result.learning_paths.map((path, idx) => (
            <Card key={idx} size="sm" className="h-full">
              <CardContent className="space-y-1.5 py-3">
                <p className="text-sm font-medium">{path.skill_name}</p>
                <p className="text-xs text-muted-foreground">
                  {path.current_level} → {path.target_level} · ~
                  {path.estimated_weeks} wks · {path.difficulty}
                </p>
                {path.milestones.length > 0 && (
                  <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                    {path.milestones.map((m) => (
                      <li key={m.week}>
                        Week {m.week}: {m.milestone}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Render SMART career goals result.
 *
 * @param result Career goals result payload.
 * @returns JSX for short-, medium-, long-term, and SMART goals.
 */
function CareerGoalsResultView({ result }: { result: CareerGoalsResult }) {
  const sections: {
    label: string;
    goals: CareerGoalsResult["short_term_goals"];
  }[] = [
    { label: "Short-Term Goals", goals: result.short_term_goals },
    { label: "Medium-Term Goals", goals: result.medium_term_goals },
    { label: "Long-Term Goals", goals: result.long_term_goals },
    { label: "SMART Goals", goals: result.smart_goals },
  ];

  return (
    <div className="space-y-4">
      {sections.map(
        (section) =>
          section.goals.length > 0 && (
            <div key={section.label}>
              <h4 className="mb-2 text-sm font-medium">{section.label}</h4>
              <div className="space-y-2">
                {section.goals.map((goal, idx) => (
                  <Card key={idx} size="sm">
                    <CardContent className="space-y-1">
                      <p className="text-sm font-medium">{goal.goal}</p>
                      <p className="text-xs text-muted-foreground">
                        Timeline: {goal.timeline}
                      </p>
                      {goal.actions.length > 0 && (
                        <ul className="list-disc pl-4 text-xs text-muted-foreground">
                          {goal.actions.map((action, aidx) => (
                            <li key={aidx}>{action}</li>
                          ))}
                        </ul>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ),
      )}
    </div>
  );
}

// ── Keyword input ─────────────────────────────────────────────────────────────

/**
 * Chip-style keyword editor: type a keyword, press Enter or Add, and it
 * appears as a removable chip.
 *
 * @param id ID for the underlying input element.
 * @param keywords Current keyword list.
 * @param onChange Called with the updated keyword list.
 * @param placeholder Placeholder text for the input.
 * @returns Keyword chip editor.
 */
function KeywordListInput({
  id,
  keywords,
  onChange,
  placeholder,
}: {
  id: string;
  keywords: string[];
  onChange: (keywords: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  const addKeyword = () => {
    const value = draft.trim();
    if (!value) return;
    const exists = keywords.some(
      (k) => k.toLowerCase() === value.toLowerCase(),
    );
    if (!exists) onChange([...keywords, value]);
    setDraft("");
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          id={id}
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addKeyword();
            }
          }}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={addKeyword}
          disabled={!draft.trim()}
        >
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </div>
      {keywords.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {keywords.map((keyword) => (
            <Badge key={keyword} variant="secondary" className="gap-1 pr-1">
              {keyword}
              <button
                type="button"
                aria-label={`Remove ${keyword}`}
                className="rounded-sm hover:text-red-500"
                onClick={() => onChange(keywords.filter((k) => k !== keyword))}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab components ────────────────────────────────────────────────────────────

/**
 * Career Path analysis tab: submit optional target jobs and poll for results.
 *
 * @param profile User profile used as the analysis baseline.
 * @returns Tab content with form and result display.
 */
function CareerAnalysisTab({ profile }: { profile: UserProfile }) {
  const { taskId, submit, task, reset } = useAgentTask<CareerAnalysisResult>(
    "Career analysis",
    (id, signal) => agentsApi.getTask<CareerAnalysisResult>(id, signal),
  );

  const [keywords, setKeywords] = useState<string[]>([]);

  const handleAnalyze = () => {
    const payload: CareerAnalysisRequest = {
      profile,
      keywords: keywords.length > 0 ? keywords : undefined,
    };
    submit.mutate(() => agentsApi.careerAnalysis(payload));
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Compass className="h-4 w-4" />
            Career Path Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="career-target-jobs">
                Target Roles (optional)
              </Label>
              <KeywordListInput
                id="career-target-jobs"
                keywords={keywords}
                onChange={setKeywords}
                placeholder="e.g. Senior Software Engineer"
              />
              <p className="text-xs text-muted-foreground">
                Type a role or skill keyword and press Add. Leave empty to
                analyze against your profile targets.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={handleAnalyze}
                disabled={submit.isPending}
              >
                {submit.isPending ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-1.5 h-4 w-4" />
                )}
                {submit.isPending ? "Starting…" : "Analyze Career Path"}
              </Button>
              {taskId && (
                <Button type="button" variant="ghost" onClick={reset}>
                  <RefreshCw className="mr-1.5 h-4 w-4" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {taskId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Result</CardTitle>
              <StatusBadge status={task.data?.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              Task {taskId.slice(0, 12)}… · updated{" "}
              {task.data ? formatDatetime(task.data.updated_at) : "N/A"}
            </p>
          </CardHeader>
          <CardContent>
            {task.isPending && !task.data && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Waiting for first update…
              </div>
            )}
            {task.data?.status === "failed" && (
              <p className="text-sm text-red-600">
                {task.data.error || "Analysis failed."}
              </p>
            )}
            {task.data?.status === "completed" && task.data.result && (
              <CareerAnalysisResultView result={task.data.result} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/**
 * Skill Gap analysis tab: submit target jobs and poll for results.
 *
 * @param profile User profile to compare against target jobs.
 * @returns Tab content with form and result display.
 */
function GapAnalysisTab({ profile }: { profile: UserProfile }) {
  const { taskId, submit, task, reset } = useAgentTask<GapAnalysisResult>(
    "Gap analysis",
    (id, signal) => agentsApi.getTask<GapAnalysisResult>(id, signal),
  );

  const [keywords, setKeywords] = useState<string[]>([]);

  const handleAnalyze = () => {
    if (keywords.length === 0) {
      toast.error("Add at least one target role keyword");
      return;
    }
    const payload: GapAnalysisRequest = { profile, keywords };
    submit.mutate(() => agentsApi.gapAnalysis(payload));
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Target className="h-4 w-4" />
            Skill Gap Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="gap-target-jobs">Target Roles *</Label>
              <KeywordListInput
                id="gap-target-jobs"
                keywords={keywords}
                onChange={setKeywords}
                placeholder="e.g. Backend Developer, Python"
              />
              <p className="text-xs text-muted-foreground">
                Type the roles or skills you want to compare against and press
                Add.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={handleAnalyze}
                disabled={submit.isPending || keywords.length === 0}
              >
                {submit.isPending ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <Target className="mr-1.5 h-4 w-4" />
                )}
                {submit.isPending ? "Starting…" : "Analyze Gaps"}
              </Button>
              {taskId && (
                <Button type="button" variant="ghost" onClick={reset}>
                  <RefreshCw className="mr-1.5 h-4 w-4" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {taskId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Result</CardTitle>
              <StatusBadge status={task.data?.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              Task {taskId.slice(0, 12)}… · updated{" "}
              {task.data ? formatDatetime(task.data.updated_at) : "N/A"}
            </p>
          </CardHeader>
          <CardContent>
            {task.isPending && !task.data && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Waiting for first update…
              </div>
            )}
            {task.data?.status === "failed" && (
              <p className="text-sm text-red-600">
                {task.data.error || "Analysis failed."}
              </p>
            )}
            {task.data?.status === "completed" && task.data.result && (
              <GapAnalysisResultView result={task.data.result} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/**
 * Upskilling Roadmap tab: submit a prior gap-analysis JSON and poll for results.
 *
 * @param profile User profile used to tailor the roadmap.
 * @returns Tab content with form and result display.
 */
function UpskillingRoadmapTab({ profile }: { profile: UserProfile }) {
  const { taskId, submit, task, reset } = useAgentTask<UpskillingRoadmapResult>(
    "Upskilling roadmap",
    (id, signal) => agentsApi.getTask<UpskillingRoadmapResult>(id, signal),
  );

  const [keywords, setKeywords] = useState<string[]>([]);

  const handleGenerate = () => {
    if (keywords.length === 0) {
      toast.error("Add at least one target role or skill keyword");
      return;
    }
    const payload: UpskillingRoadmapRequest = { profile, keywords };
    submit.mutate(() => agentsApi.upskillingRoadmap(payload));
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            Upskilling Roadmap
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="roadmap-target-jobs">Target Roles *</Label>
              <KeywordListInput
                id="roadmap-target-jobs"
                keywords={keywords}
                onChange={setKeywords}
                placeholder="e.g. Data Scientist, Machine Learning"
              />
              <p className="text-xs text-muted-foreground">
                Type the roles or skills you want to grow into and press Add.
                We&apos;ll find your gaps and build a learning plan around them.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={handleGenerate}
                disabled={submit.isPending || keywords.length === 0}
              >
                {submit.isPending ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <BookOpen className="mr-1.5 h-4 w-4" />
                )}
                {submit.isPending ? "Starting…" : "Generate Roadmap"}
              </Button>
              {taskId && (
                <Button type="button" variant="ghost" onClick={reset}>
                  <RefreshCw className="mr-1.5 h-4 w-4" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {taskId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Result</CardTitle>
              <StatusBadge status={task.data?.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              Task {taskId.slice(0, 12)}… · updated{" "}
              {task.data ? formatDatetime(task.data.updated_at) : "N/A"}
            </p>
          </CardHeader>
          <CardContent>
            {task.isPending && !task.data && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Waiting for first update…
              </div>
            )}
            {task.data?.status === "failed" && (
              <p className="text-sm text-red-600">
                {task.data.error || "Analysis failed."}
              </p>
            )}
            {task.data?.status === "completed" && task.data.result && (
              <UpskillingRoadmapResultView result={task.data.result} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/**
 * Career Goals tab: generate SMART goals and poll for results.
 *
 * @param profile User profile used to generate goals.
 * @returns Tab content with trigger and result display.
 */
function CareerGoalsTab({ profile }: { profile: UserProfile }) {
  const { taskId, submit, task, reset } = useAgentTask<CareerGoalsResult>(
    "Career goals",
    (id, signal) => agentsApi.getTask<CareerGoalsResult>(id, signal),
  );

  const onAnalyze = () => {
    submit.mutate(() => agentsApi.careerGoals({ profile }));
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Flag className="h-4 w-4" />
            SMART Career Goals
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Generate short-, medium-, and long-term career goals plus SMART
            goals based on your profile.
          </p>
          <div className="flex gap-2">
            <Button onClick={onAnalyze} disabled={submit.isPending}>
              {submit.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Lightbulb className="mr-1.5 h-4 w-4" />
              )}
              {submit.isPending ? "Starting…" : "Generate Goals"}
            </Button>
            {taskId && (
              <Button type="button" variant="ghost" onClick={reset}>
                <RefreshCw className="mr-1.5 h-4 w-4" />
                Reset
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {taskId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Result</CardTitle>
              <StatusBadge status={task.data?.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              Task {taskId.slice(0, 12)}… · updated{" "}
              {task.data ? formatDatetime(task.data.updated_at) : "N/A"}
            </p>
          </CardHeader>
          <CardContent>
            {task.isPending && !task.data && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Waiting for first update…
              </div>
            )}
            {task.data?.status === "failed" && (
              <p className="text-sm text-red-600">
                {task.data.error || "Analysis failed."}
              </p>
            )}
            {task.data?.status === "completed" && task.data.result && (
              <CareerGoalsResultView result={task.data.result} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

/**
 * Career Coach page providing tabbed access to career analyses.
 *
 * Loads the user profile and renders four analysis tabs: Career Path, Skill
 * Gap, Upskilling Roadmap, and Career Goals. Requires a real profile (contact
 * name) before analysis forms are shown — mirrors the cover-letter CV gate.
 *
 * @returns The Career Coach page component.
 */
export default function CareerCoachPage() {
  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
    staleTime: 60_000,
    retry: 1,
  });

  const profile = profileQuery.data;
  const hasProfile = !!profile?.contact_info?.name;

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        title="Career Coach"
        subtitle="Run AI-powered career analyses against your profile: career-path insights, skill gaps, upskilling roadmaps, and SMART goals."
        icon={<Compass className="h-6 w-6" />}
      />

      {profileQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading profile…
        </div>
      )}

      {!profileQuery.isLoading && !hasProfile && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2.5">
          <p className="text-sm flex items-center gap-2 text-amber-700 dark:text-amber-500">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span>
              No profile uploaded &mdash; career analyses need an active resume.{" "}
              <Link
                href="/profile"
                className="font-medium underline underline-offset-2"
              >
                Upload one on the Profile page
              </Link>
              .
            </span>
          </p>
        </div>
      )}

      {hasProfile && profile && (
        <Tabs defaultValue="career">
          <TabsList className="flex-wrap h-auto">
            <TabsTrigger value="career">Career Path</TabsTrigger>
            <TabsTrigger value="gap">Skill Gap</TabsTrigger>
            <TabsTrigger value="roadmap">Upskilling Roadmap</TabsTrigger>
            <TabsTrigger value="goals">Career Goals</TabsTrigger>
          </TabsList>

          <TabsContent value="career" className="mt-6">
            <CareerAnalysisTab profile={profile} />
          </TabsContent>
          <TabsContent value="gap" className="mt-6">
            <GapAnalysisTab profile={profile} />
          </TabsContent>
          <TabsContent value="roadmap" className="mt-6">
            <UpskillingRoadmapTab profile={profile} />
          </TabsContent>
          <TabsContent value="goals" className="mt-6">
            <CareerGoalsTab profile={profile} />
          </TabsContent>
        </Tabs>
      )}
    </PageContainer>
  );
}
