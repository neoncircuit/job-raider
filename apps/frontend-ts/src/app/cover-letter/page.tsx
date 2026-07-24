"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Mail,
  FileText,
  Sparkles,
  Download,
  Copy,
  CheckCircle,
  Loader2,
  PenTool,
  Gauge,
  AlertTriangle,
  ClipboardList,
  HelpCircle,
  Lightbulb,
  FileUser,
  ClipboardCheck,
} from "lucide-react";
import { coverLetterApi, downloadFile } from "@/lib/api/coverLetter";
import type {
  JdMatchResponse,
  PrepSheetResponse,
  ScoreExplanation,
} from "@/lib/api/coverLetter";
import { profileApi } from "@/lib/api/profile";
import { applicationsApi } from "@/lib/api/applications";
import type {
  CoverLetterResponse,
  CoverLetterValidation,
  UserProfile,
} from "@/lib/types/api";
import { formatDate } from "@/lib/utils/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { CoverLetterValidationDisplay } from "@/components/cover-letter-validation";
import { ScoreExplanationDisplay } from "@/components/score-explanation";
import { createLogger } from "@/lib/logger";

const logger = createLogger("CoverLetterPage");

interface FormState {
  title: string;
  company: string;
  location: string;
  description: string;
  deep: boolean;
  review: boolean;
}

const initialForm: FormState = {
  title: "",
  company: "",
  location: "",
  description: "",
  deep: false,
  review: false,
};

const recommendationStyles: Record<JdMatchResponse["recommendation"], string> =
  {
    apply: "bg-emerald-500/15 text-emerald-600",
    maybe: "bg-amber-500/15 text-amber-600",
    skip: "bg-red-500/15 text-red-600",
  };

/** Debounce delay before auto-assessing the pasted JD (ms). */
const ASSESS_DEBOUNCE_MS = 800;

/**
 * Derive a human-friendly filename and file type for the active CV.
 *
 * Prefers the original uploaded filename; falls back to the stored resume
 * path's basename (a generated `profile_<id>.<ext>` name). The file type is
 * the uppercased extension of whichever source is available.
 *
 * @param profile - The active user profile from GET /profile.
 * @returns The display filename and uppercased file type (may be empty).
 */
function describeCv(profile: UserProfile): {
  filename: string;
  fileType: string;
} {
  const source = profile.original_filename ?? profile.resume_path ?? "";
  const base = source.split(/[\\/]/).pop() ?? source;
  const ext = base.includes(".") ? (base.split(".").pop() ?? "") : "";
  return {
    filename: profile.original_filename ?? base ?? "Resume",
    fileType: ext.toUpperCase(),
  };
}

/**
 * Turn a score-breakdown category key (e.g. "keyword_match") into a readable
 * label (e.g. "Keyword Match").
 */
function prettyCategory(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Dedicated Cover Letter tab for the "other" category of jobs discovered
 * outside the platform's scrapers. Paste a job description, generate a
 * tailored cover letter using the local model, and export it as DOCX/PDF.
 */
export default function CoverLetterPage() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [result, setResult] = useState<CoverLetterResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [assessment, setAssessment] = useState<JdMatchResponse | null>(null);
  const [assessError, setAssessError] = useState<string | null>(null);
  const [assessLoading, setAssessLoading] = useState(false);
  const [prepSheet, setPrepSheet] = useState<PrepSheetResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Editable letter body + live-revalidated quality metrics, plus on-demand
  // plain-language explanations of the fit and letter scores.
  const [editedContent, setEditedContent] = useState("");
  const [validation, setValidation] = useState<CoverLetterValidation | null>(
    null,
  );
  const [revalidating, setRevalidating] = useState(false);
  const [fitExplain, setFitExplain] = useState<ScoreExplanation | null>(null);
  const [letterExplain, setLetterExplain] = useState<ScoreExplanation | null>(
    null,
  );
  const revalidateAbortRef = useRef<AbortController | null>(null);
  // Content of the last successfully validated edit. Lets no-op edit cycles
  // (e.g. space then backspace) skip re-validation so the score stays stable.
  // State (not a ref) because it's read during render to disable the button.
  const [lastValidated, setLastValidated] = useState<string | null>(null);

  // Aftermath status recorded to the job tracker for this listing.
  const [aftermath, setAftermath] = useState<string | null>(null);
  const trackedJobIdRef = useRef<string | null>(null);

  // Active CV reference so the user can confirm which resume is being used.
  // Reuses the shared ["profile"] query key, so uploading a new resume on the
  // Profile page refreshes this indicator without a manual reload.
  const {
    data: profile,
    isLoading: profileLoading,
    isError: profileError,
  } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const cv = profile ? describeCv(profile) : null;

  const generateMutation = useMutation({
    mutationFn: () =>
      coverLetterApi.generate(
        {
          title: form.title,
          company: form.company,
          description: form.description,
          location: form.location || undefined,
        },
        form.deep,
        form.review,
      ),
    onSuccess: (data) => {
      setResult(data);
      setEditedContent(data.cover_letter.content);
      setValidation(data.validation);
      setLastValidated(data.cover_letter.content);
      setPrepSheet(null);
      setLetterExplain(null);
      setAftermath(null);
      trackedJobIdRef.current = null;
      toast.success("Cover letter generated");
      logger.info("Generated cover letter", { jobId: data.job_id });
    },
    onError: (err: Error) => {
      logger.error("Cover letter generation failed", err);
      toast.error(err.message || "Failed to generate cover letter");
    },
  });

  const exportMutation = useMutation({
    mutationFn: async (format: "docx" | "pdf") => {
      if (!result) throw new Error("No cover letter to export");
      const res = await coverLetterApi.export({
        content: editedContent,
        format,
        company: form.company,
        title: form.title,
      });
      const fallback = `cover_letter_${form.company.replace(/\s+/g, "_")}_${form.title.replace(/\s+/g, "_")}.${format}`;
      await downloadFile(res, fallback);
    },
    onSuccess: (_, format) => {
      toast.success(`Cover letter exported as ${format.toUpperCase()}`);
    },
    onError: (err: Error) => {
      logger.error("Cover letter export failed", err);
      toast.error(err.message || "Failed to export cover letter");
    },
  });

  const prepMutation = useMutation({
    mutationFn: () =>
      coverLetterApi.prep({
        title: form.title,
        company: form.company,
        description: form.description,
        location: form.location || undefined,
      }),
    onSuccess: (data) => {
      setPrepSheet(data);
      toast.success("Prep sheet generated");
    },
    onError: (err: Error) => {
      logger.error("Prep sheet generation failed", err);
      toast.error(err.message || "Failed to generate prep sheet");
    },
  });

  const explainFitMutation = useMutation({
    mutationFn: () =>
      coverLetterApi.explainFit({
        title: form.title,
        company: form.company,
        description: form.description,
        location: form.location || undefined,
      }),
    onSuccess: setFitExplain,
    onError: (err: Error) => {
      logger.error("Fit explanation failed", err);
      toast.error(err.message || "Failed to explain the score");
    },
  });

  const explainLetterMutation = useMutation({
    mutationFn: () =>
      coverLetterApi.explainLetter({
        content: editedContent,
        title: form.title,
        company: form.company,
        description: form.description,
        location: form.location || undefined,
      }),
    onSuccess: setLetterExplain,
    onError: (err: Error) => {
      logger.error("Letter explanation failed", err);
      toast.error(err.message || "Failed to explain the quality");
    },
  });

  // Record an aftermath status (applied / saved / did-not-apply) to the tracker.
  // The listing is created once (storing the JD in metadata so interview prep
  // can run later from the tracker), then transitioned to the chosen status.
  const aftermathMutation = useMutation({
    mutationFn: async (status: string) => {
      const isNew = !trackedJobIdRef.current;
      const jobId =
        trackedJobIdRef.current ??
        `cl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      trackedJobIdRef.current = jobId;
      if (isNew) {
        await applicationsApi.trackExternal({
          job_id: jobId,
          job_title: form.title,
          company: form.company,
          application_date: new Date().toISOString(),
          application_method: "cover_letter",
          metadata: {
            description: form.description,
            location: form.location || undefined,
          },
        });
      }
      // A brand-new record already starts as "applied"; otherwise transition.
      if (!(isNew && status === "applied")) {
        await applicationsApi.updateStatus(jobId, status);
      }
      return status;
    },
    onSuccess: (status) => {
      setAftermath(status);
      toast.success("Saved to your job tracker");
    },
    onError: (err: Error) => {
      logger.error("Aftermath status update failed", err);
      toast.error(err.message || "Failed to update the tracker");
    },
  });

  const { title, company, location, description } = form;

  // Auto-assess job fit while the user fills in the form, debounced and
  // aborting any in-flight request that has gone stale. All state updates
  // happen inside the debounced callback so the effect body stays free of
  // synchronous setState (which triggers cascading renders).
  useEffect(() => {
    const ready =
      title.trim() && company.trim() && description.trim().length >= 50;

    const timer = setTimeout(async () => {
      abortRef.current?.abort();

      if (!ready) {
        setAssessment(null);
        setFitExplain(null);
        setAssessError(null);
        setAssessLoading(false);
        return;
      }

      const controller = new AbortController();
      abortRef.current = controller;
      setAssessLoading(true);
      setAssessError(null);
      try {
        const data = await coverLetterApi.assess(
          {
            title,
            company,
            description,
            location: location || undefined,
          },
          controller.signal,
        );
        // Only apply the latest request's result (guard against a slow earlier
        // response overwriting a newer one).
        if (abortRef.current === controller) {
          setAssessment(data);
          setFitExplain(null);
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          logger.error("JD assessment failed", err);
          setAssessError("Could not assess job fit");
        }
      } finally {
        if (abortRef.current === controller) setAssessLoading(false);
      }
    }, ASSESS_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [title, company, location, description]);

  const canGenerate =
    form.title.trim() &&
    form.company.trim() &&
    form.description.trim().length >= 50;

  const handleCopy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(editedContent);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      logger.error("Clipboard copy failed", err);
      toast.error("Could not copy to clipboard");
    }
  };

  // Re-run the quality breakdown on the edited letter, on demand. The user
  // triggers this via the "Re-check quality" button once they are done
  // editing, instead of re-validating automatically on every keystroke.
  const handleRevalidate = async () => {
    if (!result) return;

    revalidateAbortRef.current?.abort();
    const controller = new AbortController();
    revalidateAbortRef.current = controller;
    setRevalidating(true);
    try {
      const data = await coverLetterApi.validate(
        {
          content: editedContent,
          title,
          company,
          description,
          location: location || undefined,
          deep: form.deep,
        },
        controller.signal,
      );
      if (revalidateAbortRef.current === controller) {
        setValidation(data);
        setLastValidated(editedContent);
        setLetterExplain(null);
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        logger.error("Cover letter re-validation failed", err);
        toast.error((err as Error).message || "Failed to re-check quality");
      }
    } finally {
      if (revalidateAbortRef.current === controller) setRevalidating(false);
    }
  };

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        title="Cover Letter"
        subtitle="Paste a job description and generate a tailored, proofread cover letter."
        icon={<Mail className="h-6 w-6 text-primary" />}
      />

      {/* Active CV indicator: confirms which resume is being referenced. */}
      <div className="rounded-lg border bg-muted/30 px-4 py-2.5">
        {profileLoading ? (
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Checking active CV...
          </p>
        ) : profileError || !profile || !cv ? (
          <p className="text-sm flex items-center gap-2 text-amber-600 dark:text-amber-500">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span>
              No CV uploaded &mdash; generation needs an active resume.{" "}
              <Link
                href="/profile"
                className="font-medium underline underline-offset-2"
              >
                Upload one on the Profile page
              </Link>
              .
            </span>
          </p>
        ) : (
          <div className="flex items-center gap-2.5">
            <FileUser className="h-4 w-4 text-primary shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">
                Referencing CV: {cv.filename}
              </p>
              <p className="text-xs text-muted-foreground">
                {[
                  profile.contact_info?.name,
                  cv.fileType || null,
                  profile.created_at
                    ? `uploaded ${formatDate(profile.created_at)}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Input form */}
        <Card className="lg:col-span-4">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              Job Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="title">Job Title</Label>
                <Input
                  id="title"
                  placeholder="e.g. Software Engineer"
                  value={form.title}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, title: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="company">Company</Label>
                <Input
                  id="company"
                  placeholder="e.g. Acme Inc"
                  value={form.company}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, company: e.target.value }))
                  }
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="location">Location (optional)</Label>
              <Input
                id="location"
                placeholder="e.g. Remote / Singapore"
                value={form.location}
                onChange={(e) =>
                  setForm((f) => ({ ...f, location: e.target.value }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Job Description</Label>
              <Textarea
                id="description"
                placeholder="Paste the full job description here..."
                className="min-h-[240px] resize-y"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
              />
              <p className="text-xs text-muted-foreground">
                Minimum 50 characters required for meaningful generation.
              </p>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <Label
                  htmlFor="deep"
                  className="text-sm font-medium flex items-center gap-2"
                >
                  <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                  Deep validation
                </Label>
                <p className="text-xs text-muted-foreground">
                  Use the LLM for deeper proofreading and feedback.
                </p>
              </div>
              <Switch
                id="deep"
                checked={form.deep}
                onCheckedChange={(checked) =>
                  setForm((f) => ({ ...f, deep: checked }))
                }
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <Label
                  htmlFor="review"
                  className="text-sm font-medium flex items-center gap-2"
                >
                  <PenTool className="h-3.5 w-3.5 text-primary" />
                  Review & rewrite
                </Label>
                <p className="text-xs text-muted-foreground">
                  Ask a reviewer to critique the draft and rewrite it once if
                  needed.
                </p>
              </div>
              <Switch
                id="review"
                checked={form.review}
                onCheckedChange={(checked) =>
                  setForm((f) => ({ ...f, review: checked }))
                }
              />
            </div>

            <Button
              className="w-full"
              disabled={!canGenerate || generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate Cover Letter
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Job fit column */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Gauge className="h-4 w-4 text-primary" />
              Job Fit
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {assessLoading ? (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Assessing job fit...
              </p>
            ) : assessError ? (
              <p className="text-sm text-destructive flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5" />
                {assessError}
              </p>
            ) : assessment ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium flex items-center gap-2">
                    <Gauge className="h-3.5 w-3.5 text-primary" />
                    Job fit: {assessment.score}/100
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${recommendationStyles[assessment.recommendation]}`}
                  >
                    {assessment.recommendation.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {assessment.reasoning}
                </p>
                {Object.keys(assessment.breakdown).length > 0 && (
                  <div className="space-y-1 pt-0.5">
                    <p className="text-[11px] font-medium text-muted-foreground">
                      Score breakdown (points toward 100)
                    </p>
                    {Object.entries(assessment.breakdown)
                      .sort((a, b) => b[1] - a[1])
                      .map(([category, points]) => {
                        const max = Math.max(
                          ...Object.values(assessment.breakdown),
                          1,
                        );
                        return (
                          <div
                            key={category}
                            className="flex items-center gap-2"
                          >
                            <span className="w-28 shrink-0 text-[11px] text-muted-foreground">
                              {prettyCategory(category)}
                            </span>
                            <div className="h-1.5 flex-1 rounded-full bg-muted">
                              <div
                                className="h-1.5 rounded-full bg-primary"
                                style={{
                                  width: `${(points / max) * 100}%`,
                                }}
                              />
                            </div>
                            <span className="w-6 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">
                              {points}
                            </span>
                          </div>
                        );
                      })}
                  </div>
                )}
                {assessment.matched_keywords.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium">Matched:</span>{" "}
                    {assessment.matched_keywords.slice(0, 12).join(", ")}
                  </p>
                )}
                {assessment.missing_skills.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium">Missing skills:</span>{" "}
                    {assessment.missing_skills.join(", ")}
                  </p>
                )}
                {assessment.scam_flags.length > 0 ? (
                  <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 space-y-1">
                    <p className="text-[11px] font-semibold text-amber-600 flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" />
                      Company risk: {assessment.scam_risk.toUpperCase()} — flags
                      to review
                    </p>
                    <ul className="list-disc pl-4 text-[11px] text-muted-foreground space-y-0.5">
                      {assessment.scam_flags.map((flag) => (
                        <li key={flag}>{flag}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="text-[11px] text-emerald-600 flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" />
                    No common scam signals detected
                  </p>
                )}
                <div className="pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => explainFitMutation.mutate()}
                    disabled={explainFitMutation.isPending}
                  >
                    {explainFitMutation.isPending ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Lightbulb className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    {fitExplain ? "Refresh explanation" : "Explain this score"}
                  </Button>
                </div>
                {fitExplain && (
                  <ScoreExplanationDisplay explanation={fitExplain} />
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Fill in the job title, company, and description (50+ characters)
                to see your fit score, breakdown, and company-risk flags.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Result panel */}
        <div className="space-y-6 lg:col-span-5">
          {result ? (
            <>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-primary" />
                      Generated Cover Letter
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopy}
                        disabled={copied}
                      >
                        {copied ? (
                          <CheckCircle className="mr-1.5 h-3.5 w-3.5" />
                        ) : (
                          <Copy className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        {copied ? "Copied" : "Copy"}
                      </Button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Textarea
                    value={editedContent}
                    onChange={(e) => {
                      setEditedContent(e.target.value);
                      setLetterExplain(null);
                    }}
                    className="min-h-[320px] resize-y font-serif leading-relaxed"
                  />
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                      {revalidating ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Re-checking quality...
                        </>
                      ) : (
                        "Edit the letter above, then re-check the quality on demand."
                      )}
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRevalidate}
                      disabled={revalidating || editedContent === lastValidated}
                    >
                      {revalidating ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <ClipboardCheck className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      Re-check quality
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => exportMutation.mutate("docx")}
                      disabled={exportMutation.isPending}
                    >
                      <Download className="mr-1.5 h-3.5 w-3.5" />
                      Export DOCX
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => exportMutation.mutate("pdf")}
                      disabled={exportMutation.isPending}
                    >
                      <Download className="mr-1.5 h-3.5 w-3.5" />
                      Export PDF
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Aftermath status recorded to the job tracker. */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <ClipboardCheck className="h-4 w-4 text-primary" />
                    Application status
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-xs text-muted-foreground">
                    Record what you did with this listing — it appears in your
                    job tracker, and its job description is saved for interview
                    prep later.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Applied", value: "applied" },
                      { label: "Saved", value: "saved_bookmarked" },
                      { label: "Did not apply", value: "not_interested" },
                    ].map(({ label, value }) => (
                      <Button
                        key={value}
                        size="sm"
                        variant={aftermath === value ? "default" : "outline"}
                        disabled={aftermathMutation.isPending}
                        onClick={() => aftermathMutation.mutate(value)}
                      >
                        {aftermathMutation.isPending &&
                        aftermathMutation.variables === value ? (
                          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                        ) : null}
                        {label}
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {validation && (
                <div className="space-y-2">
                  <div className="flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => explainLetterMutation.mutate()}
                      disabled={explainLetterMutation.isPending}
                    >
                      {explainLetterMutation.isPending ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Lightbulb className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      {letterExplain
                        ? "Refresh explanation"
                        : "Explain quality"}
                    </Button>
                  </div>
                  <CoverLetterValidationDisplay validation={validation} />
                  {letterExplain && (
                    <ScoreExplanationDisplay explanation={letterExplain} />
                  )}
                </div>
              )}

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <ClipboardList className="h-4 w-4 text-primary" />
                      Interview Prep
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => prepMutation.mutate()}
                      disabled={prepMutation.isPending}
                    >
                      {prepMutation.isPending ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      {prepSheet ? "Regenerate" : "Generate prep sheet"}
                    </Button>
                  </CardTitle>
                </CardHeader>
                {prepSheet && (
                  <CardContent className="space-y-4 text-sm">
                    {prepSheet.likely_questions.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="font-medium flex items-center gap-2">
                          <HelpCircle className="h-3.5 w-3.5 text-primary" />
                          Likely questions
                        </p>
                        <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                          {prepSheet.likely_questions.map((q) => (
                            <li key={q}>{q}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {prepSheet.gaps_to_address.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="font-medium flex items-center gap-2">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                          Gaps to address honestly
                        </p>
                        <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                          {prepSheet.gaps_to_address.map((g) => (
                            <li key={g}>{g}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {prepSheet.talking_points.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="font-medium flex items-center gap-2">
                          <Lightbulb className="h-3.5 w-3.5 text-primary" />
                          Talking points
                        </p>
                        <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                          {prepSheet.talking_points.map((t) => (
                            <li key={t}>{t}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            </>
          ) : (
            <Card className="h-full min-h-[400px] flex items-center justify-center">
              <CardContent className="text-center space-y-3">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                  <Mail className="h-6 w-6 text-muted-foreground" />
                </div>
                <div>
                  <p className="font-medium">No cover letter yet</p>
                  <p className="text-sm text-muted-foreground">
                    Fill in the job details and click generate.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
