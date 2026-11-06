import { isDemoMode } from "@/demo/mode";

const REPOSITORY = "https://github.com/neoncircuit/job-raider#measured-results";

/**
 * Say on each page that this is a demo with sample data.
 *
 * @returns The banner in the demo build, and nothing in the server build.
 */
export function DemoBanner() {
  if (!isDemoMode()) {
    return null;
  }
  return (
    <p
      role="note"
      className="border-b border-border bg-muted px-4 py-2 text-center text-xs text-muted-foreground"
    >
      Demo with sample data. The candidate, jobs, and companies are fictional,
      and nothing leaves your browser.{" "}
      <a href={REPOSITORY} className="underline">
        See the measured results
      </a>
      .
    </p>
  );
}

/**
 * Say what the rule checks missed in the sample letter.
 *
 * A test keeps this text true: the letter says "deployed", and the profile
 * does not.
 *
 * @returns The note in the demo build, and nothing in the server build.
 */
export function DemoLetterNote() {
  if (!isDemoMode()) {
    return null;
  }
  return (
    <p role="note" className="rounded-md border p-3 text-xs">
      Sample letter, written once by the default local model and not edited. The
      rule checks approved it, but they miss real errors: this letter says
      &quot;deployed&quot;, and the profile does not. Read each letter before
      you send it.
    </p>
  );
}
