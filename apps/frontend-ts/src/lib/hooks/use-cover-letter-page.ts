/**
 * State, queries, and actions of the Cover Letter page.
 *
 * Moved from `src/app/cover-letter/page.tsx` with no change in behaviour, so
 * the page and its section components stay small.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
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
import { applicationsApi } from "@/lib/api/applications";
import type {
  CoverLetterResponse,
  CoverLetterValidation,
  UserProfile,
} from "@/lib/types/api";
import { getJdPasteHint } from "@/lib/utils/jd-paste-hint";
import { SETTINGS_DEFAULT_MODEL_VALUE } from "@/components/model-select";
import { createLogger } from "@/lib/logger";

const logger = createLogger("CoverLetterPage");

export interface FormState {
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
 * Hold the state of the Cover Letter page, and run its queries and actions.
 *
 * @returns Each value and handler that the page sections read.
 */
export function useCoverLetterPage() {
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
      toast.error(getApiErrorMessage(err, "Failed to generate cover letter"));
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

  return {
    form,
    setForm,
    writerModel,
    setWriterModel,
    result,
    setResult,
    copied,
    setCopied,
    assessment,
    setAssessment,
    assessError,
    setAssessError,
    assessLoading,
    setAssessLoading,
    prepSheet,
    setPrepSheet,
    abortRef,
    jdUploadFilename,
    setJdUploadFilename,
    jdUploadWarnings,
    setJdUploadWarnings,
    jdUploading,
    setJdUploading,
    jdFileInputRef,
    jdInstructions,
    setJdInstructions,
    detectAbortRef,
    editedContent,
    setEditedContent,
    validation,
    setValidation,
    revalidating,
    setRevalidating,
    fitExplain,
    setFitExplain,
    letterExplain,
    setLetterExplain,
    revalidateAbortRef,
    lastValidated,
    setLastValidated,
    aftermath,
    setAftermath,
    trackedJobIdRef,
    cv,
    generateMutation,
    exportMutation,
    exportAnalysisMutation,
    prepMutation,
    explainFitMutation,
    explainLetterMutation,
    aftermathMutation,
    jdPasteHint,
    handleJdUpload,
    canGenerate,
    handleCopy,
    handleRevalidate,
    profile,
    profileLoading,
    profileError,
    title,
    company,
    location,
    description,
  };
}

/** Everything that the Cover Letter page sections read. */
export type CoverLetterPage = ReturnType<typeof useCoverLetterPage>;
