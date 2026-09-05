import { describe, expect, it } from "vitest";
import {
  blendTopSkillScores,
  buildCategoryRadarData,
  buildEvidenceCorpus,
  countSkillMentions,
  formatCategoryLabel,
  scaleRelativeToMax,
  scoreSkillEvidence,
} from "@/lib/skills-radar";
import type { ProfileSkill, Project, WorkExperience } from "@/lib/types/api";

describe("skills-radar helpers", () => {
  it("formats category labels", () => {
    expect(formatCategoryLabel("programming_language")).toBe(
      "Programming Language",
    );
  });

  it("counts skill mentions in experience and project text", () => {
    const experience: WorkExperience[] = [
      {
        title: "Engineer",
        company: "Acme",
        current: true,
        highlights: ["Shipped Python APIs"],
        technologies: ["Python", "FastAPI"],
      },
    ];
    const projects: Project[] = [
      {
        name: "Job Matcher",
        description: "Ranking with Python and PostgreSQL",
        technologies: ["Python"],
        highlights: [],
      },
    ];
    const corpus = buildEvidenceCorpus(experience, projects);
    expect(countSkillMentions("Python", corpus)).toBeGreaterThanOrEqual(3);
    expect(countSkillMentions("Java", corpus)).toBe(0);
  });

  it("boosts core skills and evidence over bare proficiency", () => {
    const skill: ProfileSkill = {
      name: "Python",
      category: "programming_language",
      proficiency: "Intermediate",
      years_of_experience: 2,
    };
    const bare = scoreSkillEvidence(skill, new Set(), "");
    const boosted = scoreSkillEvidence(
      skill,
      new Set(["python"]),
      "python fastapi python etl",
    );
    expect(boosted).toBeGreaterThan(bare);
  });

  it("blends top skills instead of flattening with a mean", () => {
    // One strong + many weak: top-K blend stays high; mean would drop hard.
    const scores = [90, 30, 28, 25, 22, 20];
    const blend = blendTopSkillScores(scores);
    const mean = Math.round(
      scores.reduce((sum, value) => sum + value, 0) / scores.length,
    );
    expect(blend).toBeGreaterThan(mean);
    expect(blend).toBeGreaterThan(70);
  });

  it("scales categories relative to the strongest", () => {
    const scaled = scaleRelativeToMax({
      programming_language: 80,
      soft_skill: 40,
      other: 0,
    });
    expect(scaled.programming_language).toBe(95);
    expect(scaled.soft_skill).toBe(48);
    expect(scaled.other).toBe(8);
  });

  it("builds uneven radar data when CV evidence is uneven", () => {
    const skills: ProfileSkill[] = [
      {
        name: "Python",
        category: "programming_language",
        proficiency: "Advanced",
        years_of_experience: 4,
      },
      {
        name: "FastAPI",
        category: "framework",
        proficiency: "Intermediate",
        years_of_experience: 2,
      },
      {
        name: "Communication",
        category: "soft_skill",
        proficiency: "Intermediate",
        years_of_experience: 0,
      },
      {
        name: "Excel",
        category: "tool",
        proficiency: "Beginner",
        years_of_experience: 0,
      },
    ];
    const data = buildCategoryRadarData({
      skills,
      core_skills: ["Python"],
      work_experience: [
        {
          title: "Software Engineer",
          company: "DataWorks",
          current: true,
          description: "Built Python and FastAPI services",
          highlights: ["Cut Python API latency by 35%"],
          technologies: ["Python", "FastAPI", "PostgreSQL"],
        },
      ],
      projects: [
        {
          name: "Job Matching API",
          description: "Python ranking service",
          technologies: ["Python", "FastAPI"],
          highlights: [],
        },
      ],
    });

    expect(data.length).toBeGreaterThanOrEqual(3);
    const byLabel = Object.fromEntries(data.map((row) => [row.category, row]));
    expect(byLabel["Programming Language"].score).toBe(95);
    expect(byLabel["Programming Language"].score).toBeGreaterThan(
      byLabel["Soft Skill"].score,
    );
    expect(byLabel["Soft Skill"].score).toBeLessThan(70);
  });

  it("returns empty data for an empty skill list", () => {
    expect(buildCategoryRadarData({ skills: [] })).toEqual([]);
  });
});
