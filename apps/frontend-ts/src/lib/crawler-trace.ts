/**
 * Job Raider - Crawler trace helpers
 *
 * Data model and pure helpers for the crawler replay prototype. A trace is
 * the listing page text plus an ordered list of extraction decisions. The
 * replay animates each decision; it must never show a decision that the
 * trace does not contain.
 */

/** Outcome of one extraction decision. */
export type TraceDecision = "kept" | "discarded" | "flagged";

/** Display state of one word during replay. */
export type WordState = "unread" | TraceDecision;

/** One word of the page text with its global position. */
export interface TraceToken {
  /** Zero-based index across the whole page. */
  index: number;
  /** Word text as it appears on the page. */
  text: string;
}

/** Authoring form of a decision: the phrase it covers on the page. */
export interface TraceEventSpec {
  /** Stable identifier. */
  id: string;
  /** Exact phrase from the page text (whitespace-insensitive). */
  phrase: string;
  /** What the extractor did with the phrase. */
  decision: TraceDecision;
  /** Listing field the phrase fills (kept or flagged only). */
  field?: string;
  /** Short reason shown in the decision log. */
  reason: string;
}

/** A decision resolved to a word range. */
export interface TraceEvent extends TraceEventSpec {
  /** First word index (inclusive). */
  start: number;
  /** Last word index (exclusive). */
  end: number;
}

/** A trace ready for replay. */
export interface ResolvedTrace {
  /** Where the page text came from. */
  source: string;
  /** Page words grouped by paragraph. */
  paragraphs: TraceToken[][];
  /** All page words in order. */
  tokens: TraceToken[];
  /** Decisions in replay order. */
  events: TraceEvent[];
}

/** One extracted field shown beside the page. */
export interface ExtractedField {
  /** Field name, for example "Salary". */
  field: string;
  /** Joined phrase values for the field. */
  value: string;
  /** "kept" for listing data, "flagged" for scam indicators. */
  decision: Exclude<TraceDecision, "discarded">;
}

/** 2D point in canvas pixels. */
export interface Point {
  x: number;
  y: number;
}

/**
 * Split page text into paragraphs of words with global indices.
 *
 * Args:
 *   text: Page text. Blank or line breaks separate paragraphs.
 *
 * Returns:
 *   Paragraphs of tokens. Empty lines are dropped.
 */
export function tokenizeParagraphs(text: string): TraceToken[][] {
  let index = 0;
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) =>
      line.split(/\s+/).map((word) => ({ index: index++, text: word })),
    );
}

/**
 * Resolve authored phrases to word ranges.
 *
 * Args:
 *   tokens: All page words in order.
 *   specs: Decisions with exact page phrases.
 *
 * Returns:
 *   Decisions with start and end word indices.
 *
 * Raises:
 *   Error: When a phrase does not occur in the page text.
 */
export function resolveTraceEvents(
  tokens: TraceToken[],
  specs: TraceEventSpec[],
): TraceEvent[] {
  const words = tokens.map((token) => token.text);
  return specs.map((spec) => {
    const needle = spec.phrase.trim().split(/\s+/);
    for (let start = 0; start + needle.length <= words.length; start++) {
      if (needle.every((word, offset) => words[start + offset] === word)) {
        return { ...spec, start, end: start + needle.length };
      }
    }
    throw new Error(`Trace phrase not found on page: "${spec.phrase}"`);
  });
}

/**
 * Build a replay-ready trace from page text and decision specs.
 *
 * Args:
 *   source: Label for where the page text came from.
 *   text: Page text.
 *   specs: Decisions in replay order.
 *
 * Returns:
 *   The resolved trace.
 */
export function buildTrace(
  source: string,
  text: string,
  specs: TraceEventSpec[],
): ResolvedTrace {
  const paragraphs = tokenizeParagraphs(text);
  const tokens = paragraphs.flat();
  return {
    source,
    paragraphs,
    tokens,
    events: resolveTraceEvents(tokens, specs),
  };
}

/**
 * Compute each word's display state after a number of decisions.
 *
 * Args:
 *   events: Decisions in replay order.
 *   wordCount: Total page words.
 *   step: Number of decisions already applied.
 *
 * Returns:
 *   One state per word.
 */
export function wordStatesAt(
  events: TraceEvent[],
  wordCount: number,
  step: number,
): WordState[] {
  const states: WordState[] = new Array(wordCount).fill("unread");
  for (const event of events.slice(0, step)) {
    for (let i = event.start; i < event.end; i++) states[i] = event.decision;
  }
  return states;
}

/**
 * List fields extracted after a number of decisions.
 *
 * Phrases for the same field are joined in order, without trailing
 * punctuation. Discarded phrases never produce a field.
 *
 * Args:
 *   events: Decisions in replay order.
 *   tokens: All page words.
 *   step: Number of decisions already applied.
 *
 * Returns:
 *   Fields in first-seen order.
 */
export function extractedFieldsAt(
  events: TraceEvent[],
  tokens: TraceToken[],
  step: number,
): ExtractedField[] {
  const fields = new Map<string, ExtractedField>();
  for (const event of events.slice(0, step)) {
    if (event.decision === "discarded" || !event.field) continue;
    const value = tokens
      .slice(event.start, event.end)
      .map((token) => token.text)
      .join(" ")
      .replace(/[.,;:]+$/, "");
    const existing = fields.get(event.field);
    if (existing) {
      existing.value = `${existing.value}; ${value}`;
    } else {
      fields.set(event.field, {
        field: event.field,
        value,
        decision: event.decision,
      });
    }
  }
  return [...fields.values()];
}

/**
 * Cubic ease-in-out for animation progress.
 *
 * Args:
 *   t: Linear progress, clamped to 0..1.
 *
 * Returns:
 *   Eased progress in 0..1.
 */
export function easeInOutCubic(t: number): number {
  const x = Math.min(Math.max(t, 0), 1);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

function distance(a: Point, b: Point): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function towards(from: Point, to: Point, length: number): Point {
  const d = distance(from, to) || 1e-6;
  const t = length / d;
  return { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t };
}

/**
 * Solve a joint chain with FABRIK so its tip reaches a target.
 *
 * The base stays fixed and every segment keeps its length. When the target
 * is out of reach, the chain stretches straight toward it.
 *
 * Args:
 *   joints: Current joint positions, base first. Not mutated.
 *   base: Anchor for the first joint.
 *   target: Desired tip position.
 *   lengths: Segment lengths; one fewer than the joint count.
 *   iterations: Maximum solver passes.
 *   tolerance: Stop when the tip is this close to the target.
 *
 * Returns:
 *   New joint positions.
 */
export function solveFabrik(
  joints: Point[],
  base: Point,
  target: Point,
  lengths: number[],
  iterations = 8,
  tolerance = 0.5,
): Point[] {
  const points = joints.map((p) => ({ ...p }));
  const last = points.length - 1;
  points[0] = { ...base };

  const reach = lengths.reduce((sum, length) => sum + length, 0);
  if (distance(base, target) >= reach) {
    for (let i = 0; i < last; i++) {
      points[i + 1] = towards(points[i], target, lengths[i]);
    }
    return points;
  }

  for (let pass = 0; pass < iterations; pass++) {
    points[last] = { ...target };
    for (let i = last - 1; i >= 0; i--) {
      points[i] = towards(points[i + 1], points[i], lengths[i]);
    }
    points[0] = { ...base };
    for (let i = 0; i < last; i++) {
      points[i + 1] = towards(points[i], points[i + 1], lengths[i]);
    }
    if (distance(points[last], target) < tolerance) break;
  }
  return points;
}

const SAMPLE_PAGE_TEXT = `
We use cookies to improve your experience. Accept all cookies?
Software Engineer (Python, Data Platform)
Kopi Analytics Pte Ltd · Singapore (Hybrid) · Full time
SGD 5,500 – 7,500 per month
About the role
You will build data pipelines and internal APIs that power our analytics products for retail clients across Southeast Asia.
Requirements
3+ years of experience with Python, FastAPI and PostgreSQL. Familiarity with Docker and CI/CD pipelines.
Nice to have
Experience with Airflow or dbt.
Kopi Analytics is an equal opportunity employer and values diversity at our company.
Share this job on Facebook LinkedIn X
For faster processing, WhatsApp our HR team at +65 8123 4567 to confirm your interview slot.
Similar jobs you may like: Data Analyst, Backend Developer, QA Engineer
`;

const SAMPLE_EVENTS: TraceEventSpec[] = [
  {
    id: "cookies",
    phrase: "We use cookies to improve your experience. Accept all cookies?",
    decision: "discarded",
    reason: "Cookie banner, not listing content",
  },
  {
    id: "title",
    phrase: "Software Engineer (Python, Data Platform)",
    decision: "kept",
    field: "Title",
    reason: "Listing heading",
  },
  {
    id: "company",
    phrase: "Kopi Analytics Pte Ltd",
    decision: "kept",
    field: "Company",
    reason: "Employer name under the heading",
  },
  {
    id: "location",
    phrase: "Singapore (Hybrid)",
    decision: "kept",
    field: "Location",
    reason: "Location and work arrangement",
  },
  {
    id: "job-type",
    phrase: "Full time",
    decision: "kept",
    field: "Job type",
    reason: "Employment type",
  },
  {
    id: "salary",
    phrase: "SGD 5,500 – 7,500 per month",
    decision: "kept",
    field: "Salary",
    reason: "Parsed monthly salary range",
  },
  {
    id: "summary",
    phrase:
      "You will build data pipelines and internal APIs that power our analytics products for retail clients across Southeast Asia.",
    decision: "kept",
    field: "Summary",
    reason: "Role description",
  },
  {
    id: "experience",
    phrase: "3+ years of experience",
    decision: "kept",
    field: "Experience",
    reason: "Minimum years required",
  },
  {
    id: "skills-core",
    phrase: "Python, FastAPI and PostgreSQL.",
    decision: "kept",
    field: "Required skills",
    reason: "Requirements section",
  },
  {
    id: "skills-ops",
    phrase: "Docker and CI/CD pipelines.",
    decision: "kept",
    field: "Required skills",
    reason: "Requirements section",
  },
  {
    id: "skills-nice",
    phrase: "Airflow or dbt.",
    decision: "kept",
    field: "Nice-to-have skills",
    reason: "Nice to have section",
  },
  {
    id: "eeo",
    phrase:
      "Kopi Analytics is an equal opportunity employer and values diversity at our company.",
    decision: "discarded",
    reason: "Boilerplate, no listing facts",
  },
  {
    id: "share",
    phrase: "Share this job on Facebook LinkedIn X",
    decision: "discarded",
    reason: "Page navigation",
  },
  {
    id: "whatsapp",
    phrase:
      "For faster processing, WhatsApp our HR team at +65 8123 4567 to confirm your interview slot.",
    decision: "flagged",
    field: "Scam flags",
    reason: "Scam indicator: asks to contact HR on WhatsApp",
  },
  {
    id: "similar",
    phrase:
      "Similar jobs you may like: Data Analyst, Backend Developer, QA Engineer",
    decision: "discarded",
    reason: "Related listings, not this job",
  },
];

/** Hand-written sample trace for the prototype (not live scraper output). */
export const SAMPLE_TRACE: ResolvedTrace = buildTrace(
  "Sample listing (fictional employer)",
  SAMPLE_PAGE_TEXT,
  SAMPLE_EVENTS,
);
