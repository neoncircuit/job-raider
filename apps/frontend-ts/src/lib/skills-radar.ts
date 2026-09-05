/**
 * Evidence-weighted skills radar scoring for the Profile page.
 *
 * Category axes stay the same; scores use CV evidence and relative
 * scaling so strong categories pull away from weak ones.
 */

import type { ProfileSkill, Project, WorkExperience } from "@/lib/types/api";

/** One axis on the skills radar chart. */
export interface RadarCategoryScore {
  /** Display label (title-cased category). */
  category: string;
  /** Relative score 0–100 after profile scaling. */
  score: number;
  /** Number of skills in this category. */
  count: number;
  /** Raw evidence score before relative scaling. */
  rawScore: number;
}

/** Inputs used to build category radar data. */
export interface SkillsRadarInput {
  skills: ProfileSkill[];
  core_skills?: string[] | null;
  work_experience?: WorkExperience[] | null;
  projects?: Project[] | null;
}

const PROFICIENCY_BASE: Record<string, number> = {
  Expert: 72,
  Advanced: 58,
  Intermediate: 42,
  Beginner: 22,
};

const TOP_K = 3;
/** Weights for the top 1–3 skills within a category (sum = 1). */
const TOP_WEIGHTS = [0.7, 0.2, 0.1] as const;
const RELATIVE_MAX = 95;
const EMPTY_CATEGORY_FLOOR = 8;
const NO_EVIDENCE_FLOOR = 12;

/**
 * Normalize a skill or technology name for case-insensitive matching.
 *
 * @param value - Raw skill or tech string.
 * @returns Lowercased trimmed token, or empty string.
 */
export function normalizeSkillToken(value: string): string {
  return (value || "").trim().toLowerCase();
}

/**
 * Format a category key for radar axis labels.
 *
 * @param category - Raw category key (e.g. ``programming_language``).
 * @returns Title-cased label.
 */
export function formatCategoryLabel(category: string): string {
  return category
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/**
 * Build a searchable evidence corpus from experience and projects.
 *
 * @param workExperience - Profile work experience entries.
 * @param projects - Profile project entries.
 * @returns Lowercased blob used for mention counting.
 */
export function buildEvidenceCorpus(
  workExperience: WorkExperience[] = [],
  projects: Project[] = [],
): string {
  const parts: string[] = [];
  for (const entry of workExperience) {
    if (entry.description) parts.push(entry.description);
    for (const highlight of entry.highlights || []) {
      if (highlight) parts.push(highlight);
    }
    for (const tech of entry.technologies || []) {
      if (tech) parts.push(tech);
    }
  }
  for (const project of projects) {
    if (project.description) parts.push(project.description);
    if (project.role) parts.push(project.role);
    for (const highlight of project.highlights || []) {
      if (highlight) parts.push(highlight);
    }
    for (const tech of project.technologies || []) {
      if (tech) parts.push(tech);
    }
  }
  return parts.join("\n").toLowerCase();
}

/**
 * Count how many times a skill name appears as a whole-ish token in corpus text.
 *
 * @param skillName - Skill to search for.
 * @param corpus - Lowercased evidence text.
 * @returns Mention count (0 when the name is too short to match safely).
 */
export function countSkillMentions(skillName: string, corpus: string): number {
  const token = normalizeSkillToken(skillName);
  if (!token || token.length < 2 || !corpus) return 0;
  // Escape regex metacharacters in skill names (e.g. C++, C#).
  const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(
    `(^|[^a-z0-9+#])${escaped}(?=[^a-z0-9+#]|$)`,
    "gi",
  );
  const matches = corpus.match(pattern);
  return matches?.length ?? 0;
}

/**
 * Score a single skill from proficiency, years, core list, and CV mentions.
 *
 * @param skill - Profile skill row.
 * @param coreSkills - Normalized core skill names.
 * @param corpus - Lowercased experience/project evidence text.
 * @returns Raw skill evidence score (uncapped soft range ~0–100).
 */
export function scoreSkillEvidence(
  skill: ProfileSkill,
  coreSkills: Set<string>,
  corpus: string,
): number {
  const name = normalizeSkillToken(skill.name);
  if (!name) return 0;

  let score = 0;
  const proficiency = skill.proficiency ?? null;
  if (proficiency && PROFICIENCY_BASE[proficiency] != null) {
    score = PROFICIENCY_BASE[proficiency];
  } else {
    const years = skill.years_of_experience ?? 0;
    if (years >= 5) score = 55;
    else if (years >= 3) score = 45;
    else if (years >= 1) score = 32;
    else score = NO_EVIDENCE_FLOOR;
  }

  const years = skill.years_of_experience ?? 0;
  score += Math.min(years * 4, 16);

  if (coreSkills.has(name)) {
    score += 12;
  }

  const mentions = countSkillMentions(skill.name, corpus);
  // Diminishing returns: first mentions matter most.
  score += Math.min(mentions * 8, 28);

  return Math.max(0, Math.min(100, Math.round(score)));
}

/**
 * Blend the top K skill scores in a category (not a flat mean).
 *
 * @param scores - Descending skill scores in one category.
 * @returns Weighted top-K blend, or 0 when empty.
 */
export function blendTopSkillScores(scores: number[]): number {
  if (scores.length === 0) return 0;
  const ranked = [...scores].sort((a, b) => b - a).slice(0, TOP_K);
  let weightSum = 0;
  let valueSum = 0;
  ranked.forEach((value, index) => {
    const weight = TOP_WEIGHTS[index] ?? 0;
    valueSum += value * weight;
    weightSum += weight;
  });
  if (weightSum <= 0) return 0;
  return Math.round(valueSum / weightSum);
}

/**
 * Scale category raw scores so the strongest maps near RELATIVE_MAX.
 *
 * @param rawScores - Category raw scores keyed by category id.
 * @returns Relative scores keyed the same way.
 */
export function scaleRelativeToMax(
  rawScores: Record<string, number>,
): Record<string, number> {
  const values = Object.values(rawScores);
  if (values.length === 0) return {};
  const max = Math.max(...values, 0);
  if (max <= 0) {
    return Object.fromEntries(
      Object.keys(rawScores).map((key) => [key, EMPTY_CATEGORY_FLOOR]),
    );
  }
  const scaled: Record<string, number> = {};
  for (const [key, raw] of Object.entries(rawScores)) {
    if (raw <= 0) {
      scaled[key] = EMPTY_CATEGORY_FLOOR;
      continue;
    }
    scaled[key] = Math.max(
      EMPTY_CATEGORY_FLOOR,
      Math.min(100, Math.round((raw / max) * RELATIVE_MAX)),
    );
  }
  return scaled;
}

/**
 * Build radar category rows from profile skills and CV evidence.
 *
 * @param input - Skills plus optional core skills, experience, and projects.
 * @returns Category scores sorted by relative score descending (all categories).
 */
export function buildCategoryRadarData(
  input: SkillsRadarInput,
): RadarCategoryScore[] {
  const skills = input.skills || [];
  if (skills.length === 0) return [];

  const coreSkills = new Set(
    (input.core_skills || []).map(normalizeSkillToken).filter(Boolean),
  );
  const corpus = buildEvidenceCorpus(
    input.work_experience || [],
    input.projects || [],
  );

  const byCategory = new Map<string, number[]>();
  for (const skill of skills) {
    const cat = skill.category || "other";
    const score = scoreSkillEvidence(skill, coreSkills, corpus);
    const list = byCategory.get(cat) ?? [];
    list.push(score);
    byCategory.set(cat, list);
  }

  const rawByCategory: Record<string, number> = {};
  const countByCategory: Record<string, number> = {};
  for (const [cat, scores] of byCategory.entries()) {
    rawByCategory[cat] = blendTopSkillScores(scores);
    countByCategory[cat] = scores.length;
  }

  const relative = scaleRelativeToMax(rawByCategory);

  return Object.keys(rawByCategory)
    .map((cat) => ({
      category: formatCategoryLabel(cat),
      score: relative[cat] ?? EMPTY_CATEGORY_FLOOR,
      count: countByCategory[cat] ?? 0,
      rawScore: rawByCategory[cat] ?? 0,
    }))
    .sort((a, b) => b.score - a.score || b.rawScore - a.rawScore);
}
