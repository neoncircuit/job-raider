"use client";

import { useState } from "react";
import {
  ExternalLink,
  MapPin,
  Building2,
  Clock,
  FileText,
  Copy,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { JobClassificationDisplay } from "@/components/job-classification";
import {
  TrustAnalysisDisplay,
  TrustTierBadge,
} from "@/components/trust-analysis";
import { CoverLetterValidationDisplay } from "@/components/cover-letter-validation";
import { ScoreExplanationDisplay } from "@/components/score-explanation";
import { cn } from "@/lib/utils/cn";
import { formatDate, formatSalaryRange } from "@/lib/utils/format";
import { JobDescriptionBody } from "@/components/jobs/job-description-body";
import { SOURCE_COLORS } from "@/lib/utils/constants";
import { toast } from "sonner";
import type { JobListing } from "@/lib/types/api";
import {
  useClassifyJob,
  useAnalyzeTrust,
  useGenerateCoverLetter,
  useExplainJobFit,
  useCachedClassification,
  useCachedTrustAnalysis,
  useCachedCoverLetter,
  useCachedExplainFit,
} from "@/lib/hooks/use-jobs";

interface JobDetailProps {
  /** Job to display. */
  job: JobListing;
  /** Whether this job is saved/bookmarked. */
  isSaved: boolean;
  /** Whether this job has been marked as applied elsewhere. */
  isAppliedExternally: boolean;
  /** Called when the save button is clicked. */
  onSave: () => void;
  /** Called when auto-apply is triggered. */
  onApply: () => void;
  /** Called when marking the job as applied externally. */
  onMarkAppliedExternally: () => void;
}

/**
 * Detailed job panel with analysis, trust, cover-letter, and apply actions.
 */
export function JobDetail({
  job,
  isSaved,
  isAppliedExternally,
  onSave,
  onApply,
  onMarkAppliedExternally,
}: JobDetailProps) {
  const [deepCheck, setDeepCheck] = useState(false);

  const classify = useClassifyJob();
  const analyzeTrust = useAnalyzeTrust();
  const generateCoverLetter = useGenerateCoverLetter();
  const explainFit = useExplainJobFit();

  const cachedClassification = useCachedClassification(job.job_id);
  const cachedTrust = useCachedTrustAnalysis(job.job_id);
  const cachedCoverLetter = useCachedCoverLetter(job.job_id, deepCheck);
  const cachedExplainFit = useCachedExplainFit(job.job_id);

  const classification =
    cachedClassification.data ?? job.classification ?? null;
  const trustAnalysis = cachedTrust.data ?? job.trust_analysis ?? null;
  const coverLetterData = cachedCoverLetter.data;

  const sourceColor =
    SOURCE_COLORS[job.source.toLowerCase()] ?? "bg-muted text-muted-foreground";

  const handleCopyLink = () => {
    if (!job.source_url) return;
    navigator.clipboard.writeText(job.source_url);
    toast.success("Link copied to clipboard");
  };

  return (
    <div className="flex flex-col h-full rounded-lg border bg-card">
      {/* Fixed header section */}
      <div className="p-5 space-y-4 border-b border-border/50">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-foreground truncate">
              {job.title}
            </h2>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                {job.company}
              </span>
              {job.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {job.location}
                </span>
              )}
              {job.posted_date && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {formatDate(job.posted_date)}
                </span>
              )}
            </div>
          </div>
          {job.source_url && (
            <a
              href={job.source_url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open ${job.title} job posting (opens in new tab)`}
              className="shrink-0 text-primary hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>

        {/* Salary */}
        {job.salary_range && (
          <p className="text-sm font-medium text-success">
            {formatSalaryRange(job.salary_range)}
          </p>
        )}

        {/* Job metadata badges */}
        <div className="flex flex-wrap gap-2">
          <Badge className={cn("text-xs", sourceColor)}>{job.source}</Badge>

          {job.already_applied && (
            <Badge className="text-xs bg-success text-success-foreground">
              Applied
            </Badge>
          )}

          {job.listing_status === "expired" && (
            <Badge className="text-xs bg-destructive text-destructive-foreground">
              Expired
            </Badge>
          )}

          {job.scraped_today && (
            <Badge
              variant="outline"
              className="text-xs border-info/30 bg-info/10 text-info"
            >
              Scraped today
            </Badge>
          )}

          {job.work_mode && job.work_mode !== "On-site" && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                job.work_mode === "Remote"
                  ? "border-success/30 bg-success/10 text-success"
                  : job.work_mode === "Hybrid"
                    ? "border-info/30 bg-info/10 text-info"
                    : "border-border text-muted-foreground",
              )}
            >
              {job.work_mode}
            </Badge>
          )}

          {job.job_type && job.job_type !== "Full-time" && (
            <Badge
              variant="outline"
              className="text-xs border-secondary bg-secondary text-secondary-foreground"
            >
              {job.job_type}
            </Badge>
          )}

          {job.experience_level && job.experience_level !== "Not Specified" && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                job.experience_level === "Internship"
                  ? "border-warning/30 bg-warning/10 text-warning"
                  : job.experience_level === "Entry Level"
                    ? "border-info/30 bg-info/10 text-info"
                    : job.experience_level === "Mid Level"
                      ? "border-primary/30 bg-primary/10 text-primary"
                      : job.experience_level === "Senior"
                        ? "border-secondary bg-secondary text-secondary-foreground"
                        : job.experience_level === "Lead"
                          ? "border-muted-foreground/30 bg-muted text-muted-foreground"
                          : "border-border text-muted-foreground",
              )}
            >
              {job.experience_level}
            </Badge>
          )}

          {trustAnalysis && <TrustTierBadge tier={trustAnalysis.tier} />}
          {!trustAnalysis && job.scam_score != null && job.scam_score > 0.5 && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                job.scam_score > 0.7
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-warning/30 bg-warning/10 text-warning",
              )}
            >
              {job.scam_score > 0.7 ? "High Risk" : "Review"}
            </Badge>
          )}
        </div>

        {job.relevance_score != null && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Relevance Score
            </p>
            <Badge
              className={cn(
                "text-sm px-2 py-1",
                job.relevance_score >= 80
                  ? "bg-success text-success-foreground"
                  : job.relevance_score >= 60
                    ? "bg-warning text-warning-foreground"
                    : "bg-destructive text-destructive-foreground",
              )}
            >
              {job.relevance_score}/100
            </Badge>
          </div>
        )}
      </div>

      {/* Scrollable content section */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {/* Skills */}
        {(job.skills?.length ?? 0) > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Skills
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(job.skills ?? []).slice(0, 12).map((s) => (
                <Badge
                  key={s.name}
                  variant={s.is_required ? "default" : "secondary"}
                  className="text-xs"
                >
                  {s.name}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* LLM-based Classification */}
        {classification && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
              Job Analysis
            </p>
            <JobClassificationDisplay classification={classification} />
          </div>
        )}

        {/* Trust Analysis */}
        {trustAnalysis && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
              Trust Analysis
            </p>
            <TrustAnalysisDisplay analysis={trustAnalysis} />
          </div>
        )}

        {/* Description */}
        {job.description?.trim() ? (
          <div className="flex-1 overflow-y-auto">
            <p className="text-xs font-semibold uppercase tracking-wide text-foreground mb-4 border-b border-border pb-2">
              Job Description
            </p>
            <JobDescriptionBody markdown={job.description} />
          </div>
        ) : (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-foreground mb-2 border-b border-border pb-2">
              Job Description
            </p>
            <p className="text-sm text-muted-foreground">
              No description was captured for this listing
              {job.source_url ? (
                <>
                  {" "}
                  —{" "}
                  <a
                    href={job.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline underline-offset-2 text-foreground"
                  >
                    open the original posting
                  </a>
                </>
              ) : null}
              .
            </p>
          </div>
        )}
      </div>

      {/* Fixed footer with actions */}
      <div className="p-4 border-t bg-muted/50 space-y-3">
        <div className="flex gap-2">
          {job.already_applied ? (
            <Button size="sm" disabled className="flex-1" variant="secondary">
              Applied
            </Button>
          ) : job.apply_method === "external_site" && job.source_url ? (
            <div className="flex gap-2 flex-1">
              <a
                href={job.source_url}
                target="_blank"
                rel="noreferrer"
                className="flex-1"
              >
                <Button size="sm" className="w-full">
                  Apply on{" "}
                  {job.source === "jsearch"
                    ? "Job Board"
                    : job.source === "mycareersfuture"
                      ? "MyCareersFuture"
                      : job.source === "jobstreet"
                        ? "JobStreet"
                        : job.source}
                </Button>
              </a>
              <Button size="sm" variant="outline" onClick={handleCopyLink}>
                Copy Link
              </Button>
            </div>
          ) : (
            <Button size="sm" onClick={onApply} className="flex-1">
              Simulate Apply
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={onSave}>
            {isSaved ? "Unsave" : "Save"}
          </Button>
          <Button
            size="sm"
            variant={isAppliedExternally ? "secondary" : "outline"}
            onClick={onMarkAppliedExternally}
            disabled={isAppliedExternally}
          >
            {isAppliedExternally ? "Applied Elsewhere" : "Applied Elsewhere?"}
          </Button>
        </div>

        {!classification && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => classify.mutate({ id: job.job_id, job })}
            disabled={classify.isPending}
            className="w-full"
          >
            {classify.isPending ? "Analyzing..." : "Analyze with AI"}
          </Button>
        )}

        {!trustAnalysis && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => analyzeTrust.mutate({ id: job.job_id, job })}
            disabled={analyzeTrust.isPending}
            className="w-full"
          >
            {analyzeTrust.isPending ? "Analyzing Trust..." : "Analyze Trust"}
          </Button>
        )}

        {job.relevance_score != null && !cachedExplainFit.data && (
          <div className="space-y-1.5">
            <Button
              size="sm"
              variant="outline"
              onClick={() => explainFit.mutate({ id: job.job_id, job })}
              disabled={
                explainFit.isPending || (job.description?.length ?? 0) < 50
              }
              className="w-full"
            >
              {explainFit.isPending ? "Explaining..." : "Explain This Match"}
            </Button>
            {(job.description?.length ?? 0) < 50 && (
              <p className="text-xs text-muted-foreground text-center">
                Job description needs at least 50 characters to explain.
              </p>
            )}
          </div>
        )}

        {cachedExplainFit.data && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Why This Match
            </p>
            <ScoreExplanationDisplay explanation={cachedExplainFit.data} />
          </div>
        )}

        {coverLetterData ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Cover Letter
              </p>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-xs"
                onClick={() => {
                  navigator.clipboard.writeText(coverLetterData.content);
                  toast.success("Cover letter copied to clipboard");
                }}
              >
                <Copy className="mr-1 h-3 w-3" />
                Copy
              </Button>
            </div>
            <div className="rounded-md border bg-card p-3 text-sm text-card-foreground whitespace-pre-line max-h-60 overflow-y-auto">
              {coverLetterData.content}
            </div>
            {coverLetterData.validation && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                  Proofread
                </p>
                <CoverLetterValidationDisplay
                  validation={coverLetterData.validation}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Switch
                  id={`deep-check-${job.job_id}`}
                  checked={deepCheck}
                  onCheckedChange={setDeepCheck}
                />
                <Label
                  htmlFor={`deep-check-${job.job_id}`}
                  className="cursor-pointer text-xs text-muted-foreground"
                >
                  Deep check (LLM)
                </Label>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                generateCoverLetter.mutate({
                  id: job.job_id,
                  job,
                  deep: deepCheck,
                })
              }
              disabled={generateCoverLetter.isPending}
              className="w-full"
            >
              <FileText className="mr-1.5 h-3.5 w-3.5" />
              {generateCoverLetter.isPending
                ? "Generating..."
                : "Generate Cover Letter"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
