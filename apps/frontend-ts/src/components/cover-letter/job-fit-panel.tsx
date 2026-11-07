"use client";

import {
  CheckCircle,
  Loader2,
  Gauge,
  AlertTriangle,
  Lightbulb,
} from "lucide-react";
import type { JdMatchResponse } from "@/lib/api/coverLetter";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreExplanationDisplay } from "@/components/score-explanation";
import type { CoverLetterPage } from "@/lib/hooks/use-cover-letter-page";

const recommendationStyles: Record<JdMatchResponse["recommendation"], string> =
  {
    apply: "bg-emerald-500/15 text-emerald-600",
    maybe: "bg-amber-500/15 text-amber-600",
    skip: "bg-red-500/15 text-red-600",
  };

/**
 * Turn a score-breakdown category key (e.g. "keyword_match") into a readable
 * label (e.g. "Keyword Match").
 */
function prettyCategory(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Show the job fit assessment of the pasted job.
 *
 * @param props - The component props.
 * @param props.page - The state and actions of the Cover Letter page.
 * @returns The section.
 */
export function JobFitPanel({ page }: { page: CoverLetterPage }) {
  const {
    assessment,
    assessError,
    assessLoading,
    fitExplain,
    explainFitMutation,
  } = page;
  return (
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
                      <div key={category} className="flex items-center gap-2">
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
                  Company risk: {assessment.scam_risk.toUpperCase()} — flags to
                  review
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
            {fitExplain && <ScoreExplanationDisplay explanation={fitExplain} />}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Fill in the job title, company, and description (50+ characters) to
            see your fit score, breakdown, and company-risk flags.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
