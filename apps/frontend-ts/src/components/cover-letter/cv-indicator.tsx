"use client";

import Link from "next/link";
import { Loader2, AlertTriangle, FileUser } from "lucide-react";
import { formatDate } from "@/lib/utils/format";
import type { CoverLetterPage } from "@/lib/hooks/use-cover-letter-page";

/**
 * Show which resume the letter uses.
 *
 * @param props - The component props.
 * @param props.page - The state and actions of the Cover Letter page.
 * @returns The section.
 */
export function CvIndicator({ page }: { page: CoverLetterPage }) {
  const { cv, profile, profileLoading, profileError } = page;
  return (
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
  );
}
