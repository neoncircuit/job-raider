"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { FastForward, Pause, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useMediaQuery } from "@/lib/hooks/use-media-query";
import { cn } from "@/lib/utils/cn";
import {
  easeInOutCubic,
  extractedFieldsAt,
  solveFabrik,
  wordStatesAt,
  type Point,
  type ResolvedTrace,
  type TraceDecision,
  type WordState,
} from "@/lib/crawler-trace";

const TENTACLE_COUNT = 3;
const SEGMENTS = 16;
const BODY_RADIUS = 22;
/** Must match the right padding (``pr-24``) of the page text container. */
const GUTTER_PX = 96;

const TIMING_MS = {
  reach: 650,
  crawlPerWord: 85,
  crawlMax: 1400,
  decide: 380,
  retract: 480,
};

type Phase = "reach" | "crawl" | "decide" | "retract";

interface Tentacle {
  joints: Point[];
  lengths: number[];
  seed: number;
}

interface ActiveGrab {
  eventIndex: number;
  tentacle: number;
  phase: Phase;
  phaseStart: number;
  from: Point;
  tip: Point;
}

interface Simulation {
  body: Point;
  tentacles: Tentacle[];
  active: ActiveGrab | null;
  lastFrame: number;
}

interface Palette {
  body: string;
  eye: string;
  pupil: string;
  decision: Record<TraceDecision, string>;
}

const WORD_CLASS: Record<WordState | "reading", string> = {
  unread: "text-foreground/80",
  reading: "bg-warning/20 text-foreground",
  kept: "bg-success/15 text-success",
  discarded:
    "text-muted-foreground/60 line-through decoration-muted-foreground/40",
  flagged: "bg-destructive/15 text-destructive",
};

const DECISION_LABEL: Record<TraceDecision, string> = {
  kept: "Kept",
  discarded: "Discarded",
  flagged: "Flagged",
};

const DECISION_BADGE: Record<TraceDecision, string> = {
  kept: "bg-success/15 text-success",
  discarded: "bg-muted text-muted-foreground",
  flagged: "bg-destructive/15 text-destructive",
};

const DECISION_DOT: Record<TraceDecision, string> = {
  kept: "bg-success",
  discarded: "bg-muted-foreground",
  flagged: "bg-destructive",
};

function lerpPoint(a: Point, b: Point, t: number): Point {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

function readPalette(element: HTMLElement): Palette {
  const style = getComputedStyle(element);
  const read = (name: string, fallback: string) =>
    style.getPropertyValue(name).trim() || fallback;
  return {
    body: read("--primary", "#c5303e"),
    eye: read("--background", "#ffffff"),
    pupil: read("--foreground", "#111111"),
    decision: {
      kept: read("--success", "#15803d"),
      discarded: read("--muted-foreground", "#6b7280"),
      flagged: read("--destructive", "#b91c1c"),
    },
  };
}

function createSimulation(): Simulation {
  return {
    body: { x: 0, y: 0 },
    tentacles: Array.from({ length: TENTACLE_COUNT }, (_, k) => ({
      joints: Array.from({ length: SEGMENTS + 1 }, () => ({ x: 0, y: 0 })),
      lengths: new Array(SEGMENTS).fill(3),
      seed: k * 2.1,
    })),
    active: null,
    lastFrame: 0,
  };
}

function anchorFor(body: Point, k: number): Point {
  const angle = Math.PI * (0.8 + k * 0.2);
  return {
    x: body.x + Math.cos(angle) * BODY_RADIUS * 0.6,
    y: body.y + Math.sin(angle) * BODY_RADIUS * 0.6,
  };
}

function restTipFor(body: Point, k: number, now: number, seed: number): Point {
  const angle = Math.PI * (0.75 + k * 0.25) + Math.sin(now / 700 + seed) * 0.3;
  const radius = 52 + Math.sin(now / 500 + seed) * 6;
  return {
    x: body.x + Math.cos(angle) * radius,
    y: body.y + Math.sin(angle) * radius,
  };
}

interface CrawlerReplayProps {
  /** Trace to replay. */
  trace: ResolvedTrace;
}

/**
 * Animated replay of how a listing page is read.
 *
 * A "parasite" in the right gutter sends tentacles across the page words.
 * Each grab maps to one trace decision: kept words fill a field, discarded
 * words fade, flagged words raise a scam flag. Users who prefer reduced
 * motion get the same decisions without the canvas animation.
 *
 * @param trace - Resolved trace to replay.
 */
export function CrawlerReplay({ trace }: CrawlerReplayProps) {
  const { paragraphs, tokens, events } = trace;
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fast, setFast] = useState(false);
  const [reading, setReading] = useState<{ start: number; end: number } | null>(
    null,
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wordRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const simRef = useRef<Simulation>(createSimulation());
  const stepRef = useRef(0);
  const playingRef = useRef(false);
  const speedRef = useRef(1);

  const done = step >= events.length;
  const states = useMemo(
    () => wordStatesAt(events, tokens.length, step),
    [events, tokens.length, step],
  );
  const fields = useMemo(
    () => extractedFieldsAt(events, tokens, step),
    [events, tokens, step],
  );
  const committed = events.slice(0, step);
  const latest = committed.at(-1);

  useEffect(() => {
    if (reducedMotion) return;
    const container = containerRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!container || !canvas || !ctx) return;

    let frame = 0;
    let palette = readPalette(container);
    let paletteReadAt = 0;
    let readingEnd = -1;

    const wordCenter = (index: number, origin: DOMRect): Point => {
      const span = wordRefs.current[index];
      if (!span) return { x: origin.width / 2, y: origin.height / 2 };
      const rect = span.getBoundingClientRect();
      return {
        x: rect.left - origin.left + rect.width / 2,
        y: rect.top - origin.top + rect.height / 2,
      };
    };

    const tick = (now: number) => {
      const sim = simRef.current;
      const origin = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = Math.round(origin.width * dpr);
      const height = Math.round(origin.height * dpr);
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      if (now - paletteReadAt > 1000) {
        palette = readPalette(container);
        paletteReadAt = now;
      }

      const delta = sim.lastFrame ? now - sim.lastFrame : 0;
      sim.lastFrame = now;
      if (sim.body.x === 0) {
        sim.body = { x: origin.width - GUTTER_PX / 2, y: origin.height / 2 };
      }
      sim.body.x = origin.width - GUTTER_PX / 2;

      const restTip = (k: number) =>
        restTipFor(sim.body, k, now, sim.tentacles[k].seed);

      if (
        !sim.active &&
        playingRef.current &&
        stepRef.current < events.length
      ) {
        const k = stepRef.current % TENTACLE_COUNT;
        const tip = sim.tentacles[k].joints[SEGMENTS];
        sim.active = {
          eventIndex: stepRef.current,
          tentacle: k,
          phase: "reach",
          phaseStart: now,
          from: { ...tip },
          tip: { ...tip },
        };
      }

      const active = sim.active;
      if (active) {
        if (!playingRef.current) active.phaseStart += delta;
        const event = events[active.eventIndex];
        const elapsed = (now - active.phaseStart) * speedRef.current;

        if (active.phase === "reach") {
          const t = elapsed / TIMING_MS.reach;
          active.tip = lerpPoint(
            active.from,
            wordCenter(event.start, origin),
            easeInOutCubic(t),
          );
          if (t >= 1) {
            active.phase = "crawl";
            active.phaseStart = now;
          }
        } else if (active.phase === "crawl") {
          const words = event.end - event.start;
          const perWord = Math.min(
            TIMING_MS.crawlPerWord,
            TIMING_MS.crawlMax / words,
          );
          const position = elapsed / perWord;
          const offset = Math.min(Math.floor(position), words - 1);
          const next = Math.min(offset + 1, words - 1);
          active.tip = lerpPoint(
            wordCenter(event.start + offset, origin),
            wordCenter(event.start + next, origin),
            Math.min(position - offset, 1),
          );
          const end = event.start + offset + 1;
          if (end !== readingEnd) {
            readingEnd = end;
            setReading({ start: event.start, end });
          }
          if (position >= words) {
            active.phase = "decide";
            active.phaseStart = now;
            readingEnd = -1;
            stepRef.current = active.eventIndex + 1;
            setStep(stepRef.current);
            setReading(null);
          }
        } else if (active.phase === "decide") {
          const anchor = wordCenter(event.end - 1, origin);
          active.tip = {
            x: anchor.x + Math.sin(now / 40) * 1.5,
            y: anchor.y + Math.cos(now / 50) * 1.5,
          };
          if (elapsed >= TIMING_MS.decide) {
            active.phase = "retract";
            active.phaseStart = now;
            active.from = { ...active.tip };
          }
        } else {
          const t = elapsed / TIMING_MS.retract;
          active.tip = lerpPoint(
            active.from,
            restTip(active.tentacle),
            easeInOutCubic(t),
          );
          if (t >= 1) {
            sim.active = null;
            if (stepRef.current >= events.length) {
              playingRef.current = false;
              setPlaying(false);
            }
          }
        }
      }

      const focusY = sim.active ? sim.active.tip.y : origin.height / 2;
      const clampedY = Math.min(
        Math.max(focusY, BODY_RADIUS + 8),
        origin.height - BODY_RADIUS - 8,
      );
      sim.body.y += (clampedY - sim.body.y) * 0.05;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, origin.width, origin.height);

      sim.tentacles.forEach((tentacle, k) => {
        const grabbing = sim.active?.tentacle === k ? sim.active : null;
        const target = grabbing ? grabbing.tip : restTip(k);
        const base = anchorFor(sim.body, k);
        const total = tentacle.lengths.reduce((sum, l) => sum + l, 0);
        const desired =
          Math.hypot(target.x - base.x, target.y - base.y) * 1.04 + 18;
        const segment = (total + (desired - total) * 0.25) / SEGMENTS;
        tentacle.lengths.fill(segment);
        const span = Math.hypot(target.x - base.x, target.y - base.y) || 1;
        const normal = {
          x: -(target.y - base.y) / span,
          y: (target.x - base.x) / span,
        };
        const bulge = span * 0.15 * (k % 2 === 0 ? 1 : -1);
        for (let i = 1; i < SEGMENTS; i++) {
          const t = i / SEGMENTS;
          const arc = lerpPoint(base, target, t);
          const sag = Math.sin(Math.PI * t) * bulge;
          tentacle.joints[i] = lerpPoint(
            tentacle.joints[i],
            { x: arc.x + normal.x * sag, y: arc.y + normal.y * sag },
            0.3,
          );
        }
        tentacle.joints = solveFabrik(
          tentacle.joints,
          base,
          target,
          tentacle.lengths,
        );

        const points = tentacle.joints.map((joint, i) => {
          if (i === 0 || i === SEGMENTS) return joint;
          const prev = tentacle.joints[i - 1];
          const dx = joint.x - prev.x;
          const dy = joint.y - prev.y;
          const len = Math.hypot(dx, dy) || 1;
          const wave =
            Math.sin(now / 260 + i * 0.7 + tentacle.seed) *
            4 *
            Math.sin((Math.PI * i) / SEGMENTS);
          return {
            x: joint.x - (dy / len) * wave,
            y: joint.y + (dx / len) * wave,
          };
        });

        ctx.lineCap = "round";
        ctx.strokeStyle = palette.body;
        ctx.fillStyle = palette.eye;
        const mid = (a: Point, b: Point) => lerpPoint(a, b, 0.5);
        for (let i = 0; i < SEGMENTS; i++) {
          ctx.globalAlpha = 0.9;
          ctx.lineWidth = 10 * (1 - i / SEGMENTS) + 1.5;
          ctx.beginPath();
          const from = i === 0 ? points[0] : mid(points[i - 1], points[i]);
          const to =
            i === SEGMENTS - 1
              ? points[SEGMENTS]
              : mid(points[i], points[i + 1]);
          ctx.moveTo(from.x, from.y);
          ctx.quadraticCurveTo(points[i].x, points[i].y, to.x, to.y);
          ctx.stroke();
          if (i % 3 === 1 && i < SEGMENTS - 2) {
            ctx.globalAlpha = 0.45;
            ctx.beginPath();
            ctx.arc(
              points[i].x,
              points[i].y,
              2.2 * (1 - i / SEGMENTS) + 0.8,
              0,
              Math.PI * 2,
            );
            ctx.fill();
          }
        }

        if (grabbing && grabbing.phase === "decide") {
          const decision = events[grabbing.eventIndex].decision;
          ctx.globalAlpha = 0.35;
          ctx.fillStyle = palette.decision[decision];
          ctx.beginPath();
          ctx.arc(grabbing.tip.x, grabbing.tip.y, 12, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      ctx.globalAlpha = 1;
      ctx.fillStyle = palette.body;
      ctx.beginPath();
      for (let j = 0; j <= 24; j++) {
        const angle = (j / 24) * Math.PI * 2;
        const radius =
          BODY_RADIUS +
          Math.sin(angle * 3 + now / 400) * 2.5 +
          Math.sin(angle * 5 - now / 300) * 1.5;
        const x = sim.body.x + Math.cos(angle) * radius;
        const y = sim.body.y + Math.sin(angle) * radius;
        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fill();

      const look = sim.active ? sim.active.tip : restTip(1);
      const lookAngle = Math.atan2(look.y - sim.body.y, look.x - sim.body.x);
      const eye = {
        x: sim.body.x + Math.cos(lookAngle) * 4,
        y: sim.body.y + Math.sin(lookAngle) * 4,
      };
      ctx.fillStyle = palette.eye;
      ctx.beginPath();
      ctx.arc(eye.x, eye.y, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = palette.pupil;
      ctx.beginPath();
      ctx.arc(
        eye.x + Math.cos(lookAngle) * 3,
        eye.y + Math.sin(lookAngle) * 3,
        3.8,
        0,
        Math.PI * 2,
      );
      ctx.fill();

      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [events, reducedMotion]);

  const restart = () => {
    simRef.current.active = null;
    stepRef.current = 0;
    playingRef.current = !reducedMotion;
    setStep(0);
    setReading(null);
    setPlaying(!reducedMotion);
  };

  const skipToResult = () => {
    simRef.current.active = null;
    stepRef.current = events.length;
    playingRef.current = false;
    setStep(events.length);
    setReading(null);
    setPlaying(false);
  };

  const togglePlay = () => {
    if (done) {
      restart();
      return;
    }
    playingRef.current = !playingRef.current;
    setPlaying(playingRef.current);
  };

  const toggleSpeed = () => {
    speedRef.current = fast ? 1 : 2;
    setFast(!fast);
  };

  const wordClass = (index: number): string => {
    const state = states[index];
    if (
      state === "unread" &&
      reading &&
      index >= reading.start &&
      index < reading.end
    ) {
      return WORD_CLASS.reading;
    }
    return WORD_CLASS[state];
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section aria-label="Listing page" className="rounded-lg border bg-card">
        <div className="flex items-center justify-between gap-2 border-b px-4 py-2 text-xs text-muted-foreground">
          <span>{trace.source}</span>
          <span>
            {step} / {events.length} decisions
          </span>
        </div>
        <div ref={containerRef} className="relative py-4 pr-24 pl-5">
          <div className="space-y-2 text-sm leading-7">
            {paragraphs.map((paragraph) => (
              <p key={paragraph[0].index}>
                {paragraph.map((token) => (
                  <Fragment key={token.index}>
                    <span
                      ref={(element) => {
                        wordRefs.current[token.index] = element;
                      }}
                      data-state={states[token.index]}
                      className={cn(
                        "rounded px-0.5 transition-colors duration-300",
                        wordClass(token.index),
                      )}
                    >
                      {token.text}
                    </span>{" "}
                  </Fragment>
                ))}
              </p>
            ))}
          </div>
          {!reducedMotion && (
            <canvas
              ref={canvasRef}
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 h-full w-full"
            />
          )}
        </div>
      </section>

      <aside className="space-y-4">
        <div className="space-y-3 rounded-lg border bg-card p-4">
          <div className="flex flex-wrap gap-2">
            {reducedMotion ? (
              <Button onClick={skipToResult} disabled={done}>
                <FastForward />
                Show result
              </Button>
            ) : (
              <Button onClick={togglePlay}>
                {playing ? <Pause /> : <Play />}
                {playing ? "Pause" : done ? "Replay" : "Start crawl"}
              </Button>
            )}
            <Button variant="outline" onClick={restart}>
              <RotateCcw />
              Restart
            </Button>
            {!reducedMotion && (
              <>
                <Button
                  variant="outline"
                  onClick={skipToResult}
                  disabled={done}
                >
                  <FastForward />
                  Skip
                </Button>
                <Button
                  variant="ghost"
                  onClick={toggleSpeed}
                  aria-pressed={fast}
                >
                  {fast ? "2x" : "1x"}
                </Button>
              </>
            )}
          </div>
          {reducedMotion && (
            <p className="text-xs text-muted-foreground">
              Animation is off because your system prefers reduced motion.
            </p>
          )}
          <div className="flex flex-wrap gap-3 text-xs">
            {(Object.keys(DECISION_LABEL) as TraceDecision[]).map(
              (decision) => (
                <span key={decision} className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      "inline-block size-2.5 rounded-full",
                      DECISION_DOT[decision],
                    )}
                  />
                  {DECISION_LABEL[decision]}
                </span>
              ),
            )}
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-semibold">Extracted fields</h2>
          {fields.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Nothing extracted yet.
            </p>
          ) : (
            <dl className="mt-2 space-y-2 text-xs">
              {fields.map((field) => (
                <div key={field.field}>
                  <dt
                    className={cn(
                      "font-medium",
                      field.decision === "flagged" && "text-destructive",
                    )}
                  >
                    {field.field}
                  </dt>
                  <dd className="text-muted-foreground">{field.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        <div className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-semibold">Decision log</h2>
          <p className="sr-only" aria-live="polite">
            {latest
              ? `${DECISION_LABEL[latest.decision]}: ${latest.reason}`
              : ""}
          </p>
          {committed.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              No decisions yet.
            </p>
          ) : (
            <ol className="mt-2 max-h-72 space-y-2 overflow-y-auto text-xs">
              {[...committed].reverse().map((event) => (
                <li key={event.id} className="flex items-start gap-2">
                  <span
                    className={cn(
                      "shrink-0 rounded px-1.5 py-0.5 font-medium",
                      DECISION_BADGE[event.decision],
                    )}
                  >
                    {DECISION_LABEL[event.decision]}
                  </span>
                  <span className="text-muted-foreground">
                    {event.field ? `${event.field}: ` : ""}
                    {event.reason}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </aside>
    </div>
  );
}
