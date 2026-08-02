"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Target, CheckCircle2, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { discApi } from "@/lib/api/assessment";
import type {
  DISCAnswer,
  DISCQuestion,
  DISCResult,
  DISCTrait,
} from "@/lib/types/api";
import { cn } from "@/lib/utils/cn";

interface DISCAssessmentProps {
  onComplete?: (result: DISCResult) => void;
}

const TRAIT_LABELS: Record<DISCTrait, string> = {
  D: "Dominance",
  I: "Influence",
  S: "Steadiness",
  C: "Conscientiousness",
};

const TRAIT_ORDER: DISCTrait[] = ["D", "I", "S", "C"];

/**
 * Format a DISC category slug for display.
 *
 * @param category - Category id such as ``work_style``.
 * @returns Human-readable category label.
 */
function formatCategory(category: string): string {
  return category.replaceAll("_", " ");
}

/**
 * Format a primary/secondary trait letter for results.
 *
 * @param trait - DISC letter code.
 * @returns Label like ``Dominance (D)``.
 */
function formatTrait(trait: DISCTrait): string {
  return `${TRAIT_LABELS[trait]} (${trait})`;
}

/**
 * DISC workplace-style assessment flow (intro → questions → results).
 *
 * @param onComplete - Optional callback after a successful submit.
 */
export function DISCAssessment({ onComplete }: DISCAssessmentProps) {
  const queryClient = useQueryClient();
  const [currentStep, setCurrentStep] = useState<
    "intro" | "loading" | "assessment" | "submitting" | "complete"
  >("intro");
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<DISCQuestion[]>([]);

  // Track answers: question_id -> { most_like, least_like }
  const [answers, setAnswers] = useState<
    Record<string, { most_like?: string; least_like?: string }>
  >({});

  const { data: existingProfile } = useQuery({
    queryKey: ["disc-profile"],
    queryFn: async () => {
      try {
        return await discApi.getProfile();
      } catch {
        return null;
      }
    },
  });

  const startMutation = useMutation({
    mutationFn: async () => {
      setCurrentStep("loading");
      return await discApi.start();
    },
    onSuccess: (session) => {
      setSessionId(session.session_id);
      setQuestions(session.questions);
      setCurrentStep("assessment");
    },
    onError: (error: Error) => {
      toast.error(`Failed to start assessment: ${error.message}`);
      setCurrentStep("intro");
    },
  });

  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!sessionId) throw new Error("No active session");

      const discAnswers: DISCAnswer[] = questions.map((q) => {
        const answer = answers[q.id];
        if (!answer?.most_like || !answer?.least_like) {
          throw new Error(`Missing answer for question ${q.id}`);
        }
        return {
          question_id: q.id,
          most_like: answer.most_like,
          least_like: answer.least_like,
          answered_at: new Date().toISOString(),
        };
      });

      setCurrentStep("submitting");
      return await discApi.submit({
        session_id: sessionId,
        answers: discAnswers,
      });
    },
    onSuccess: (result) => {
      setCurrentStep("complete");
      void queryClient.invalidateQueries({ queryKey: ["disc-profile"] });
      onComplete?.(result);
      toast.success("DISC assessment completed");
    },
    onError: (error: Error) => {
      toast.error(`Failed to submit assessment: ${error.message}`);
      setCurrentStep("assessment");
    },
  });

  const handleStart = () => {
    startMutation.mutate();
  };

  const handleSelection = (
    questionId: string,
    type: "most_like" | "least_like",
    label: string,
  ) => {
    const currentAnswer = answers[questionId] || {};
    const otherType = type === "most_like" ? "least_like" : "most_like";

    if (currentAnswer[otherType] === label) {
      toast.error("You cannot select the same option for both Most and Least");
      return;
    }

    setAnswers((prev) => ({
      ...prev,
      [questionId]: {
        ...prev[questionId],
        [type]: label,
      },
    }));
  };

  const handleNext = () => {
    const question = questions[currentQuestion];
    const answer = answers[question.id];

    if (!answer?.most_like || !answer?.least_like) {
      toast.error(
        "Please select both Most like you and Least like you before continuing",
      );
      return;
    }

    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
    } else {
      submitMutation.mutate();
    }
  };

  const handleBack = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(currentQuestion - 1);
    }
  };

  const handleRetake = () => {
    setAnswers({});
    setCurrentQuestion(0);
    setSessionId(null);
    setQuestions([]);
    setCurrentStep("intro");
  };

  if (currentStep === "intro") {
    const hasExistingProfile = !!existingProfile;

    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Target className="h-4 w-4 text-primary" />
            DISC Work Style Assessment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <p className="text-sm text-foreground">
              Practice a workplace DISC-style screen: Dominance, Influence,
              Steadiness, and Conscientiousness. Many employers use similar
              Most/Least formats. This is work-style practice, not a full
              personality inventory.
            </p>
            <ul className="text-xs text-muted-foreground space-y-1 ml-4 list-disc">
              <li>
                24 questions across leadership, communication, work style, and
                problem-solving
              </li>
              <li>
                Most/Least format: pick which option is most and least like you
              </li>
              <li>
                See your D/I/S/C mix and heuristic job-type match suggestions
              </li>
            </ul>
            <div className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
              <strong className="text-foreground">Takes 5-8 minutes</strong> ·
              Fixed question bank · No wrong answers · Results are relative to
              this attempt
            </div>
            {hasExistingProfile && (
              <div className="rounded-md border border-border bg-card p-3 text-xs text-foreground">
                You already have a saved profile. Retake to update your results.
              </div>
            )}
            <Button
              onClick={handleStart}
              className="w-full"
              disabled={startMutation.isPending}
            >
              {startMutation.isPending
                ? "Loading..."
                : hasExistingProfile
                  ? "Retake Assessment"
                  : "Start Assessment"}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (currentStep === "loading") {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">
              Loading assessment...
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (currentStep === "assessment" || currentStep === "submitting") {
    const question = questions[currentQuestion];
    const answer = answers[question.id] || {};
    const progress = ((currentQuestion + 1) / questions.length) * 100;
    const isLastQuestion = currentQuestion === questions.length - 1;
    const answeredCount = Object.values(answers).filter(
      (a) => a.most_like && a.least_like,
    ).length;

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Target className="h-4 w-4 text-primary" />
              Question {currentQuestion + 1} of {questions.length}
            </CardTitle>
            <button
              type="button"
              onClick={handleRetake}
              className="text-xs text-muted-foreground hover:text-foreground"
              disabled={currentStep === "submitting"}
            >
              Cancel
            </button>
          </div>
          <div className="h-1 w-full bg-muted rounded-full mt-2">
            <div
              className="h-full bg-primary rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span className="capitalize">
              {formatCategory(question.category)}
            </span>
            <span>
              {answeredCount} of {questions.length} answered
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm font-medium text-foreground">
              {question.question}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="text-xs font-semibold text-foreground bg-muted px-3 py-1.5 rounded border border-border">
                  MOST like you
                </div>
                {question.options.map((option) => (
                  <button
                    key={`most-${option.label}`}
                    type="button"
                    onClick={() =>
                      handleSelection(question.id, "most_like", option.label)
                    }
                    disabled={currentStep === "submitting"}
                    className={cn(
                      "w-full text-left rounded-lg border px-4 py-3 text-sm transition-all",
                      answer.most_like === option.label
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border text-foreground hover:border-primary/50 hover:bg-muted/60",
                    )}
                  >
                    <span className="font-medium mr-2">{option.label}.</span>
                    {option.text}
                  </button>
                ))}
              </div>

              <div className="space-y-2">
                <div className="text-xs font-semibold text-foreground bg-muted px-3 py-1.5 rounded border border-border">
                  LEAST like you
                </div>
                {question.options.map((option) => (
                  <button
                    key={`least-${option.label}`}
                    type="button"
                    onClick={() =>
                      handleSelection(question.id, "least_like", option.label)
                    }
                    disabled={currentStep === "submitting"}
                    className={cn(
                      "w-full text-left rounded-lg border px-4 py-3 text-sm transition-all",
                      answer.least_like === option.label
                        ? "border-destructive bg-destructive/10 text-foreground"
                        : "border-border text-foreground hover:border-destructive/40 hover:bg-muted/60",
                    )}
                  >
                    <span className="font-medium mr-2">{option.label}.</span>
                    {option.text}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-between pt-2">
              <Button
                variant="outline"
                onClick={handleBack}
                disabled={currentQuestion === 0 || currentStep === "submitting"}
              >
                Back
              </Button>
              <Button
                onClick={handleNext}
                disabled={
                  !answer.most_like ||
                  !answer.least_like ||
                  currentStep === "submitting"
                }
                className="min-w-[100px]"
              >
                {currentStep === "submitting" ? (
                  "Submitting..."
                ) : isLastQuestion ? (
                  <>
                    Submit Results <ChevronRight className="ml-1 h-4 w-4" />
                  </>
                ) : (
                  <>
                    Next <ChevronRight className="ml-1 h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const result = submitMutation.data;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-4 w-4 text-primary" />
          Assessment Complete
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Your DISC work-style profile is saved. Percentages are relative to
            this attempt and are for practice, not a clinical reading.
          </p>

          {result && (
            <div className="space-y-3 mt-4">
              <div className="rounded-md border border-border bg-muted/40 p-4">
                <h3 className="text-sm font-semibold text-foreground mb-3">
                  Your Profile
                </h3>
                <div className="space-y-2">
                  {TRAIT_ORDER.map((trait) => {
                    const value = result.profile[trait] ?? 0;
                    return (
                      <div key={trait} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="font-medium text-foreground">
                            {TRAIT_LABELS[trait]} ({trait})
                          </span>
                          <span className="text-muted-foreground">
                            {value}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-muted">
                          <div
                            className="h-1.5 rounded-full bg-primary transition-all"
                            style={{
                              width: `${Math.min(Math.max(value, 0), 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-foreground">
                    <strong>Primary:</strong> {formatTrait(result.primary_type)}
                    {result.secondary_type ? (
                      <span>
                        {" "}
                        · <strong>Secondary:</strong>{" "}
                        {formatTrait(result.secondary_type)}
                      </span>
                    ) : null}
                  </p>
                </div>
              </div>

              <div className="rounded-md border border-border bg-card p-4">
                <h3 className="text-sm font-semibold text-foreground mb-1">
                  Suggested job-type matches
                </h3>
                <p className="text-xs text-muted-foreground mb-3">
                  Heuristic fits against static role archetypes — directional,
                  not live job rankings.
                </p>
                <div className="space-y-3">
                  {result.job_matches.slice(0, 3).map((match) => (
                    <div key={match.job_type} className="space-y-0.5">
                      <div className="flex justify-between items-center gap-2">
                        <span className="text-xs font-medium text-foreground">
                          {match.job_type}
                        </span>
                        <span className="text-xs font-semibold text-primary shrink-0">
                          {match.match_score}%
                        </span>
                      </div>
                      {match.description ? (
                        <p className="text-xs text-muted-foreground">
                          {match.description}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <Button variant="outline" onClick={handleRetake} className="w-full">
            Retake Assessment
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
