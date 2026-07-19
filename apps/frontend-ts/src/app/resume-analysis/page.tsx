"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Upload, Download } from "lucide-react";
import { profileApi } from "@/lib/api/profile";
import type { ResumeAnalysis } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";
import { PageContainer } from "@/components/layout/PageContainer";

// ── Score ring ────────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-green-500"
      : score >= 60
        ? "text-yellow-500"
        : "text-red-500";
  return (
    <div className="flex flex-col items-center gap-1">
      <div className={cn("text-5xl font-bold", color)}>{score}</div>
      <div className="text-xs text-muted-foreground">/ 100</div>
    </div>
  );
}

// ── Analysis result display ───────────────────────────────────────────────────

function AnalysisDisplay({ analysis }: { analysis: ResumeAnalysis }) {
  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(analysis, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "resume-analysis.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Score header — full width */}
      <Card>
        <CardContent className="flex items-center gap-8 pt-6 pb-5">
          <ScoreRing score={analysis.overall_score} />
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">
              {analysis.analysis_type === "job_specific"
                ? "Job-Specific Analysis"
                : "General Analysis"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
              {analysis.summary}
            </p>
            {analysis.target_alignment_score != null && (
              <p className="mt-2 text-sm">
                Target alignment:{" "}
                <span className="font-semibold">
                  {analysis.target_alignment_score}/100
                </span>
              </p>
            )}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={downloadJson}
            className="shrink-0"
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            Export
          </Button>
        </CardContent>
      </Card>

      {/* Two-column grid for all details */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Strengths */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-700">Strengths</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {(analysis.key_strengths ?? []).map((s, i) => (
                <li key={i} className="flex gap-2 text-sm text-foreground">
                  <span className="shrink-0 text-green-500">✓</span>
                  {s}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Improvements */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-amber-700">
              Areas to Improve
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {(analysis.key_improvements ?? []).map((s, i) => (
                <li key={i} className="flex gap-2 text-sm text-foreground">
                  <span className="shrink-0 text-amber-500">→</span>
                  {s}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Skills assessment */}
        {(analysis.skills_assessment?.length ?? 0) > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Skills Assessment</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 pr-4">Skill</th>
                    <th className="pb-2 pr-4">Proficiency</th>
                    <th className="pb-2 pr-4">Experience</th>
                    <th className="pb-2">Relevant</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {(analysis.skills_assessment ?? []).map((s, i) => (
                    <tr key={i} className="hover:bg-muted">
                      <td className="py-2 pr-4 font-medium text-foreground">
                        {s.skill_name}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {s.proficiency_level}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {s.years_experience != null
                          ? `${s.years_experience}y`
                          : "—"}
                      </td>
                      <td className="py-2">
                        <Badge
                          variant={
                            s.is_industry_relevant ? "default" : "secondary"
                          }
                          className="text-xs"
                        >
                          {s.is_industry_relevant ? "Yes" : "No"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* Skill gaps */}
        {(analysis.skill_gaps?.length ?? 0) > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-red-700">
                Skill Gaps
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {(analysis.skill_gaps ?? []).map((g) => (
                  <Badge
                    key={g}
                    variant="outline"
                    className="border-red-200 text-red-600 text-xs"
                  >
                    {g}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recommendations */}
        {(analysis.resume_improvements?.length ?? 0) > 0 && (
          <Card
            className={
              (analysis.skill_gaps?.length ?? 0) > 0 ? "" : "lg:col-span-2"
            }
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2">
                {(analysis.resume_improvements ?? []).map((r, i) => (
                  <li key={i} className="flex gap-2 text-sm text-foreground">
                    <span className="shrink-0 font-semibold text-blue-600">
                      {i + 1}.
                    </span>
                    {r}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

// ── Upload form ───────────────────────────────────────────────────────────────

function AnalysisForm({ onResult }: { onResult: (r: ResumeAnalysis) => void }) {
  const [jobDescription, setJobDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const analyze = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("No file selected");
      return profileApi.analyze(file, jobDescription || undefined);
    },
    onSuccess: onResult,
    onError: () =>
      toast.error("Analysis failed. Check that the backend is running."),
  });

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors",
          isDragActive
            ? "border-blue-500 bg-blue-50"
            : "border-border bg-muted hover:border-border",
        )}
      >
        <input {...getInputProps()} />
        <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
        {file ? (
          <p className="text-sm font-medium text-blue-600">{file.name}</p>
        ) : (
          <>
            <p className="text-sm font-medium text-foreground">
              Drop your resume here, or click to browse
            </p>
            <p className="mt-1 text-xs text-muted-foreground">PDF or DOCX</p>
          </>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="jd">Job Description (optional)</Label>
        <Textarea
          id="jd"
          rows={5}
          placeholder="Paste the job description to get a tailored gap analysis…"
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
        />
      </div>

      <Button
        onClick={() => analyze.mutate()}
        disabled={!file || analyze.isPending}
        className="w-full"
      >
        {analyze.isPending ? "Analyzing…" : "Analyze Resume"}
      </Button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ResumeAnalysisPage() {
  const [result, setResult] = useState<ResumeAnalysis | null>(null);

  return (
    <PageContainer variant={result ? "wide" : "form"}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Resume Analysis
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            AI-powered feedback on your resume with optional job-specific gap
            analysis.
          </p>
        </div>
        {result && (
          <Button variant="outline" size="sm" onClick={() => setResult(null)}>
            New Analysis
          </Button>
        )}
      </div>

      {result ? (
        <AnalysisDisplay analysis={result} />
      ) : (
        <AnalysisForm onResult={setResult} />
      )}
    </PageContainer>
  );
}
