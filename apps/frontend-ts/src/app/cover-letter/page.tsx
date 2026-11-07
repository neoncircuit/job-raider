"use client";

import { Mail } from "lucide-react";
import { CoverLetterForm } from "@/components/cover-letter/cover-letter-form";
import { CoverLetterResult } from "@/components/cover-letter/cover-letter-result";
import { CvIndicator } from "@/components/cover-letter/cv-indicator";
import { JobFitPanel } from "@/components/cover-letter/job-fit-panel";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { useCoverLetterPage } from "@/lib/hooks/use-cover-letter-page";

/**
 * Dedicated Cover Letter tab for the "other" category of jobs discovered
 * outside the platform's scrapers. Paste a job description, generate a
 * tailored cover letter using the local model, and export it as DOCX/PDF.
 */
export default function CoverLetterPage() {
  const page = useCoverLetterPage();

  return (
    <PageContainer variant="full-bleed">
      <PageHeader
        title="Cover Letter"
        subtitle="Paste a job description and generate a tailored, proofread cover letter."
        icon={<Mail className="h-6 w-6 text-primary" />}
      />

      {/* Active CV indicator: confirms which resume is being referenced. */}
      <CvIndicator page={page} />

      <div className="grid gap-6 lg:grid-cols-12">
        <CoverLetterForm page={page} />
        <JobFitPanel page={page} />
        <CoverLetterResult page={page} />
      </div>
    </PageContainer>
  );
}
