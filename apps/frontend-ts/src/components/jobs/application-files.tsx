"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { jobsApi } from "@/lib/api/jobs";
import type { ApplicationFile, JobListing } from "@/lib/types/api";

interface ApplicationFilesProps {
  /** Job whose generated application files are listed. */
  job: JobListing;
}

/**
 * Job detail section: download the generated CV and cover letter (apply pack).
 *
 * Files that the pipeline has not generated are shown as not generated yet.
 * Nothing is shown when the list cannot be loaded.
 *
 * @param props - The job whose files are listed.
 * @returns The file list, or nothing while loading or on error.
 */
export function ApplicationFiles({ job }: ApplicationFilesProps) {
  const [files, setFiles] = useState<ApplicationFile[] | null>(null);

  useEffect(() => {
    let active = true;
    jobsApi
      .getApplicationFiles(job.job_id)
      .then((res) => {
        if (active) setFiles(res.files);
      })
      .catch(() => {
        if (active) setFiles(null);
      });
    return () => {
      active = false;
    };
  }, [job.job_id]);

  if (files === null) return null;

  const anyAvailable = files.some((f) => f.available);

  /**
   * Download one generated file, reporting failure as a toast.
   *
   * @param file - The file to download.
   */
  const download = async (file: ApplicationFile) => {
    try {
      await jobsApi.downloadApplicationFile(
        job.job_id,
        file.kind,
        file.filename,
      );
    } catch {
      toast.error(`Could not download ${file.label}`);
    }
  };

  return (
    <div
      data-testid="application-files"
      className="p-5 space-y-2 border-b border-border"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground">
        Application files
      </p>
      {!anyAvailable ? (
        <p className="text-sm text-muted-foreground">
          No application files yet
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {files.map((file) =>
            file.available ? (
              <Button
                key={file.kind}
                size="sm"
                variant="outline"
                onClick={() => download(file)}
              >
                {`Download ${file.label}`}
              </Button>
            ) : (
              <p
                key={file.kind}
                className="w-full text-xs text-muted-foreground"
              >
                {file.kind === "cover_letter"
                  ? `${file.label}: not generated yet. Letters that need review are on the Cover Letter page.`
                  : `${file.label}: not generated yet`}
              </p>
            ),
          )}
        </div>
      )}
    </div>
  );
}
