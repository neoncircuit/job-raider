"use client";

import {
  Mail,
  FileText,
  Sparkles,
  Download,
  Copy,
  CheckCircle,
  Loader2,
  AlertTriangle,
  ClipboardList,
  HelpCircle,
  Lightbulb,
  ClipboardCheck,
} from "lucide-react";
import { formatDurationMs, formatTokenCount } from "@/lib/utils/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { CoverLetterValidationDisplay } from "@/components/cover-letter-validation";
import { CoverLetterSources } from "@/components/cover-letter-sources";
import { AiWaitProgress } from "@/components/ai-wait-progress";
import { CloudBadge } from "@/components/cloud-badge";
import { ScoreExplanationDisplay } from "@/components/score-explanation";
import { resolveMissionSourceCitations } from "@/lib/mission-sources";
import type { CoverLetterPage } from "@/lib/hooks/use-cover-letter-page";

/**
 * Show the letter, its checks, and its follow-up actions.
 *
 * @param props - The component props.
 * @param props.page - The state and actions of the Cover Letter page.
 * @returns The section.
 */
export function CoverLetterResult({ page }: { page: CoverLetterPage }) {
  const {
    form,
    result,
    copied,
    prepSheet,
    editedContent,
    setEditedContent,
    validation,
    revalidating,
    letterExplain,
    setLetterExplain,
    lastValidated,
    aftermath,
    generateMutation,
    exportMutation,
    exportAnalysisMutation,
    prepMutation,
    explainLetterMutation,
    aftermathMutation,
    handleCopy,
    handleRevalidate,
  } = page;
  return (
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
                    <span className="inline-flex items-center gap-1.5">
                      Model:{" "}
                      <span className="font-mono">
                        {result.cover_letter.model_used}
                      </span>
                      <CloudBadge
                        show={Boolean(
                          result.cover_letter.provider_used &&
                          result.cover_letter.provider_used !== "ollama",
                        )}
                      />
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
                        {formatDurationMs(result.cover_letter.timing.total_ms)}
                      </span>
                    </>
                  ) : null}
                  {result.cover_letter.token_usage?.total_tokens != null ? (
                    <span>
                      Tokens:{" "}
                      {formatTokenCount(
                        result.cover_letter.token_usage.total_tokens,
                      )}
                      {result.cover_letter.token_usage.prompt_tokens != null &&
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
                            result.cover_letter.token_usage.completion_tokens,
                          )}{" "}
                          out)
                        </span>
                      ) : null}
                    </span>
                  ) : null}
                </p>
              )}
              <CoverLetterSources
                sources={resolveMissionSourceCitations(result.mission_context)}
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
                  disabled={exportAnalysisMutation.isPending || !result}
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
                Full analysis is a JSON snapshot for quality control and model
                compares. Cover letter PDF is the letter only.
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
                Record what you did with this listing — it appears in your job
                tracker, and its job description is saved for interview prep
                later.
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
                  {letterExplain ? "Refresh explanation" : "Explain quality"}
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
  );
}
