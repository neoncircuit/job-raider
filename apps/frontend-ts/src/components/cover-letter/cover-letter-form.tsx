"use client";

import { FileText, Sparkles, Loader2, PenTool } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { AiWaitProgress } from "@/components/ai-wait-progress";
import { TaskModelSelect } from "@/components/model-select";
import type { CoverLetterPage } from "@/lib/hooks/use-cover-letter-page";

/**
 * Show the job details form and the Generate button.
 *
 * @param props - The component props.
 * @param props.page - The state and actions of the Cover Letter page.
 * @returns The section.
 */
export function CoverLetterForm({ page }: { page: CoverLetterPage }) {
  const {
    form,
    setForm,
    writerModel,
    setWriterModel,
    jdUploadFilename,
    jdUploadWarnings,
    jdUploading,
    jdFileInputRef,
    jdInstructions,
    generateMutation,
    jdPasteHint,
    handleJdUpload,
    canGenerate,
  } = page;
  return (
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
                    {jdInstructions.why_interest.unit} on why this interests you
                    (matched “{jdInstructions.why_interest.matched_span}
                    ”). Generate will replace the full letter with that short
                    answer.
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
            fills this field only; click Generate when ready. The JD is scanned
            for submission asks (any length unit near interest/mission cues,
            plus include-link asks)—not only “3-4 lines”.
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
            Classic uses a traditional letter structure while staying grounded
            to your resume and the job description. Export still adds date and
            sender details.
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
              needed. Recommended for local 7B writers (for example qwen2.5:7b).
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
  );
}
