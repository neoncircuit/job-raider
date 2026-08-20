"use client";

import { Bookmark, BookmarkCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import { SOURCE_COLORS, STATUS_COLORS } from "@/lib/utils/constants";
import type { JobListing } from "@/lib/types/api";

interface JobListItemProps {
  /** Job to display. */
  job: JobListing;
  /** Whether this job is currently selected. */
  isSelected: boolean;
  /** Whether this job is saved/bookmarked. */
  isSaved: boolean;
  /** Whether this job has been marked as applied elsewhere. */
  isAppliedExternally: boolean;
  /** Whether scraper or cross-source match says already applied. */
  isAlreadyTracked?: boolean;
  /** Called when the row is clicked. */
  onClick: () => void;
  /** Called when the save button is clicked. */
  onSave: (e: React.MouseEvent) => void;
}

/**
 * Compact job row shown in the jobs list panel.
 *
 * The row is an actual button so it is keyboard-focusable and screen-reader
 * friendly. The save action is a sibling button layered on top to avoid nested
 * interactive controls.
 */
export function JobListItem({
  job,
  isSelected,
  isSaved,
  isAppliedExternally,
  isAlreadyTracked = false,
  onClick,
  onSave,
}: JobListItemProps) {
  const sourceColor =
    SOURCE_COLORS[job.source.toLowerCase()] ?? "bg-muted text-muted-foreground";
  const showApplied = Boolean(job.already_applied) || isAlreadyTracked;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "absolute inset-0 z-0 w-full rounded border transition-all duration-150 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/70 focus-visible:ring-offset-1",
          isSelected
            ? "border-primary bg-primary/5 shadow-sm"
            : "border-border bg-card hover:border-primary hover:ring-2 hover:ring-primary/40",
        )}
        aria-label={`View ${job.title} at ${job.company}`}
      />

      <div className="relative z-10 p-3 pointer-events-none">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-medium text-foreground text-sm">
              {job.title}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {job.company}
            </p>
          </div>
          <button
            type="button"
            onClick={onSave}
            className={cn(
              "pointer-events-auto shrink-0 rounded border border-transparent p-0.5 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 hover:border-primary hover:ring-2 hover:ring-primary/40",
              isSaved
                ? "text-primary"
                : "text-muted-foreground hover:text-primary",
            )}
            aria-label={isSaved ? "Unsave job" : "Save job"}
          >
            {isSaved ? (
              <BookmarkCheck className="h-4 w-4" />
            ) : (
              <Bookmark className="h-4 w-4" />
            )}
          </button>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          <Badge className={cn("text-[10px] px-1.5 py-0", sourceColor)}>
            {job.source}
          </Badge>
          {job.is_remote && (
            <Badge
              variant="outline"
              className="text-[10px] px-1.5 py-0 border-success/30 bg-success/10 text-success"
            >
              Remote
            </Badge>
          )}
          {isAppliedExternally && !showApplied && (
            <Badge
              className={cn(
                "text-[10px] px-1.5 py-0",
                STATUS_COLORS.applied_elsewhere,
              )}
            >
              Applied Elsewhere
            </Badge>
          )}
          {job.listing_status === "expired" && (
            <Badge className="text-[10px] px-1.5 py-0 bg-destructive text-destructive-foreground">
              Expired
            </Badge>
          )}
          {job.scraped_today && (
            <Badge
              variant="outline"
              className="text-[10px] px-1.5 py-0 border-info/30 bg-info/10 text-info"
            >
              Scraped today
            </Badge>
          )}
          {showApplied && (
            <Badge className="text-[10px] px-1.5 py-0 bg-success text-success-foreground">
              Applied
            </Badge>
          )}
          {job.relevance_score != null && (
            <Badge
              className={cn(
                "text-[10px] px-1.5 py-0",
                job.relevance_score >= 80
                  ? "bg-success text-success-foreground"
                  : job.relevance_score >= 60
                    ? "bg-warning text-warning-foreground"
                    : "bg-destructive text-destructive-foreground",
              )}
            >
              {job.relevance_score}/100
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}
