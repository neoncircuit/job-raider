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
import { getApiErrorMessage } from "@/lib/api/client";
import { coverLetterApi, downloadFile } from "@/lib/api/coverLetter";
import type {
  DetectInstructionsResponse,
  JdMatchResponse,
  PrepSheetResponse,
  ScoreExplanation,
} from "@/lib/api/coverLetter";
import { profileApi } from "@/lib/api/profile";
import { buildCoverLetterAnalysisExport } from "@/lib/cover-letter-analysis-export";
import { formatDurationMs, formatTokenCount } from "@/lib/utils/format";
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
import { getJdPasteHint } from "@/lib/utils/jd-paste-hint";
import { Textarea } from "@/components/ui/textarea";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { CoverLetterValidationDisplay } from "@/components/cover-letter-validation";
import { CoverLetterSources } from "@/components/cover-letter-sources";
import { AiWaitProgress } from "@/components/ai-wait-progress";
import { ScoreExplanationDisplay } from "@/components/score-explanation";
import {
  TaskModelSelect,
  SETTINGS_DEFAULT_MODEL_VALUE,
} from "@/components/model-select";
import { createLogger } from "@/lib/logger";
import { resolveMissionSourceCitations } from "@/lib/mission-sources";

const logger = createLogger("CoverLetterPage");

interface FormState {
  title: string;
  company: string;
  location: string;
  description: string;
  style: "modern" | "classic";
  deep: boolean;
  review: boolean;
}

const initialForm: FormState = {
  title: "",
  company: "",
  location: "",
  description: "",
  style: "modern",
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
  const [writerModel, setWriterModel] = useState(SETTINGS_DEFAULT_MODEL_VALUE);
  const [result, setResult] = useState<CoverLetterResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [assessment, setAssessment] = useState<JdMatchResponse | null>(null);
  const [assessError, setAssessError] = useState<string | null>(null);
  const [assessLoading, setAssessLoading] = useState(false);
  const [prepSheet, setPrepSheet] = useState<PrepSheetResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [jdUploadFilename, setJdUploadFilename] = useState<string | null>(null);
  const [jdUploadWarnings, setJdUploadWarnings] = useState<string[]>([]);
  const [jdUploading, setJdUploading] = useState(false);
  const jdFileInputRef = useRef<HTMLInputElement | null>(null);
  const [jdInstructions, setJdInstructions] =
    useState<DetectInstructionsResponse | null>(null);
  const detectAbortRef = useRef<AbortController | null>(null);

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
          style: form.style,
          writer_model:
            writerModel === SETTINGS_DEFAULT_MODEL_VALUE
              ? undefined
              : writerModel,
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
      toast.success(
        data.instructions_context?.short_answer_mode
          ? "Short application answer generated"
          : "Cover letter generated",
      );
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

  const exportAnalysisMutation = useMutation({
    mutationFn: async (format: "json" | "pdf") => {
      if (!result) {
        throw new Error("Generate a cover letter before exporting analysis");
      }
      const analysis = buildCoverLetterAnalysisExport({
        title: form.title,
        company: form.company,
        description: form.description,
        location: form.location || undefined,
        style: form.style,
        deep: form.deep,
        review: form.review,
        writerModelLabel:
          writerModel === SETTINGS_DEFAULT_MODEL_VALUE
            ? result.cover_letter.model_used || "settings-default"
            : writerModel,
        letterText: editedContent || result.cover_letter.content,
        result,
        validation,
        assessment,
      });
      const res = await coverLetterApi.exportAnalysis({
        format,
        analysis: analysis as unknown as Record<string, unknown>,
      });
      const fallback = `cover_letter_analysis_${form.company.replace(/\s+/g, "_")}_${form.title.replace(/\s+/g, "_")}.${format}`;
      await downloadFile(res, fallback);
    },
    onSuccess: (_data, format) => {
      toast.success(
        format === "json"
          ? "Full analysis exported"
          : "Analysis exported as PDF",
      );
    },
    onError: (err: Error) => {
      logger.error("Cover letter analysis export failed", err);
      toast.error(err.message || "Failed to export analysis");
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
  const jdPasteHint = getJdPasteHint(description);

  // Scan the pasted JD for application instructions (why-interest length
  // asks, inclusion asks) while typing. Always runs — not limited to
  // “3-4 lines”; any confident lines/sentences/words range near interest
  // cues may match. Empty/ambiguous JD clears the banner.
  useEffect(() => {
    const timer = setTimeout(async () => {
      detectAbortRef.current?.abort();
      const controller = new AbortController();
      detectAbortRef.current = controller;
      const text = description.trim();
      if (text.length < 20) {
        setJdInstructions(null);
        return;
      }
      try {
        const detected = await coverLetterApi.detectInstructions(
          description,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setJdInstructions(detected);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        logger.error("JD instruction detect failed", err);
      }
    }, 400);
    return () => {
      clearTimeout(timer);
      detectAbortRef.current?.abort();
    };
  }, [description]);

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

  /**
   * Parse an uploaded JD PDF/DOCX into the description textarea.
   * Does not call generate, assess, or prep — the user must still click Generate.
   *
   * @param file - Selected PDF or DOCX file from the file input.
   */
  const handleJdUpload = async (file: File) => {
    setJdUploading(true);
    setJdUploadWarnings([]);
    try {
      const parsed = await coverLetterApi.parseJd(file);
      setForm((f) => ({ ...f, description: parsed.text }));
      setJdUploadFilename(parsed.filename);
      setJdUploadWarnings(parsed.warnings ?? []);
      if (parsed.warnings?.length) {
        toast.warning(parsed.warnings[0]);
      } else {
        toast.success(`Loaded job description from ${parsed.filename}`);
      }
      logger.info("JD document parsed", {
        filename: parsed.filename,
        charCount: parsed.char_count,
      });
    } catch (err) {
      logger.error("JD document parse failed", err);
      toast.error(
        getApiErrorMessage(err, "Failed to parse job description file"),
      );
    } finally {
      setJdUploading(false);
      if (jdFileInputRef.current) {
        jdFileInputRef.current.value = "";
      }
    }
  };

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
          style: form.style,
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
              <div className="space-y-2">
                <Label
                  htmlFor="jd-upload"
                  className="text-sm font-normal text-muted-foreground"
                >
                  Upload job description (PDF or DOCX)
                </Label>
                <Input
                  id="jd-upload"
                  ref={jdFileInputRef}
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  disabled={jdUploading}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      void handleJdUpload(file);
                    }
                  }}
                />
                {jdUploading && (
                  <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Extracting text from document...
                  </p>
                )}
                {jdUploadFilename && !jdUploading && (
                  <p className="text-xs text-muted-foreground">
                    Source file: {jdUploadFilename}
                  </p>
                )}
                {jdUploadWarnings.map((warning) => (
                  <p
                    key={warning}
                    className="text-xs text-amber-700 dark:text-amber-400"
                  >
                    {warning}
                  </p>
                ))}
              </div>
              <Textarea
                id="description"
                placeholder="Paste the full job description here..."
                className="min-h-[240px] resize-y"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
              />
              {jdPasteHint && (
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  {jdPasteHint}
                </p>
              )}
              {jdInstructions &&
                (jdInstructions.short_answer_mode ||
                  jdInstructions.has_inclusions) && (
                  <div
                    className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground space-y-1"
                    role="status"
                  >
                    <p className="font-medium text-foreground">
                      JD application instructions detected
                    </p>
                    {jdInstructions.why_interest && (
                      <p>
                        Length ask:{" "}
                        {jdInstructions.why_interest.max_n == null
                          ? `at least ${jdInstructions.why_interest.min_n}`
                          : `${jdInstructions.why_interest.min_n}${
                              jdInstructions.why_interest.max_n !==
                              jdInstructions.why_interest.min_n
                                ? `–${jdInstructions.why_interest.max_n}`
                                : ""
                            }`}{" "}
                        {jdInstructions.why_interest.unit} on why this interests
                        you (matched “{jdInstructions.why_interest.matched_span}
                        ”). Generate will replace the full letter with that
                        short answer.
                      </p>
                    )}
                    {jdInstructions.inclusions.length > 0 && (
                      <p>
                        Inclusion ask:{" "}
                        {jdInstructions.inclusions
                          .map((item) => item.kind)
                          .join(", ")}
                        . Profile links will be injected when available.
                      </p>
                    )}
                  </div>
                )}
              <p className="text-xs text-muted-foreground">
                Minimum 50 characters required for meaningful generation. Upload
                fills this field only; click Generate when ready. The JD is
                scanned for submission asks (any length unit near
                interest/mission cues, plus include-link asks)—not only “3-4
                lines”.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Letter style</Label>
              <div
                className="grid grid-cols-2 gap-2"
                role="radiogroup"
                aria-label="Cover letter style"
              >
                <Button
                  type="button"
                  variant={form.style === "modern" ? "default" : "outline"}
                  className="h-auto flex-col items-start gap-0.5 py-2.5 px-3"
                  aria-pressed={form.style === "modern"}
                  onClick={() => setForm((f) => ({ ...f, style: "modern" }))}
                >
                  <span className="text-sm font-medium">Modern</span>
                  <span className="text-xs font-normal opacity-80 text-left">
                    Achievement-led opening, no letterhead in body
                  </span>
                </Button>
                <Button
                  type="button"
                  variant={form.style === "classic" ? "default" : "outline"}
                  className="h-auto flex-col items-start gap-0.5 py-2.5 px-3"
                  aria-pressed={form.style === "classic"}
                  onClick={() => setForm((f) => ({ ...f, style: "classic" }))}
                >
                  <span className="text-sm font-medium">Classic</span>
                  <span className="text-xs font-normal opacity-80 text-left">
                    Salutation, formal arc, sincerely + name
                  </span>
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Classic uses a traditional letter structure while staying
                grounded to your resume and the job description. Export still
                adds date and sender details.
              </p>
            </div>

            <TaskModelSelect
              taskType="cover_letter_writing"
              label="Writer model"
              value={writerModel}
              onValueChange={setWriterModel}
            />

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
                  needed. Recommended for local 7B writers (for example
                  qwen2.5:7b).
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
            {generateMutation.isPending ? (
              <AiWaitProgress
                label={
                  form.review
                    ? "Writing and reviewing cover letter…"
                    : "Writing cover letter…"
                }
                hint="The model is working. This can take a minute."
              />
            ) : null}
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
                  {(result.cover_letter.model_used ||
                    result.cover_letter.timing ||
                    result.cover_letter.token_usage) && (
                    <p className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-1">
                      {result.cover_letter.model_used ? (
                        <span>
                          Model:{" "}
                          <span className="font-mono">
                            {result.cover_letter.model_used}
                          </span>
                        </span>
                      ) : null}
                      {result.cover_letter.timing ? (
                        <>
                          <span>
                            Draft:{" "}
                            {formatDurationMs(
                              result.cover_letter.timing.generation_ms,
                            )}
                          </span>
                          {result.cover_letter.timing.rewrite_ms != null ? (
                            <span>
                              Rewrite:{" "}
                              {formatDurationMs(
                                result.cover_letter.timing.rewrite_ms,
                              )}
                            </span>
                          ) : null}
                          {result.cover_letter.timing.review_ms != null ? (
                            <span>
                              Review:{" "}
                              {formatDurationMs(
                                result.cover_letter.timing.review_ms,
                              )}
                            </span>
                          ) : null}
                          <span>
                            Total:{" "}
                            {formatDurationMs(
                              result.cover_letter.timing.total_ms,
                            )}
                          </span>
                        </>
                      ) : null}
                      {result.cover_letter.token_usage?.total_tokens != null ? (
                        <span>
                          Tokens:{" "}
                          {formatTokenCount(
                            result.cover_letter.token_usage.total_tokens,
                          )}
                          {result.cover_letter.token_usage.prompt_tokens !=
                            null &&
                          result.cover_letter.token_usage.completion_tokens !=
                            null ? (
                            <span className="text-muted-foreground/80">
                              {" "}
                              (
                              {formatTokenCount(
                                result.cover_letter.token_usage.prompt_tokens,
                              )}{" "}
                              in /{" "}
                              {formatTokenCount(
                                result.cover_letter.token_usage
                                  .completion_tokens,
                              )}{" "}
                              out)
                            </span>
                          ) : null}
                        </span>
                      ) : null}
                    </p>
                  )}
                  <CoverLetterSources
                    sources={resolveMissionSourceCitations(
                      result.mission_context,
                    )}
                  />
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
                      onClick={() => exportAnalysisMutation.mutate("json")}
                      disabled={
                        exportAnalysisMutation.isPending || !result
                      }
                    >
                      <Download className="mr-1.5 h-3.5 w-3.5" />
                      Export full analysis
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => exportMutation.mutate("pdf")}
                      disabled={exportMutation.isPending || !result}
                    >
                      <Download className="mr-1.5 h-3.5 w-3.5" />
                      Export cover letter PDF
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Full analysis is a JSON snapshot for quality control and
                    model compares. Cover letter PDF is the letter only.
                  </p>
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
                {prepMutation.isPending ? (
                  <CardContent>
                    <AiWaitProgress
                      label="Generating interview prep…"
                      hint="The model is drafting questions and talking points."
                    />
                  </CardContent>
                ) : null}
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
              <CardContent className="text-center space-y-3 w-full max-w-md">
                {generateMutation.isPending ? (
                  <AiWaitProgress
                    label={
                      form.review
                        ? "Writing and reviewing cover letter…"
                        : "Writing cover letter…"
                    }
                    hint="The model is working. This can take a minute."
                  />
                ) : (
                  <>
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                      <Mail className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium">No cover letter yet</p>
                      <p className="text-sm text-muted-foreground">
                        Fill in the job details and click generate.
                      </p>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
