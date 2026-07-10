"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod/v4";
import { toast } from "sonner";
import {
  BookOpen,
  Compass,
  Flag,
  Lightbulb,
  Loader2,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import { agentsApi } from "@/lib/api/agents";
import { profileApi } from "@/lib/api/profile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { PageContainer } from "@/components/layout/PageContainer";
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

// ── Helpers ───────────────────────────────────────────────────────────────────

const emptyProfile: UserProfile = {
  contact_info: {},
  target_job: {
    keywords: [],
    locations: [],
    experience_levels: [],
    remote_preference: false,
    constraint_mode: "boost",
  },
  skills: [],
  work_experience: [],
  education: [],
  projects: [],
};

/**
 * Parse an optional JSON array string into a list of objects.
 *
 * @param raw Raw JSON array string; whitespace-only strings yield ``undefined``.
 * @returns Parsed array of objects, or ``undefined`` if the input is empty.
 */
function parseOptionalJsonArray(
  raw: string,
): Record<string, unknown>[] | undefined {
  if (!raw.trim()) return undefined;
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) throw new Error("Expected a JSON array");
  return parsed as Record<string, unknown>[];
}

/**
 * Parse a required JSON array string into a non-empty list of objects.
 *
 * @param raw Raw JSON array string.
 * @returns Parsed non-empty array of objects.
 * @throws Error if the input is not a non-empty JSON array.
 */
function parseRequiredJsonArray(raw: string): Record<string, unknown>[] {
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error("Expected a non-empty JSON array");
  }
  return parsed as Record<string, unknown>[];
}

/**
 * Parse a required JSON object string into a record.
 *
 * @param raw Raw JSON object string.
 * @returns Parsed object as a record.
 * @throws Error if the input is not a JSON object.
 */
function parseRequiredJsonObject(raw: string): Record<string, unknown> {
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Expected a JSON object");
  }
  return parsed as Record<string, unknown>;
}

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
        normalized === "pending" &&
          "border-blue-200 text-blue-700 animate-pulse",
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
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Badge variant="secondary">
          Timeline: {result.timeline.total_weeks} weeks
        </Badge>
      </div>
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
      <div>
        <h4 className="mb-2 text-sm font-medium">Learning Paths</h4>
        <div className="space-y-2">
          {result.learning_paths.map((path, idx) => (
            <Card key={idx} size="sm">
              <CardContent className="space-y-1">
                <p className="text-sm font-medium">
                  {path.skill_name} · {path.current_level} → {path.target_level}
                </p>
                <p className="text-xs text-muted-foreground">
                  Estimated {path.estimated_weeks} weeks · difficulty:{" "}
                  {path.difficulty}
                </p>
                {path.milestones.length > 0 && (
                  <ul className="list-disc pl-4 text-xs text-muted-foreground">
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

// ── Form schemas ──────────────────────────────────────────────────────────────

const jsonArrayFieldSchema = z.string().refine(
  (v) => {
    if (!v.trim()) return true;
    try {
      return Array.isArray(JSON.parse(v));
    } catch {
      return false;
    }
  },
  { message: "Must be a valid JSON array" },
);

const jsonArrayRequiredFieldSchema = z
  .string()
  .min(1, "Target jobs are required")
  .refine(
    (v) => {
      try {
        const parsed = JSON.parse(v);
        return Array.isArray(parsed) && parsed.length > 0;
      } catch {
        return false;
      }
    },
    { message: "Must be a valid non-empty JSON array" },
  );

const jsonObjectRequiredFieldSchema = z
  .string()
  .min(1, "Gap analysis result is required")
  .refine(
    (v) => {
      try {
        const parsed = JSON.parse(v);
        return parsed && typeof parsed === "object" && !Array.isArray(parsed);
      } catch {
        return false;
      }
    },
    { message: "Must be a valid JSON object" },
  );

const careerAnalysisSchema = z.object({ targetJobs: jsonArrayFieldSchema });
const gapAnalysisSchema = z.object({
  targetJobs: jsonArrayRequiredFieldSchema,
});
const roadmapSchema = z.object({ gapJson: jsonObjectRequiredFieldSchema });

/** Runtime schema for a single job's skill-gap data. */
const jobGapDataSchema = z.object({
  missing: z.array(z.string()),
  overlap: z.array(z.string()),
  coverage: z.number(),
  total_required: z.number(),
  total_matched: z.number(),
});

/** Runtime schema for a skill-gap recommendation entry. */
const skillGapRecommendationSchema = z.object({
  type: z.string(),
  skill: z.string(),
  severity: z.string(),
  job: z.string(),
  resources: z.array(z.record(z.string(), z.unknown())),
});

/** Runtime schema validating the JSON payload accepted by the roadmap tab. */
const gapAnalysisResultSchema = z.object({
  skills_gap: z.record(z.string(), jobGapDataSchema),
  experience_gap: z.record(z.string(), z.unknown()),
  education_gap: z.record(z.string(), z.unknown()),
  recommendations: z.array(skillGapRecommendationSchema),
});

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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ targetJobs: string }>({
    resolver: zodResolver(careerAnalysisSchema),
    defaultValues: { targetJobs: "" },
  });

  const onSubmit = ({ targetJobs }: { targetJobs: string }) => {
    const target_jobs = parseOptionalJsonArray(targetJobs);
    const payload: CareerAnalysisRequest = { profile, target_jobs };
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
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="career-target-jobs">
                Target Jobs JSON (optional)
              </Label>
              <Textarea
                id="career-target-jobs"
                placeholder={`[{"title": "Senior Software Engineer", "company": "Example Corp"}]`}
                {...register("targetJobs")}
              />
              <p className="text-xs text-muted-foreground">
                Paste a JSON array of target jobs, or leave blank to analyze
                against your profile targets.
              </p>
              {errors.targetJobs && (
                <p className="text-xs text-red-500">
                  {errors.targetJobs.message}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={submit.isPending}>
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
          </form>
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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ targetJobs: string }>({
    resolver: zodResolver(gapAnalysisSchema),
    defaultValues: { targetJobs: "" },
  });

  const onSubmit = ({ targetJobs }: { targetJobs: string }) => {
    const target_jobs = parseRequiredJsonArray(targetJobs);
    const payload: GapAnalysisRequest = { profile, target_jobs };
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
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="gap-target-jobs">Target Jobs JSON *</Label>
              <Textarea
                id="gap-target-jobs"
                placeholder={`[{"title": "Senior Software Engineer", "required_skills": ["Python", "FastAPI"]}]`}
                {...register("targetJobs")}
              />
              <p className="text-xs text-muted-foreground">
                Paste a JSON array describing the roles you want to compare
                against your profile.
              </p>
              {errors.targetJobs && (
                <p className="text-xs text-red-500">
                  {errors.targetJobs.message}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={submit.isPending}>
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
          </form>
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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ gapJson: string }>({
    resolver: zodResolver(roadmapSchema),
    defaultValues: { gapJson: "" },
  });

  const onSubmit = ({ gapJson }: { gapJson: string }) => {
    const parsedGap = parseRequiredJsonObject(gapJson);
    const gap_analysis: GapAnalysisResult =
      gapAnalysisResultSchema.parse(parsedGap);
    const payload: UpskillingRoadmapRequest = { gap_analysis, profile };
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
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="roadmap-gap-json">Gap Analysis JSON *</Label>
              <Textarea
                id="roadmap-gap-json"
                placeholder={`{"skills_gap": {...}, "recommendations": [...]}`}
                className="min-h-40"
                {...register("gapJson")}
              />
              <p className="text-xs text-muted-foreground">
                Paste the JSON result from a previous gap analysis.
              </p>
              {errors.gapJson && (
                <p className="text-xs text-red-500">{errors.gapJson.message}</p>
              )}
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={submit.isPending}>
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
          </form>
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
 * Gap, Upskilling Roadmap, and Career Goals.
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

  const profile = profileQuery.data ?? emptyProfile;

  return (
    <PageContainer variant="wide">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Compass className="h-6 w-6" />
            Career Coach
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Run AI-powered career analyses against your profile: career-path
            insights, skill gaps, upskilling roadmaps, and SMART goals.
          </p>
        </div>

        <Tabs defaultValue="career">
          <TabsList className="flex-wrap h-auto">
            <TabsTrigger value="career">Career Path</TabsTrigger>
            <TabsTrigger value="gap">Skill Gap</TabsTrigger>
            <TabsTrigger value="roadmap">Upskilling Roadmap</TabsTrigger>
            <TabsTrigger value="goals">Career Goals</TabsTrigger>
          </TabsList>

          <TabsContent value="career" className="mt-5">
            <CareerAnalysisTab profile={profile} />
          </TabsContent>
          <TabsContent value="gap" className="mt-5">
            <GapAnalysisTab profile={profile} />
          </TabsContent>
          <TabsContent value="roadmap" className="mt-5">
            <UpskillingRoadmapTab profile={profile} />
          </TabsContent>
          <TabsContent value="goals" className="mt-5">
            <CareerGoalsTab profile={profile} />
          </TabsContent>
        </Tabs>
      </div>
    </PageContainer>
  );
}
