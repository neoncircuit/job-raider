/**
 * Split a comma-separated input into trimmed, non-empty terms.
 *
 * Only commas separate terms, so a multi-word term such as "New York" or
 * "machine learning" stays whole. The Pipeline form, the Jobs search bar,
 * and the profile job targets all use this function.
 *
 * @param value - Raw input text.
 * @returns The terms in input order.
 */
export function splitList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}
