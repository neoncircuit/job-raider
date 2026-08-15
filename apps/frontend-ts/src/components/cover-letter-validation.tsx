"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type {
  CoverLetterReviewDetails,
  CoverLetterValidation,
} from "@/lib/types/api";
import {
  CheckCircle,
  AlertCircle,
  XCircle,
  FileText,
  LayoutTemplate,
  MessageSquare,
  PenTool,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { formatDurationMs } from "@/lib/utils/format";

interface CoverLetterValidationDisplayProps {
  validation: CoverLetterValidation;
}

const RECOMMENDATION_CONFIG: Record<
  CoverLetterValidation["recommendation"],
  {
    label: string;
    color: string;
    bg: string;
    border: string;
    icon: typeof CheckCircle;
  }
> = {
  approve: {
    label: "Ready to send",
    color: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    icon: CheckCircle,
  },
  needs_revision: {
    label: "Needs revision",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertCircle,
  },
  reject: {
    label: "Major issues",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    icon: XCircle,
  },
};

function scoreColor(score: number): string {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-amber-600";
  if (score >= 40) return "text-orange-600";
  return "text-red-600";
}

function scoreBarColor(score: number): string {
  if (score >= 80) return "bg-green-500";
  if (score >= 60) return "bg-amber-500";
  if (score >= 40) return "bg-orange-500";
  return "bg-red-500";
}

function issueLabel(issue: string): string {
  return issue
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function ScoreBar({
  label,
  score,
  icon: Icon,
}: {
  label: string;
  score: number;
  icon: typeof LayoutTemplate;
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="w-20 text-xs text-muted-foreground">{label}</span>
      <div className="flex-1">
        <div className="h-1.5 w-full rounded-full bg-muted">
          <div
            className={cn(
              "h-1.5 rounded-full transition-all",
              scoreBarColor(score),
            )}
            style={{ width: `${Math.min(Math.max(score, 0), 100)}%` }}
          />
        </div>
      </div>
      <span
        className={cn("w-8 text-right text-xs font-medium", scoreColor(score))}
      >
        {score}
      </span>
    </div>
  );
}

export function CoverLetterValidationDisplay({
  validation,
}: CoverLetterValidationDisplayProps) {
  // Fall back gracefully if the backend sends an unrecognized recommendation
  // (e.g. an LLM validator returning a non-canonical string) so the whole
  // result panel never crashes on an unexpected value.
  const config =
    RECOMMENDATION_CONFIG[validation.recommendation] ??
    RECOMMENDATION_CONFIG.needs_revision;
  const RecIcon = config.icon;

  const details = validation.details as Record<string, unknown> | undefined;
  const paragraphCount =
    typeof details?.paragraph_count === "number"
      ? details.paragraph_count
      : null;
  const companyMentioned =
    typeof details?.company_mentioned === "boolean"
      ? details.company_mentioned
      : null;
  const jobTitleMentioned =
    typeof details?.job_title_mentioned === "boolean"
      ? details.job_title_mentioned
      : null;
  const hasCallToAction =
    typeof details?.has_call_to_action === "boolean"
      ? details.has_call_to_action
      : null;
  const referencedProjects = Array.isArray(details?.referenced_projects)
    ? (details.referenced_projects as string[])
    : [];
  const llmFeedback = Array.isArray(details?.llm_feedback)
    ? (details.llm_feedback as string[])
    : [];
  const ungroundedSentences = Array.isArray(details?.ungrounded_sentences)
    ? (details.ungrounded_sentences as string[])
    : [];
  const claimOverclaims = Array.isArray(details?.claim_overclaims)
    ? (
        details.claim_overclaims as Array<{
          sentence?: string;
          flags?: string[];
        }>
      ).filter(
        (item) => item && (item.sentence || (item.flags?.length ?? 0) > 0),
      )
    : [];
  const fabricatedTechnologies = Array.isArray(details?.fabricated_technologies)
    ? (details.fabricated_technologies as string[])
    : [];
  const inflatedDurationClaims = Array.isArray(
    details?.inflated_duration_claims,
  )
    ? (
        details.inflated_duration_claims as Array<{
          sentence?: string;
          flags?: string[];
          claimed_years?: number;
          cap_years?: number;
        }>
      ).filter(
        (item) => item && (item.sentence || (item.flags?.length ?? 0) > 0),
      )
    : [];
  const inconsistentPercentClaims = Array.isArray(
    details?.inconsistent_percent_claims,
  )
    ? (
        details.inconsistent_percent_claims as Array<{
          sentence?: string;
          flags?: string[];
          from_pct?: number;
          to_pct?: number;
          claimed_pct?: number;
        }>
      ).filter(
        (item) => item && (item.sentence || (item.flags?.length ?? 0) > 0),
      )
    : [];
  const groundingPenalty =
    details?.grounding_penalty &&
    typeof details.grounding_penalty === "object" &&
    !Array.isArray(details.grounding_penalty)
      ? (details.grounding_penalty as {
          soft_ungrounded?: number;
          hard_ungrounded?: number;
          scope_inflation?: number;
          technique_mismatch?: number;
          fabricated_tech?: number;
          inflated_duration?: number;
          inconsistent_metric?: number;
          capped_penalty?: number;
          weights?: {
            soft_ungrounded?: number;
            hard_ungrounded?: number;
            scope_inflation?: number;
            technique_mismatch?: number;
            fabricated_tech?: number;
            inflated_duration?: number;
            inconsistent_metric?: number;
          };
        })
      : null;

  const reviewDetails = details?.review as CoverLetterReviewDetails | undefined;

  return (
    <div className="space-y-3">
      {/* Recommendation header */}
      <Card className={cn("border", config.border)}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 text-muted-foreground" />
              Proofread Result
            </span>
            <Badge
              className={cn(
                config.bg,
                config.color,
                "border-0 text-sm font-semibold",
              )}
            >
              <RecIcon className="mr-1 h-3 w-3" />
              {config.label}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Overall Score</span>
              <span className={cn("font-medium", scoreColor(validation.score))}>
                {validation.score}/100
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted">
              <div
                className={cn(
                  "h-2 rounded-full transition-all",
                  scoreBarColor(validation.score),
                )}
                style={{
                  width: `${Math.min(Math.max(validation.score, 0), 100)}%`,
                }}
              />
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>{validation.word_count} words</span>
              {paragraphCount != null && (
                <span>{paragraphCount} paragraphs</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Dimension scores */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <LayoutTemplate className="h-4 w-4 text-muted-foreground" />
            Quality Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <ScoreBar
              label="Structure"
              score={validation.structure_score}
              icon={LayoutTemplate}
            />
            <ScoreBar
              label="Content"
              score={validation.content_score}
              icon={MessageSquare}
            />
            <ScoreBar
              label="Tone"
              score={validation.tone_score}
              icon={PenTool}
            />
          </div>
        </CardContent>
      </Card>

      {/* Issues */}
      {validation.issues.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Issues to Address
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {validation.issues.map((issue, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-xs text-foreground"
                >
                  <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                  {issueLabel(issue)}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Ungrounded / overclaim review — deterministic resume grounding */}
      {(ungroundedSentences.length > 0 ||
        claimOverclaims.length > 0 ||
        fabricatedTechnologies.length > 0 ||
        inflatedDurationClaims.length > 0 ||
        inconsistentPercentClaims.length > 0) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Review before sending
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {groundingPenalty != null &&
              typeof groundingPenalty.capped_penalty === "number" &&
              groundingPenalty.capped_penalty > 0 && (
                <p className="text-xs text-muted-foreground">
                  Content score deducted {groundingPenalty.capped_penalty} by
                  severity
                  {groundingPenalty.soft_ungrounded
                    ? ` · ${groundingPenalty.soft_ungrounded} soft (−${groundingPenalty.weights?.soft_ungrounded ?? 3} each)`
                    : ""}
                  {groundingPenalty.hard_ungrounded
                    ? ` · ${groundingPenalty.hard_ungrounded} hard overclaim (−${groundingPenalty.weights?.hard_ungrounded ?? 10} each)`
                    : ""}
                  {groundingPenalty.scope_inflation
                    ? ` · ${groundingPenalty.scope_inflation} scope (−${groundingPenalty.weights?.scope_inflation ?? 12} each)`
                    : ""}
                  {groundingPenalty.technique_mismatch
                    ? ` · ${groundingPenalty.technique_mismatch} technique (−${groundingPenalty.weights?.technique_mismatch ?? 10} each)`
                    : ""}
                  {groundingPenalty.fabricated_tech
                    ? ` · ${groundingPenalty.fabricated_tech} fabricated tech (−${groundingPenalty.weights?.fabricated_tech ?? 10} each)`
                    : ""}
                  {groundingPenalty.inflated_duration
                    ? ` · ${groundingPenalty.inflated_duration} inflated duration (−${groundingPenalty.weights?.inflated_duration ?? 10} each)`
                    : ""}
                  {groundingPenalty.inconsistent_metric
                    ? ` · ${groundingPenalty.inconsistent_metric} inconsistent metric (−${groundingPenalty.weights?.inconsistent_metric ?? 10} each)`
                    : ""}
                  . Penalties scale by severity (soft wording vs hard
                  overclaims).
                </p>
              )}
            {fabricatedTechnologies.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  These technologies appear in the letter but are not listed in
                  your Technical Skills. Remove them or add them to your profile
                  before sending.
                </p>
                <ul className="flex flex-wrap gap-1.5">
                  {fabricatedTechnologies.map((tech) => (
                    <li key={`fabricated-tech-${tech}`}>
                      <Badge variant="outline" className="font-normal">
                        {tech}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {inflatedDurationClaims.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  These sentences claim more years of experience than your dated
                  roles (merged, non-overlapping) support.
                </p>
                <ul className="space-y-2">
                  {inflatedDurationClaims.map((item, i) => (
                    <li
                      key={`duration-${i}-${(item.sentence || "").slice(0, 24)}`}
                      className="space-y-1 text-xs text-foreground"
                    >
                      <p className="flex items-start gap-2">
                        <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                        <span>{item.sentence}</span>
                      </p>
                      {(item.flags || []).map((flag) => (
                        <p key={flag} className="pl-3.5 text-muted-foreground">
                          {flag}
                        </p>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {inconsistentPercentClaims.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  These sentences state a percentage gain that does not match
                  the from/to endpoints (absolute points or relative change).
                </p>
                <ul className="space-y-2">
                  {inconsistentPercentClaims.map((item, i) => (
                    <li
                      key={`metric-${i}-${(item.sentence || "").slice(0, 24)}`}
                      className="space-y-1 text-xs text-foreground"
                    >
                      <p className="flex items-start gap-2">
                        <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                        <span>{item.sentence}</span>
                      </p>
                      {(item.flags || []).map((flag) => (
                        <p key={flag} className="pl-3.5 text-muted-foreground">
                          {flag}
                        </p>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {ungroundedSentences.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  These sentences have weak overlap with your resume (or
                  introduce capability claims like deployed / production /
                  launched that are not in your profile).
                </p>
                <ul className="space-y-1.5">
                  {ungroundedSentences.map((sentence, i) => (
                    <li
                      key={`ungrounded-${i}-${sentence.slice(0, 24)}`}
                      className="flex items-start gap-2 text-xs text-foreground"
                    >
                      <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                      {sentence}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {claimOverclaims.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Scope inflation or technique mismatch: a misleading phrase
                  inside an otherwise grounded sentence (for example
                  &quot;leading&quot; when bullets only say Built/Designed, or
                  &quot;retrieval&quot; on a project that does not use it).
                </p>
                <ul className="space-y-2">
                  {claimOverclaims.map((item, i) => (
                    <li
                      key={`claim-${i}-${(item.sentence || "").slice(0, 24)}`}
                      className="space-y-1 text-xs text-foreground"
                    >
                      <p className="flex items-start gap-2">
                        <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                        <span>{item.sentence}</span>
                      </p>
                      {(item.flags || []).map((flag) => (
                        <p key={flag} className="pl-3.5 text-muted-foreground">
                          {flag}
                        </p>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Detail chips */}
      <div className="flex flex-wrap gap-1.5">
        {companyMentioned === true && (
          <Badge variant="outline" className="text-xs text-green-600">
            Company mentioned
          </Badge>
        )}
        {companyMentioned === false && (
          <Badge variant="outline" className="text-xs text-red-600">
            Missing company
          </Badge>
        )}
        {jobTitleMentioned === true && (
          <Badge variant="outline" className="text-xs text-green-600">
            Role mentioned
          </Badge>
        )}
        {jobTitleMentioned === false && (
          <Badge variant="outline" className="text-xs text-red-600">
            Missing role
          </Badge>
        )}
        {hasCallToAction === true && (
          <Badge variant="outline" className="text-xs text-green-600">
            Has closing
          </Badge>
        )}
        {hasCallToAction === false && (
          <Badge variant="outline" className="text-xs text-red-600">
            Missing closing
          </Badge>
        )}
        {referencedProjects.map((project, i) => (
          <Badge key={i} variant="outline" className="text-xs text-primary">
            {project}
          </Badge>
        ))}
      </div>

      {/* LLM feedback */}
      {llmFeedback.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Sparkles className="h-4 w-4 text-primary" />
              AI Feedback
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {llmFeedback.map((feedback, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-xs text-foreground"
                >
                  <span className="mt-0.5 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                  {feedback}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Reviewer feedback */}
      {reviewDetails && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm">
                <PenTool className="h-4 w-4 text-primary" />
                Reviewer Feedback
              </span>
              {reviewDetails.rewrite_count > 0 ? (
                <Badge variant="outline" className="text-xs text-primary">
                  Rewritten once
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="text-xs text-muted-foreground"
                >
                  Original draft
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-foreground">{reviewDetails.critique}</p>
            <div className="flex flex-wrap gap-1.5">
              {reviewDetails.rewrite_needed && (
                <Badge variant="outline" className="text-xs text-amber-600">
                  Rewrite requested
                </Badge>
              )}
              {
                <span className="text-xs text-muted-foreground">
                  Model: {reviewDetails.model_used}
                </span>
              }
              {reviewDetails.review_ms != null && (
                <span className="text-xs text-muted-foreground">
                  Review: {formatDurationMs(reviewDetails.review_ms)}
                </span>
              )}
              {reviewDetails.rewrite_ms != null && (
                <span className="text-xs text-muted-foreground">
                  Rewrite: {formatDurationMs(reviewDetails.rewrite_ms)}
                </span>
              )}
            </div>
            {reviewDetails.error && (
              <p className="text-xs text-red-600">{reviewDetails.error}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* No issues message */}
      {validation.issues.length === 0 &&
        llmFeedback.length === 0 &&
        ungroundedSentences.length === 0 &&
        claimOverclaims.length === 0 &&
        fabricatedTechnologies.length === 0 &&
        inflatedDurationClaims.length === 0 &&
        inconsistentPercentClaims.length === 0 &&
        !reviewDetails && (
          <p className="text-xs text-muted-foreground">
            No issues detected. The cover letter looks good.
          </p>
        )}
    </div>
  );
}

/**
 * Compact recommendation badge for inline use.
 */
export function CoverLetterRecommendationBadge({
  recommendation,
}: {
  recommendation: CoverLetterValidation["recommendation"];
}) {
  const config = RECOMMENDATION_CONFIG[recommendation];
  const RecIcon = config.icon;
  return (
    <Badge
      className={cn(
        "gap-1 border-0 text-xs font-medium",
        config.bg,
        config.color,
      )}
    >
      <RecIcon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}
