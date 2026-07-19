"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { UserProfile, DISCResult } from "@/lib/types/api";
import {
  BarChart3,
  TrendingUp,
  Award,
  Target,
  Zap,
  Shield,
  Lightbulb,
  Briefcase,
  Rocket,
  Sparkles,
} from "lucide-react";
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils/cn";
import { DISCAssessment } from "./disc-assessment";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SkillScore {
  category: string;
  score: number;
  count: number;
}

interface DISCProfile {
  dominance: number;
  influence: number;
  steadiness: number;
  conscientiousness: number;
}

// ── Skills Radar Chart ───────────────────────────────────────────────────────

interface SkillsRadarProps {
  skills: UserProfile["skills"];
}

export function SkillsRadar({ skills }: SkillsRadarProps) {
  // Check how many skills have proficiency data
  const skillsWithProficiency = skills.filter((s) => s.proficiency).length;

  // Calculate scores by category using available data
  const categoryScores = skills.reduce<
    Record<string, { total: number; count: number; hasExp: boolean }>
  >((acc, skill) => {
    const cat = skill.category ?? "other";
    if (!acc[cat]) acc[cat] = { total: 0, count: 0, hasExp: false };

    let score = 0;

    // If we have proficiency data, use it
    if (skill.proficiency) {
      switch (skill.proficiency) {
        case "Expert":
          score = 95;
          break;
        case "Advanced":
          score = 80;
          break;
        case "Intermediate":
          score = 60;
          break;
        case "Beginner":
          score = 40;
          break;
        default:
          score = 50;
      }
      // Boost by years of experience
      score += Math.min((skill.years_of_experience || 0) * 5, 20);
    } else {
      // No proficiency data - estimate from years of experience
      const years = skill.years_of_experience || 0;
      if (years >= 5) score = 85;
      else if (years >= 3) score = 70;
      else if (years >= 1) score = 55;
      else score = 45; // New skill
    }

    // Mark if any skill in this category has experience data
    if (skill.years_of_experience && skill.years_of_experience > 0) {
      acc[cat].hasExp = true;
    }

    acc[cat].total += score;
    acc[cat].count += 1;
    return acc;
  }, {});

  const data: SkillScore[] = Object.entries(categoryScores)
    .map(([cat, { total, count }]) => {
      const avgScore = Math.min(100, Math.round(total / count));
      const label = cat
        .replace(/_/g, " ")
        .replace(/\b\w/g, (l) => l.toUpperCase());
      return {
        category: label,
        score: avgScore,
        count,
      };
    })
    .sort((a, b) => b.score - a.score);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <BarChart3 className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
            Skills Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
            No skills data available
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <BarChart3 className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
          Skills Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Scoring explanation */}
          <div className="rounded-md bg-blue-50 dark:bg-info/10 px-3 py-2 text-xs text-blue-800 dark:text-info">
            <p className="font-medium">How scores are calculated:</p>
            <ul className="mt-1 ml-4 list-disc space-y-0.5">
              <li>
                With proficiency: Expert=95%, Advanced=80%, Intermediate=60%,
                Beginner=40%
              </li>
              <li>Without proficiency: Based on years of experience</li>
              <li>5+ yrs=85%, 3+ yrs=70%, 1+ yrs=55%, 0 yrs=45%</li>
            </ul>
          </div>

          {/* Note about proficiency levels */}
          {skillsWithProficiency === 0 && (
            <div className="rounded-md bg-amber-50 dark:bg-warning/10 px-3 py-2 text-xs text-amber-800 dark:text-warning">
              <span className="font-medium">Note:</span> Your resume
              doesn&apos;t include proficiency levels. Scores are based on years
              of experience. Add proficiency levels for more accurate results.
            </div>
          )}

          {/* Radar Chart */}
          <div className="flex justify-center">
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={data.slice(0, 6)}>
                <PolarGrid stroke="var(--chart-grid)" />
                <PolarAngleAxis
                  dataKey="category"
                  tick={{ fontSize: 10, fill: "var(--chart-axis)" }}
                />
                <Radar
                  name="Skill Level"
                  dataKey="score"
                  stroke="var(--chart-radar-stroke)"
                  fill="var(--chart-radar-fill)"
                  fillOpacity={0.3}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 gap-2">
            {data.map((item) => (
              <div
                key={item.category}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-muted-foreground dark:text-muted-foreground">
                  {item.category}
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-foreground dark:text-foreground">
                    {item.score}%
                  </span>
                  <span className="text-muted-foreground dark:text-muted-foreground">
                    ({item.count})
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Experience Timeline ───────────────────────────────────────────────────────

interface ExperienceTimelineProps {
  experience: UserProfile["work_experience"];
}

export function ExperienceTimeline({ experience }: ExperienceTimelineProps) {
  if (!experience || experience.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <TrendingUp className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
            Career Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[180px] items-center justify-center text-center">
            <div>
              <Sparkles className="mx-auto h-8 w-8 text-purple-400 dark:text-primary mb-2" />
              <p className="text-sm font-medium text-foreground dark:text-muted-foreground">
                Starting Your Journey
              </p>
              <p className="text-xs text-muted-foreground dark:text-muted-foreground mt-1">
                Add experience to build your timeline
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Calculate total months per year
  const yearData = experience.reduce<Record<number, number>>((acc, exp) => {
    if (!exp.start_date) return acc;
    const startDate = new Date(exp.start_date);
    const startYear = startDate.getFullYear();
    const end = exp.end_date ? new Date(exp.end_date) : new Date();
    const endYear = end.getFullYear();

    for (let year = startYear; year <= endYear; year++) {
      const monthsInYear =
        year === startYear && year === endYear
          ? end.getMonth() - startDate.getMonth() + 1
          : year === startYear
            ? 12 - startDate.getMonth()
            : year === endYear
              ? end.getMonth() + 1
              : 12;

      acc[year] = (acc[year] || 0) + monthsInYear;
    }
    return acc;
  }, {});

  const data = Object.entries(yearData)
    .map(([year, months]) => ({
      year: parseInt(year),
      months: Math.round(months),
      years: parseFloat((months / 12).toFixed(1)),
    }))
    .sort((a, b) => a.year - b.year);

  const maxYears = Math.max(...data.map((d) => d.years));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <TrendingUp className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
          Career Timeline
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} layout="vertical">
            <XAxis type="number" domain={[0, maxYears * 1.1]} hide />
            <YAxis
              type="category"
              dataKey="year"
              tick={{ fontSize: 11, fill: "var(--chart-axis)" }}
              width={40}
            />
            <Tooltip
              cursor={{ fill: "var(--chart-cursor)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const data = payload[0].payload;
                return (
                  <div className="rounded-lg border bg-popover text-popover-foreground border-border p-2 shadow-lg">
                    <p className="text-sm font-medium">{data.year}</p>
                    <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                      {data.years} years experience
                    </p>
                  </div>
                );
              }}
            />
            <Bar
              dataKey="years"
              fill="var(--chart-timeline-fill)"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-2 text-center text-xs text-muted-foreground dark:text-muted-foreground">
          Years of professional experience by year
        </p>
      </CardContent>
    </Card>
  );
}

// ── Strength Assessment ────────────────────────────────────────────────────────

interface StrengthAssessmentProps {
  profile: UserProfile;
}

export function StrengthAssessment({ profile }: StrengthAssessmentProps) {
  // DISC assessment state
  const [discResult, setDiscResult] = useState<{
    dominance: number;
    influence: number;
    steadiness: number;
    conscientiousness: number;
  } | null>(null);
  const [showDISCAssessment, setShowDISCAssessment] = useState(false);

  // Load DISC result from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("disc_assessment_result");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setDiscResult((prev) =>
          prev?.dominance !== parsed.dominance ||
          prev?.influence !== parsed.influence ||
          prev?.steadiness !== parsed.steadiness ||
          prev?.conscientiousness !== parsed.conscientiousness
            ? parsed
            : prev,
        );
      } catch (e) {
        console.error("Failed to parse DISC result", e);
      }
    }
  }, []);

  // Calculate various metrics
  const totalSkills = profile.skills.length;
  const totalExperience = profile.years_of_experience || 0;
  const coreSkillsCount = profile.core_skills?.length || 0;
  const projectCount = profile.projects?.length || 0;
  const educationCount = profile.education?.length || 0;
  const certificationCount = profile.certifications?.length || 0;

  // Check if fresh grad (0-1 years experience)
  const isFreshGrad = totalExperience <= 1;

  // Determine strength levels
  const getLevel = (
    score: number,
    thresholds: { weak: number; moderate: number; strong: number },
  ) => {
    if (score >= thresholds.strong)
      return {
        level: "Strong",
        color:
          "text-green-600 dark:text-success bg-green-50 dark:bg-success/10",
        icon: Zap,
      };
    if (score >= thresholds.moderate)
      return {
        level: "Moderate",
        color: "text-blue-600 dark:text-info bg-blue-50 dark:bg-info/10",
        icon: Shield,
      };
    return {
      level: "Developing",
      color: "text-amber-600 dark:text-warning bg-amber-50 dark:bg-warning/10",
      icon: Lightbulb,
    };
  };

  const skillsLevel = getLevel(totalSkills, {
    weak: 3,
    moderate: 8,
    strong: 15,
  });

  // Experience level - different criteria for fresh grads vs experienced
  let experienceLevel;
  if (isFreshGrad) {
    // For fresh grads, check if they have internships or relevant projects instead
    const hasInternships = profile.work_experience.some(
      (e) =>
        e.title.toLowerCase().includes("intern") ||
        e.title.toLowerCase().includes("trainee") ||
        e.title.toLowerCase().includes("junior"),
    );
    const projectScore =
      projectCount >= 3
        ? "strong"
        : projectCount >= 1
          ? "moderate"
          : "developing";

    if (hasInternships || projectScore === "strong") {
      experienceLevel = {
        level: "Ready to Launch",
        color:
          "text-emerald-600 dark:text-success bg-emerald-50 dark:bg-success/10",
        icon: Rocket,
      };
    } else if (projectScore === "moderate") {
      experienceLevel = {
        level: "Building Portfolio",
        color: "text-blue-600 dark:text-info bg-blue-50 dark:bg-info/10",
        icon: Target,
      };
    } else {
      experienceLevel = {
        level: "Fresh Talent",
        color:
          "text-purple-600 dark:text-primary bg-purple-50 dark:bg-primary/10",
        icon: Sparkles,
      };
    }
  } else {
    experienceLevel = getLevel(totalExperience, {
      weak: 1,
      moderate: 3,
      strong: 5,
    });
  }

  const projectsLevel = getLevel(projectCount, {
    weak: 1,
    moderate: 3,
    strong: 5,
  });
  const credentialsLevel = getLevel(educationCount + certificationCount, {
    weak: 1,
    moderate: 2,
    strong: 4,
  });

  // Estimate DISC-style profile based on resume patterns
  const estimateDISC = (): DISCProfile => {
    let dominance = 30,
      influence = 30,
      conscientiousness = 30;
    const steadiness = 30;

    const leadershipKeywords = [
      "lead",
      "manager",
      "senior",
      "principal",
      "director",
      "head",
      "chief",
    ];
    const technicalKeywords = [
      "engineer",
      "developer",
      "architect",
      "technical",
    ];
    const creativeKeywords = ["design", "creative", "product", "ux", "ui"];
    const analyticalKeywords = [
      "data",
      "analyst",
      "science",
      "research",
      "analytics",
    ];

    const allText = [
      ...profile.work_experience.map(
        (e) => `${e.title} ${e.description || ""}`,
      ),
      ...profile.projects.map((p) => `${p.name} ${p.description || ""}`),
      profile.summary || "",
    ]
      .join(" ")
      .toLowerCase();

    if (leadershipKeywords.some((k) => allText.includes(k))) dominance += 20;
    if (creativeKeywords.some((k) => allText.includes(k))) influence += 15;
    if (technicalKeywords.some((k) => allText.includes(k)))
      conscientiousness += 15;
    if (analyticalKeywords.some((k) => allText.includes(k)))
      conscientiousness += 10;

    const total = dominance + influence + steadiness + conscientiousness;
    return {
      dominance: Math.round((dominance / total) * 100),
      influence: Math.round((influence / total) * 100),
      steadiness: Math.round((steadiness / total) * 100),
      conscientiousness: Math.round((conscientiousness / total) * 100),
    };
  };

  const discProfile = discResult || estimateDISC();

  const handleDISCComplete = (result: DISCResult) => {
    // Convert DISCResult (D/I/S/C) to internal format (dominance/influence/steadiness/conscientiousness)
    const converted = {
      dominance: result.profile.D,
      influence: result.profile.I,
      steadiness: result.profile.S,
      conscientiousness: result.profile.C,
    };
    setDiscResult(converted);
    localStorage.setItem("disc_assessment_result", JSON.stringify(converted));
    setShowDISCAssessment(false);
  };

  const assessments = [
    {
      label: "Technical Skills",
      value: totalSkills,
      level: skillsLevel,
      icon: Award,
    },
    {
      label: "Experience",
      value: isFreshGrad ? "Entry Level" : `${totalExperience} yrs`,
      level: experienceLevel,
      icon: Briefcase,
    },
    {
      label: "Projects",
      value: projectCount,
      level: projectsLevel,
      icon: Target,
    },
    {
      label: "Credentials",
      value: educationCount + certificationCount,
      level: credentialsLevel,
      icon: Award,
    },
  ];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Award className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
          Strength Assessment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Fresh Grad Banner */}
        {isFreshGrad && (
          <div className="flex items-start gap-3 rounded-lg border border-purple-200 dark:border-border bg-gradient-to-r from-purple-50 dark:from-muted to-indigo-50 dark:to-muted p-3">
            <Sparkles className="h-5 w-5 text-purple-600 dark:text-primary flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-purple-900 dark:text-foreground">
                Fresh Graduate Profile
              </p>
              <p className="mt-1 text-xs text-purple-700 dark:text-muted-foreground">
                Everyone starts somewhere! Your potential matters more than
                years of experience. Focus on your skills, projects, and
                eagerness to learn.
              </p>
            </div>
          </div>
        )}

        {/* Strength Indicators */}
        <div className="grid grid-cols-2 gap-3">
          {assessments.map((item) => {
            const Icon = item.level.icon;
            return (
              <div key={item.label} className="rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground dark:text-muted-foreground">
                    {item.label}
                  </span>
                  <Icon className="h-3.5 w-3.5 text-muted-foreground dark:text-muted-foreground" />
                </div>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-lg font-semibold text-foreground dark:text-foreground">
                    {item.value}
                  </span>
                  <Badge className={cn("text-[10px]", item.level.color)}>
                    {item.level.level}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>

        {/* DISC-style Profile */}
        <div className="rounded-lg border p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium text-foreground dark:text-muted-foreground">
              Working Style Profile
            </p>
            <span
              className={cn(
                "text-[10px]",
                discResult
                  ? "text-green-600 dark:text-success bg-green-50 dark:bg-success/10 px-2 py-0.5 rounded-full"
                  : "text-muted-foreground dark:text-muted-foreground",
              )}
            >
              {discResult ? "From assessment" : "Estimated from resume"}
            </span>
          </div>
          <div className="space-y-2">
            {[
              {
                label: "Dominance",
                value: discProfile.dominance,
                color: "bg-red-400 dark:bg-destructive",
                desc: "Direct, decisive",
              },
              {
                label: "Influence",
                value: discProfile.influence,
                color: "bg-yellow-400 dark:bg-warning",
                desc: "Social, enthusiastic",
              },
              {
                label: "Steadiness",
                value: discProfile.steadiness,
                color: "bg-green-400 dark:bg-success",
                desc: "Patient, reliable",
              },
              {
                label: "Conscientiousness",
                value: discProfile.conscientiousness,
                color: "bg-blue-400 dark:bg-info",
                desc: "Analytical, precise",
              },
            ].map((item) => (
              <div key={item.label}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground dark:text-muted-foreground">
                    {item.label}
                  </span>
                  <span className="text-muted-foreground dark:text-muted-foreground">
                    {item.value}%
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted dark:bg-muted">
                  <div
                    className={cn("h-full rounded-full", item.color)}
                    style={{ width: `${item.value}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={() => setShowDISCAssessment(true)}
            className="mt-3 w-full rounded-md bg-indigo-50 dark:bg-secondary px-2 py-1.5 text-xs text-indigo-700 dark:text-secondary-foreground text-left hover:bg-indigo-100 dark:hover:bg-muted transition-colors"
          >
            <span className="font-medium">
              {discResult ? "Retake" : "Take"}
            </span>{" "}
            DISC assessment for accurate results →
          </button>
        </div>

        {/* Core Strengths */}
        {coreSkillsCount > 0 && (
          <div className="rounded-lg border p-3">
            <p className="mb-2 text-xs font-medium text-foreground dark:text-muted-foreground">
              Core Strengths
            </p>
            <div className="flex flex-wrap gap-1.5">
              {profile.core_skills!.slice(0, 6).map((skill) => (
                <Badge
                  key={skill}
                  className="bg-indigo-100 dark:bg-primary/10 text-indigo-800 dark:text-primary text-xs"
                >
                  {skill}
                </Badge>
              ))}
              {coreSkillsCount > 6 && (
                <Badge variant="outline" className="text-xs">
                  +{coreSkillsCount - 6} more
                </Badge>
              )}
            </div>
          </div>
        )}
      </CardContent>

      {/* DISC Assessment Dialog */}
      <Dialog open={showDISCAssessment} onOpenChange={setShowDISCAssessment}>
        <DialogContent className="max-w-md">
          <DISCAssessment onComplete={handleDISCComplete} />
        </DialogContent>
      </Dialog>
    </Card>
  );
}
