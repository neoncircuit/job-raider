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
  /^(About (the )?(role|job|position|us|company))/i,
  /^(Responsibilities|What you'll do|What you will do|Key responsibilities)/i,
  /^(Requirements|Qualifications|What you'll need|What you will need|Must have)/i,
  /^(Nice to have|Preferred qualifications|Bonus points)/i,
  /^(Benefits|Perks|What we offer|Compensation)/i,
  /(About you)/i,
  /^(Skills|Technologies|Tech stack)/i,
  /^(Experience|Your background)/i,
  /(Why join us)/i,
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

  let inSection = false;

  for (const line of lines) {
    // Check if this line is a section header
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
      inSection = true;
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
  return /^[•\-\*•●]\s/.test(line) ||
         /^\d+[.)\]]\s/.test(line) ||
         line.startsWith('• ');
}

/**
 * Clean bullet point text
 */
export function cleanBulletPoint(text: string): string {
  return text
    .replace(/^[•\-\*•●]\s*/, '• ')  // Normalize bullet character
    .replace(/^\d+[.)\]]\s*/, '')     // Remove numbered list markers
    .trim();
}
