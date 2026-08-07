/**
 * Detect messy JD paste patterns and return a short user-facing hint.
 *
 * @param text - Raw job description pasted by the user.
 * @returns Professional hint string, or null when paste looks clean.
 */
export function getJdPasteHint(text: string): string | null {
  if (!text || !text.trim()) {
    return null;
  }

  const sample = text.slice(0, 8000);

  if (/<[a-z][\s\S]*?>/i.test(sample)) {
    return "This paste includes HTML markup. Consider copying plain text from the job page for cleaner extraction.";
  }

  const linkedInChrome = [
    /\bshow more\b/i,
    /\bsee more\b/i,
    /\beasy apply\b/i,
    /\bpeople clicked apply\b/i,
    /\bactively reviewing applicants\b/i,
    /\bpromoted\b/i,
  ];

  if (linkedInChrome.some((pattern) => pattern.test(sample))) {
    return "This paste looks like LinkedIn job UI text. Scroll the full description, copy again, and remove buttons such as Easy Apply or Show more.";
  }

  return null;
}
