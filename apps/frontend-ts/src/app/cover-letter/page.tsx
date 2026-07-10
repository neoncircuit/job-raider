"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
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
} from "lucide-react";
import { coverLetterApi, downloadFile } from "@/lib/api/coverLetter";
import type { CoverLetterResponse } from "@/lib/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { PageContainer } from "@/components/layout/PageContainer";
import { CoverLetterValidationDisplay } from "@/components/cover-letter-validation";
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

/**
 * Dedicated Cover Letter tab for the "other" category of jobs discovered
 * outside the platform's scrapers. Paste a job description, generate a
 * tailored cover letter using the local model, and export it as DOCX/PDF.
 */
export default function CoverLetterPage() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [result, setResult] = useState<CoverLetterResponse | null>(null);
  const [copied, setCopied] = useState(false);

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
        content: result.cover_letter.content,
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

  const canGenerate =
    form.title.trim() &&
    form.company.trim() &&
    form.description.trim().length >= 50;

  const handleCopy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.cover_letter.content);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      logger.error("Clipboard copy failed", err);
      toast.error("Could not copy to clipboard");
    }
  };

  return (
    <PageContainer variant="content" className="py-6">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Mail className="h-6 w-6 text-primary" />
          Cover Letter
        </h1>
        <p className="text-muted-foreground">
          Paste a job description and generate a tailored, proofread cover
          letter.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input form */}
        <Card>
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
                  <PenTool className="h-3.5 w-3.5 text-indigo-500" />
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

        {/* Result panel */}
        <div className="space-y-6">
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
                    readOnly
                    value={result.cover_letter.content}
                    className="min-h-[320px] resize-y font-serif leading-relaxed"
                  />
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

              <CoverLetterValidationDisplay validation={result.validation} />
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
