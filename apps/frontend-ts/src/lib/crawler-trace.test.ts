import { describe, expect, it } from "vitest";
import {
  SAMPLE_TRACE,
  buildTrace,
  easeInOutCubic,
  extractedFieldsAt,
  resolveTraceEvents,
  solveFabrik,
  tokenizeParagraphs,
  wordStatesAt,
  type Point,
} from "@/lib/crawler-trace";

const distance = (a: Point, b: Point) => Math.hypot(b.x - a.x, b.y - a.y);

describe("crawler-trace helpers", () => {
  it("tokenizes paragraphs with global word indices", () => {
    const paragraphs = tokenizeParagraphs("Hello world\n\nSecond  line here\n");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[1].map((t) => t.index)).toEqual([2, 3, 4]);
    expect(paragraphs[1][0].text).toBe("Second");
  });

  it("resolves phrases to word ranges and rejects missing phrases", () => {
    const tokens = tokenizeParagraphs("Pay SGD 5,000 per month").flat();
    const [event] = resolveTraceEvents(tokens, [
      { id: "s", phrase: "SGD 5,000", decision: "kept", reason: "r" },
    ]);
    expect([event.start, event.end]).toEqual([1, 3]);
    expect(() =>
      resolveTraceEvents(tokens, [
        { id: "x", phrase: "USD 9,000", decision: "kept", reason: "r" },
      ]),
    ).toThrow(/not found/);
  });

  it("applies only completed decisions to word states", () => {
    const trace = buildTrace("t", "Title here. Cookie banner.", [
      { id: "a", phrase: "Title here.", decision: "kept", reason: "r" },
      { id: "b", phrase: "Cookie banner.", decision: "discarded", reason: "r" },
    ]);
    expect(wordStatesAt(trace.events, trace.tokens.length, 1)).toEqual([
      "kept",
      "kept",
      "unread",
      "unread",
    ]);
    expect(wordStatesAt(trace.events, trace.tokens.length, 2)).toEqual([
      "kept",
      "kept",
      "discarded",
      "discarded",
    ]);
  });

  it("merges same-field phrases without trailing punctuation", () => {
    const trace = buildTrace("t", "Python and Go. Share on X.", [
      {
        id: "a",
        phrase: "Python",
        decision: "kept",
        field: "Skills",
        reason: "r",
      },
      { id: "b", phrase: "Share on X.", decision: "discarded", reason: "r" },
      {
        id: "c",
        phrase: "Go.",
        decision: "kept",
        field: "Skills",
        reason: "r",
      },
    ]);
    expect(extractedFieldsAt(trace.events, trace.tokens, 3)).toEqual([
      { field: "Skills", value: "Python; Go", decision: "kept" },
    ]);
  });

  it("resolves every sample event and flags the WhatsApp contact", () => {
    const { events, tokens } = SAMPLE_TRACE;
    expect(events.length).toBeGreaterThan(5);
    const fields = extractedFieldsAt(events, tokens, events.length);
    const scam = fields.find((f) => f.field === "Scam flags");
    expect(scam?.decision).toBe("flagged");
    expect(scam?.value).toContain("WhatsApp");
    expect(fields.find((f) => f.field === "Salary")?.value).toBe(
      "SGD 5,500 – 7,500 per month",
    );
  });

  it("eases from 0 to 1 and clamps out-of-range input", () => {
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(1)).toBe(1);
    expect(easeInOutCubic(0.5)).toBeCloseTo(0.5);
    expect(easeInOutCubic(-1)).toBe(0);
    expect(easeInOutCubic(2)).toBe(1);
  });

  it("reaches a target within range while keeping segment lengths", () => {
    const base = { x: 0, y: 0 };
    const joints = [0, 1, 2, 3, 4].map((i) => ({ x: i * 10, y: 0 }));
    const lengths = [10, 10, 10, 10];
    const target = { x: 20, y: 25 };
    const solved = solveFabrik(joints, base, target, lengths, 20);

    expect(solved[0]).toEqual(base);
    expect(distance(solved[4], target)).toBeLessThan(0.5);
    for (let i = 0; i < 4; i++) {
      expect(distance(solved[i], solved[i + 1])).toBeCloseTo(10, 3);
    }
  });

  it("stretches straight toward an unreachable target", () => {
    const base = { x: 0, y: 0 };
    const joints = [0, 1, 2].map(() => ({ x: 0, y: 0 }));
    const solved = solveFabrik(joints, base, { x: 100, y: 0 }, [10, 10]);
    expect(solved.map((p) => Math.round(p.x))).toEqual([0, 10, 20]);
    expect(solved.every((p) => Math.abs(p.y) < 1e-9)).toBe(true);
  });
});
