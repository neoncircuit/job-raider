"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import {
  Upload,
  Briefcase,
  GraduationCap,
  FolderOpen,
  Wrench,
  Award,
  Globe,
  ExternalLink,
  Link,
  MapPin,
  Mail,
  Phone,
  Settings,
  Download,
} from "lucide-react";
import { profileApi } from "@/lib/api/profile";
import { downloadFile } from "@/lib/api/coverLetter";
import type { ResumeParseInfo, UserProfile } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatDatetime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import { ApplicationSettingsModal } from "@/components/application-settings-modal";
import { JobTargetsEditor } from "@/components/job-targets-editor";
import {
  SkillsRadar,
  ExperienceTimeline,
  StrengthAssessment,
} from "@/components/profile-visualizations";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { useDateTimePrefs } from "@/lib/hooks/use-datetime-prefs";
import { writeProfileLocationCache } from "@/lib/datetime-prefs";
import { AiWaitProgress } from "@/components/ai-wait-progress";
import { getApiErrorMessage } from "@/lib/api/client";
// ── Helpers ───────────────────────────────────────────────────────────────────

const PROFICIENCY_COLORS: Record<string, string> = {
  Expert: "bg-primary/10 dark:bg-primary/10 text-primary dark:text-primary",
  Advanced: "bg-info/10 text-info",
  Intermediate: "bg-info/10 dark:bg-info/10 text-info dark:text-info",
  Beginner:
    "bg-muted dark:bg-muted text-muted-foreground dark:text-muted-foreground",
};

const CATEGORY_LABELS: Record<string, string> = {
  programming_language: "Languages",
  framework: "Frameworks",
  tool: "Tools",
  cloud: "Cloud",
  database: "Databases",
  language: "Spoken Languages",
  soft_skill: "Soft Skills",
  domain: "Domain",
  other: "Other",
};

/**
 * Drop leading highlights that duplicate the description summary line.
 *
 * @param description - Summary shown under the entry header.
 * @param highlights - Bullet list under that entry.
 * @returns Highlights with leading duplicates of description removed.
 */
function highlightsWithoutDescriptionDuplicate(
  description: string | null | undefined,
  highlights: string[] | null | undefined,
): string[] {
  const bullets = (highlights ?? []).map((item) => item.trim()).filter(Boolean);
  const summary = (description ?? "").trim();
  if (!summary || bullets.length === 0) {
    return bullets;
  }
  const normalize = (value: string) =>
    value.replace(/\s+/g, " ").trim().toLowerCase();
  const summaryKey = normalize(summary);
  let start = 0;
  while (start < bullets.length && normalize(bullets[start]) === summaryKey) {
    start += 1;
  }
  return bullets.slice(start);
}

/**
 * Return whether a project description is only its technologies list as text.
 *
 * @param description - Project summary prose.
 * @param technologies - Tag list for the same project.
 * @returns True when showing description would duplicate the tag row.
 */
function descriptionDuplicatesTechnologies(
  description: string | null | undefined,
  technologies: string[] | null | undefined,
): boolean {
  const summary = (description ?? "").trim();
  const techs = (technologies ?? []).map((item) => item.trim()).filter(Boolean);
  if (!summary || techs.length === 0) {
    return false;
  }
  const normalize = (value: string) =>
    value.replace(/\s+/g, " ").trim().toLowerCase();
  if (normalize(summary) === normalize(techs.join(", "))) {
    return true;
  }
  const descParts = summary
    .split(/[,|;]+/)
    .map((part) => normalize(part))
    .filter(Boolean)
    .sort();
  const techParts = [...techs.map(normalize)].sort();
  return (
    descParts.length === techParts.length &&
    descParts.every((part, index) => part === techParts[index])
  );
}

/**
 * Format parse duration for display (ms or seconds).
 *
 * @param durationMs - Elapsed parse time in milliseconds.
 * @returns Human-readable duration string, or null when missing.
 */
function formatParseDuration(
  durationMs: number | null | undefined,
): string | null {
  if (durationMs == null || Number.isNaN(durationMs) || durationMs < 0) {
    return null;
  }
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }
  return `${(durationMs / 1000).toFixed(1)} s`;
}

/**
 * Build a short status line describing the last resume parse.
 *
 * @param info - Resume parse metadata from the profile API.
 * @returns Display line, or null when no useful fields exist.
 */
function formatResumeParseSummary(
  info: ResumeParseInfo | null | undefined,
): string | null {
  if (!info) {
    return null;
  }
  const parts: string[] = [];
  if (info.parsed_at) {
    const when = formatDatetime(info.parsed_at);
    if (when && when !== "N/A") {
      parts.push(`Parsed ${when}`);
    }
  }
  const duration = formatParseDuration(info.duration_ms);
  if (duration) {
    parts.push(duration);
  }
  const modelLabel =
    info.method === "rule_based"
      ? "rule-based fallback"
      : [info.provider, info.model].filter(Boolean).join(" / ") || info.model;
  if (modelLabel) {
    parts.push(modelLabel);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

// ── Upload dropzone ───────────────────────────────────────────────────────────

function ResumeDropzone({ onUploaded }: { onUploaded: () => void }) {
  const qc = useQueryClient();
  // Subscribe so toast formatting refreshes if prefs change mid-session.
  useDateTimePrefs();

  const upload = useMutation({
    mutationFn: profileApi.upload,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      const summary = formatResumeParseSummary(result.resume_parse);
      toast.success(
        summary
          ? `Resume parsed · ${summary.replace(/^Parsed\s+/i, "")}`
          : "Resume uploaded and parsed.",
      );
      onUploaded();
    },
    onError: () => toast.error("Upload failed. Check the file format."),
  });

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) upload.mutate(accepted[0]);
    },
    [upload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
    disabled: upload.isPending,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors",
        upload.isPending ? "cursor-wait" : "cursor-pointer",
        isDragActive
          ? "border-primary bg-primary/10"
          : "border-border dark:border-border bg-muted dark:bg-muted hover:border-border dark:hover:border-muted-foreground/50",
      )}
    >
      <input {...getInputProps()} />
      <Upload className="mb-3 h-8 w-8 text-muted-foreground dark:text-muted-foreground" />
      {upload.isPending ? (
        <AiWaitProgress
          className="max-w-sm"
          label="Parsing resume…"
          hint="Extracting profile fields. This can take 30–60 seconds."
        />
      ) : (
        <>
          <p className="text-sm font-medium text-foreground dark:text-muted-foreground">
            Drop your resume here, or click to browse
          </p>
          <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
            PDF or DOCX, max 10 MB
          </p>
        </>
      )}
    </div>
  );
}

// ── Profile display ───────────────────────────────────────────────────────────

function ProfileDisplay({ profile }: { profile: UserProfile }) {
  const {
    contact_info: c,
    summary,
    core_skills,
    skills,
    work_experience,
    education,
    projects,
    certifications,
    languages,
    target_job,
    years_of_experience,
    resume_parse,
  } = profile;
  // Subscribe so date labels refresh when Appearance prefs change.
  useDateTimePrefs();
  useEffect(() => {
    writeProfileLocationCache(c.location);
  }, [c.location]);
  const parseSummary = formatResumeParseSummary(resume_parse);

  // Group skills by category
  const skillsByCategory = skills.reduce<Record<string, typeof skills>>(
    (acc, s) => {
      const cat = s.category ?? "other";
      (acc[cat] ??= []).push(s);
      return acc;
    },
    {},
  );

  return (
    <div className="space-y-3">
      {/* ── Hero header (open section, not a card) ── */}
      <section className="space-y-3 border-b border-border pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground">
              {c.name || "—"}
            </h2>
            {parseSummary && (
              <p className="text-xs text-muted-foreground">{parseSummary}</p>
            )}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {c.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {c.location}
                </span>
              )}
              {years_of_experience != null && years_of_experience > 0 && (
                <span className="flex items-center gap-1">
                  <Briefcase className="h-3.5 w-3.5" />
                  {years_of_experience} yrs exp
                </span>
              )}
              {c.email && (
                <span className="flex items-center gap-1">
                  <Mail className="h-3.5 w-3.5" />
                  {c.email}
                </span>
              )}
              {c.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-3.5 w-3.5" />
                  {c.phone}
                </span>
              )}
            </div>
            {(c.linkedin_url ||
              c.github_url ||
              c.portfolio_url ||
              c.website_url) && (
              <div className="flex flex-wrap gap-3 pt-1">
                {c.linkedin_url && (
                  <a
                    href={c.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    <Link className="h-3 w-3" /> LinkedIn
                  </a>
                )}
                {c.github_url && (
                  <a
                    href={c.github_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                  >
                    <Link className="h-3 w-3" /> GitHub
                  </a>
                )}
                {(c.portfolio_url || c.website_url) && (
                  <a
                    href={c.portfolio_url ?? c.website_url ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                  >
                    <Globe className="h-3 w-3" /> Portfolio
                  </a>
                )}
              </div>
            )}
          </div>
        </div>

        {summary && (
          <p className="text-sm italic leading-relaxed text-muted-foreground">
            {summary}
          </p>
        )}
      </section>

      {/* ── Visualizations ── */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <SkillsRadar
            skills={skills}
            core_skills={core_skills}
            work_experience={work_experience}
            projects={projects}
          />
        </div>
        <div className="lg:col-span-1">
          <ExperienceTimeline experience={work_experience} />
        </div>
        <div className="lg:col-span-1">
          <StrengthAssessment profile={profile} />
        </div>
      </div>

      {/* ── Two-column grid ── */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {/* ── Left column (narrow) — skills, targets, certifications, languages ── */}
        <div className="space-y-3">
          {/* Skills */}
          {skills.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Wrench className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
                  Skills
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(core_skills?.length ?? 0) > 0 && (
                  <div>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground dark:text-muted-foreground">
                      Core
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {core_skills!.map((s) => (
                        <Badge
                          key={s}
                          className="bg-primary dark:bg-primary text-white dark:text-primary-foreground text-xs"
                        >
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {Object.entries(skillsByCategory).map(([cat, catSkills]) => (
                  <div key={cat}>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground dark:text-muted-foreground">
                      {CATEGORY_LABELS[cat] ?? cat}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {catSkills.map((s) => (
                        <span
                          key={s.name}
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                            s.proficiency
                              ? (PROFICIENCY_COLORS[s.proficiency] ??
                                  "bg-muted dark:bg-muted text-foreground dark:text-muted-foreground")
                              : "bg-muted dark:bg-muted text-foreground dark:text-muted-foreground",
                          )}
                        >
                          {s.name}
                          {s.years_of_experience ? (
                            <span className="opacity-60">
                              · {s.years_of_experience}y
                            </span>
                          ) : null}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Languages */}
          {(languages?.length ?? 0) > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Globe className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
                  Languages
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {languages!.map((l) => (
                    <Badge key={l} variant="secondary" className="text-xs">
                      {l}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Target Job — experimental editable prefs */}
          <JobTargetsEditor
            key={JSON.stringify(target_job ?? {})}
            targetJob={target_job}
          />

          {/* Certifications */}
          {(certifications?.length ?? 0) > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Award className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
                  Certifications
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {certifications!.map((cert, i) => (
                  <div key={i}>
                    <p className="text-sm font-medium text-foreground dark:text-foreground">
                      {cert.name}
                    </p>
                    <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                      {cert.issuer}
                    </p>
                    <div className="mt-0.5 flex gap-2 text-xs text-muted-foreground dark:text-muted-foreground">
                      {cert.issue_date && (
                        <span>Issued {formatDate(cert.issue_date)}</span>
                      )}
                      {cert.expiration_date && (
                        <span>· Exp {formatDate(cert.expiration_date)}</span>
                      )}
                    </div>
                    {cert.credential_id && (
                      <p className="mt-0.5 text-xs text-muted-foreground dark:text-muted-foreground">
                        ID: {cert.credential_id}
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Education */}
          {education.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <GraduationCap className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
                  Education
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {education.map((e, i) => (
                  <div key={i} className={cn(i > 0 && "border-t pt-3")}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-foreground dark:text-foreground">
                          {e.degree}
                        </p>
                        {e.field_of_study && (
                          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                            {e.field_of_study}
                          </p>
                        )}
                        <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                          {e.institution}
                        </p>
                      </div>
                      <div className="shrink-0 text-right text-xs text-muted-foreground dark:text-muted-foreground">
                        {e.graduation_date && (
                          <p>Graduated {formatDate(e.graduation_date)}</p>
                        )}
                        {e.gpa != null && <p>GPA {e.gpa.toFixed(2)}</p>}
                      </div>
                    </div>
                    {(e.honors?.length ?? 0) > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {e.honors.map((h) => (
                          <Badge
                            key={h}
                            className="bg-amber-100 dark:bg-warning/10 text-amber-800 dark:text-warning text-xs"
                          >
                            {h}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {(e.coursework?.length ?? 0) > 0 && (
                      <p className="mt-1.5 text-xs text-muted-foreground dark:text-muted-foreground">
                        <span className="font-medium">Coursework:</span>{" "}
                        {e.coursework!.join(", ")}
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* ── Right column (wide) — experience, projects, education ── */}
        <div className="space-y-3 lg:col-span-2">
          {/* Experience */}
          {work_experience.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Briefcase className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
                  Experience
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {work_experience.map((e, i) => (
                  <div key={i} className={cn("pl-4", i > 0 && "border-t pt-5")}>
                    <div className="border-l-2 border-primary/40 pl-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-foreground dark:text-foreground">
                            {e.title}
                          </p>
                          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                            {e.company}
                            {e.location ? ` · ${e.location}` : ""}
                          </p>
                        </div>
                        <p className="shrink-0 text-xs text-muted-foreground dark:text-muted-foreground">
                          {e.start_date ? formatDate(e.start_date) : "?"} —{" "}
                          {e.current
                            ? "Present"
                            : e.end_date
                              ? formatDate(e.end_date)
                              : "?"}
                        </p>
                      </div>
                      {e.description && (
                        <p className="mt-2 text-sm text-muted-foreground dark:text-muted-foreground leading-relaxed">
                          {e.description}
                        </p>
                      )}
                      {(() => {
                        const bullets = highlightsWithoutDescriptionDuplicate(
                          e.description,
                          e.highlights,
                        );
                        if (bullets.length === 0) {
                          return null;
                        }
                        return (
                          <ul className="mt-2 space-y-1">
                            {bullets.map((h, j) => (
                              <li
                                key={j}
                                className="flex gap-2 text-sm text-foreground dark:text-muted-foreground"
                              >
                                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                                {h}
                              </li>
                            ))}
                          </ul>
                        );
                      })()}
                      {(e.technologies?.length ?? 0) > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {e.technologies.map((t) => (
                            <Badge
                              key={t}
                              variant="outline"
                              className="text-xs text-muted-foreground dark:text-muted-foreground"
                            >
                              {t}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Projects */}
          {projects.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <FolderOpen className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
                  Projects
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {projects.map((p, i) => (
                  <div key={i} className={cn("pl-4", i > 0 && "border-t pt-5")}>
                    <div className="border-l-2 border-primary/40 dark:border-primary pl-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-foreground dark:text-foreground">
                            {p.name}
                          </p>
                          {p.role && (
                            <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                              {p.role}
                            </p>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {(p.start_date || p.end_date) && (
                            <span className="text-xs text-muted-foreground dark:text-muted-foreground">
                              {p.start_date ? formatDate(p.start_date) : ""}
                              {p.end_date
                                ? ` — ${formatDate(p.end_date)}`
                                : " — Present"}
                            </span>
                          )}
                          {p.url && (
                            <a
                              href={p.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-muted-foreground dark:text-muted-foreground hover:text-primary"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          )}
                        </div>
                      </div>
                      {p.description &&
                        !descriptionDuplicatesTechnologies(
                          p.description,
                          p.technologies,
                        ) && (
                          <p className="mt-1.5 text-sm text-muted-foreground dark:text-muted-foreground leading-relaxed">
                            {p.description}
                          </p>
                        )}
                      {(() => {
                        const displayDescription =
                          p.description &&
                          !descriptionDuplicatesTechnologies(
                            p.description,
                            p.technologies,
                          )
                            ? p.description
                            : "";
                        const bullets = highlightsWithoutDescriptionDuplicate(
                          displayDescription,
                          p.highlights,
                        ).filter(
                          (bullet) =>
                            !descriptionDuplicatesTechnologies(
                              bullet,
                              p.technologies,
                            ),
                        );
                        if (bullets.length === 0) {
                          return null;
                        }
                        return (
                          <ul className="mt-2 space-y-1">
                            {bullets.map((h, j) => (
                              <li
                                key={j}
                                className="flex gap-2 text-sm text-foreground dark:text-muted-foreground"
                              >
                                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary dark:bg-primary" />
                                {h}
                              </li>
                            ))}
                          </ul>
                        );
                      })()}
                      {(p.technologies?.length ?? 0) > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {p.technologies.map((t) => (
                            <Badge
                              key={t}
                              variant="outline"
                              className="text-xs text-muted-foreground dark:text-muted-foreground"
                            >
                              {t}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

/**
 * Profile page: parsed resume display, upload, and application settings.
 *
 * Always renders PageContainer + PageHeader so loading does not drop chrome.
 *
 * @returns Profile page content.
 */
export default function ProfilePage() {
  const [showUpload, setShowUpload] = useState(false);
  const [showAppSettings, setShowAppSettings] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
    staleTime: 60_000,
    retry: false,
  });

  const hasProfile = !!data?.contact_info?.name;

  /**
   * Download the active profile as a structured summary PDF.
   *
   * @returns Promise that resolves when the browser download is triggered.
   */
  const handleDownloadPdf = async () => {
    setPdfDownloading(true);
    try {
      const res = await profileApi.exportPdf();
      await downloadFile(res, "profile_summary.pdf");
      toast.success("Profile PDF downloaded");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not download profile PDF."));
    } finally {
      setPdfDownloading(false);
    }
  };

  return (
    <PageContainer variant="wide">
      <PageHeader
        title="Profile"
        subtitle="Your parsed resume and target preferences."
        actions={
          <>
            {hasProfile && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleDownloadPdf()}
                  disabled={pdfDownloading}
                >
                  <Download className="h-3.5 w-3.5" />
                  {pdfDownloading ? "Downloading…" : "Download PDF"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAppSettings(true)}
                >
                  <Settings className="h-3.5 w-3.5" />
                  Application Settings
                </Button>
              </>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowUpload((v) => !v)}
            >
              {showUpload
                ? "Cancel"
                : hasProfile
                  ? "Re-upload Resume"
                  : "Upload Resume"}
            </Button>
          </>
        }
      />

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading profile…</p>
      )}

      {!isLoading && (showUpload || !hasProfile) && (
        <ResumeDropzone onUploaded={() => setShowUpload(false)} />
      )}

      {isError && !hasProfile && !isLoading && (
        <p className="text-sm text-muted-foreground">
          No profile yet. Upload your resume to get started.
        </p>
      )}

      {data && hasProfile && (
        <>
          <ProfileDisplay profile={data} />
          {showAppSettings && (
            <ApplicationSettingsModal
              profile={data}
              open={showAppSettings}
              onClose={() => setShowAppSettings(false)}
            />
          )}
        </>
      )}
    </PageContainer>
  );
}
