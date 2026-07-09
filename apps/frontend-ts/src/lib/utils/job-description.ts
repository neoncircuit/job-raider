/**
 * Job description formatting utilities
 */

export interface JobDescriptionSection {
  title: string;
  content: string[];
}

/**
 * Format a raw job description into structured, readable sections
 */
export function formatJobDescription(description: string): JobDescriptionSection[] {
  if (!description || description.trim().length === 0) {
    return [];
  }

  // Clean up the description
  const cleaned = cleanDescription(description);

  // Try to parse into sections
  const sections = parseSections(cleaned);

  return sections;
}

/**
 * Clean up messy job descriptions
 */
function cleanDescription(text: string): string {
  return text
    // Remove excessive whitespace (more than 2 consecutive newlines)
    .replace(/\n{3,}/g, '\n\n')
    // Clean up bullet points
    .replace(/[·•●]/g, '•')
    // Normalize spaces
    .replace(/[ \t]+/g, ' ')
    // Remove URLs (optional - keeps things cleaner)
    .replace(/https?:\/\/[^\s]+/g, '[URL]')
    .trim();
}

/**
 * Common section headers in job descriptions
 */
const SECTION_PATTERNS = [
  // Only match clear, unambiguous section headers
  /^(About (the )?(role|job|position|us|company|team))/i,
  /^(Responsibilities|What you'll do|What you will do|Key responsibilities|Your role)/i,
  /^(Requirements|Qualifications|What you'll need|What you will need|Must have|Required skills)/i,
  /^(Nice to have|Preferred qualifications|Bonus points|Plus)/i,
  /^(Benefits|Perks|What we offer|Compensation|What you get)/i,
  /(About you|Your profile)/i,
  /^(Skills|Technologies|Tech stack|Tools|Stack)/i,
  /^(Your background|Background|Your experience)/i,
  /(Why join us|Why work with us)/i,
  /^(Day to day|Daily|What you'll be doing)/i,
  /^(The team|Our team|Team culture)/i,
  // Very specific, clear section headers only
  /^(Required|Preferred|Desired) (Skills|Qualifications|Experience|Competencies)$/i,
  /^(Key|Core|Essential) (Skills|Requirements|Competencies)$/i,
  /^(Technical|Professional|Personal) (Skills|Requirements|Qualifications)$/i,
  /^(Job |Role )(Overview|Summary|Description)$/i,
  /^(Company |Organization )(Overview|About|Culture)$/i,
];

/**
 * Parse description into sections based on common patterns
 */
function parseSections(text: string): JobDescriptionSection[] {
  const sections: JobDescriptionSection[] = [];
  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  let currentSection: JobDescriptionSection = {
    title: 'Overview',
    content: []
  };

  for (const line of lines) {
    // Check if this line is a section header (no heuristic - only exact patterns)
    const isHeader = SECTION_PATTERNS.some(pattern => pattern.test(line));

    if (isHeader) {
      // Save previous section if it has content
      if (currentSection.content.length > 0) {
        sections.push(currentSection);
      }

      // Start new section
      currentSection = {
        title: line.replace(/[•:]/g, '').trim(),
        content: []
      };
    } else {
      // Add line to current section
      currentSection.content.push(line);
    }
  }

  // Don't forget the last section
  if (currentSection.content.length > 0) {
    sections.push(currentSection);
  }

  // If no sections were found, treat entire description as one section
  if (sections.length === 0) {
    sections.push({
      title: 'Description',
      content: lines
    });
  }

  return sections;
}

/**
 * Check if a line looks like a bullet point
 */
export function isBulletPoint(line: string): boolean {
  const trimmed = line.trim();

  // Standard bullet characters
  if (/^[•\-\*•●]\s/.test(trimmed)) return true;

  // Numbered lists
  if (/^\d+[.)\]]\s/.test(trimmed)) return true;

  // Ultra-aggressive detection: treat most short phrases as bullet points
  // Job descriptions often have lists without bullet characters

  // If it's a short line (under 120 chars) and not ending with sentence punctuation
  if (trimmed.length < 120 && trimmed.length > 3 && !/[.!?]$/.test(trimmed)) {
    // Exclude very clear headers (section titles)
    const firstWord = trimmed.split(/\s+/)[0].toLowerCase();
    const isVeryClearHeader = /^(about|responsibilities|requirements|benefits|perks|company|organization|team|culture|why|how|what)$/i.test(firstWord);

    if (!isVeryClearHeader) {
      // Exclude obvious full sentences
      const hasFullSentencePattern = /\b(you\s+will|we\s+are|they\s+will|you'll|we'll|you\s+should|we\s+should)\s+(be|have|do|go|get|take|make)\b/i.test(trimmed);

      if (!hasFullSentencePattern) {
        // Pretty much anything else short and capitalized is a bullet point
        if (/^[A-Z]/.test(trimmed)) {
          return true;
        }

        // Even if not capitalized, if it looks like a list item
        if (trimmed.length < 80 && trimmed.split(/\s+/).length >= 2) {
          return true;
        }
      }
    }
  }

  return false;
}

/**
 * Clean bullet point text - removes bullet markers since renderer adds them
 */
export function cleanBulletPoint(text: string): string {
  return text
    .replace(/^[•\-\*•●]\s*/, '')     // Remove bullet character completely
    .replace(/^\d+[.)\]]\s*/, '')     // Remove numbered list markers
    .trim();
}
