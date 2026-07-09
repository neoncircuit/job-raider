"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Target, CheckCircle2, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { discApi } from "@/lib/api/assessment";
import type { DISCQuestion, DISCAnswer, DISCResult } from "@/lib/types/api";

interface DISCAssessmentProps {
  onComplete?: (result: DISCResult) => void;
}

export function DISCAssessment({ onComplete }: DISCAssessmentProps) {
  const [currentStep, setCurrentStep] = useState<"intro" | "loading" | "assessment" | "submitting" | "complete">("intro");
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<DISCQuestion[]>([]);

  // Track answers: question_id -> { most_like: "A"|"B"|"C"|"D", least_like: "A"|"B"|"C"|"D" }
  const [answers, setAnswers] = useState<Record<string, { most_like?: string; least_like?: string }>>({});

  // Load existing profile query
  const { data: existingProfile } = useQuery({
    queryKey: ["disc-profile"],
    queryFn: async () => {
      try {
        return await discApi.getProfile();
      } catch {
        // 404 is expected if no profile exists yet
        return null;
      }
    },
  });

  // Start session mutation
  const startMutation = useMutation({
    mutationFn: async () => {
      setCurrentStep("loading");
      const session = await discApi.start();
      return session;
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

  // Submit mutation
  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!sessionId) throw new Error("No active session");

      // Convert answers to backend format
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
      return await discApi.submit({ session_id: sessionId, answers: discAnswers });
    },
    onSuccess: (result) => {
      setCurrentStep("complete");
      onComplete?.(result);
      toast.success("DISC assessment completed!");
    },
    onError: (error: Error) => {
      toast.error(`Failed to submit assessment: ${error.message}`);
      setCurrentStep("assessment");
    },
  });

  const handleStart = () => {
    startMutation.mutate();
  };

  const handleSelection = (questionId: string, type: "most_like" | "least_like", label: string) => {
    // Validate: can't select same option for both most and least
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
      toast.error("Please select both Most like you and Least like you before continuing");
      return;
    }

    // Move to next question or submit
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
    setCurrentStep("intro");
  };

  // Intro screen
  if (currentStep === "intro") {
    const hasExistingProfile = !!existingProfile;

    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Target className="h-4 w-4 text-indigo-600" />
            DISC Personality Assessment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <p className="text-sm text-gray-700">
              Discover your work style with our DISC personality assessment. Many job applications
              include similar assessments, so this helps you practice and understand your results.
            </p>
            <ul className="text-xs text-gray-600 space-y-1 ml-4 list-disc">
              <li>24 questions covering leadership, communication, work style, and problem-solving</li>
              <li>Most/Least format: choose which options are most and least like you</li>
              <li>Get job match recommendations based on your profile</li>
            </ul>
            <div className="rounded-md bg-indigo-50 p-3 text-xs text-indigo-800">
              <strong>Takes 5-8 minutes</strong> · Industry-standard format · No wrong answers
            </div>
            {hasExistingProfile && (
              <div className="rounded-md bg-green-50 p-3 text-xs text-green-800">
                ✓ You have a completed profile. Retake to update your results.
              </div>
            )}
            <Button
              onClick={handleStart}
              className="w-full"
              disabled={startMutation.isPending}
            >
              {startMutation.isPending ? "Loading..." : hasExistingProfile ? "Retake Assessment" : "Start Assessment"}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Loading screen
  if (currentStep === "loading") {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
            <p className="text-sm text-gray-600">Loading assessment...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Assessment screen
  if (currentStep === "assessment" || currentStep === "submitting") {
    const question = questions[currentQuestion];
    const answer = answers[question.id] || {};
    const progress = ((currentQuestion + 1) / questions.length) * 100;
    const isLastQuestion = currentQuestion === questions.length - 1;

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Target className="h-4 w-4 text-indigo-600" />
              Question {currentQuestion + 1} of {questions.length}
            </CardTitle>
            <button
              onClick={handleRetake}
              className="text-xs text-gray-400 hover:text-gray-600"
              disabled={currentStep === "submitting"}
            >
              Cancel
            </button>
          </div>
          <div className="h-1 w-full bg-gray-100 rounded-full mt-2">
            <div
              className="h-full bg-indigo-600 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {question.category.replace("_", " ")}
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm font-medium text-gray-900">{question.question}</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Most Like column */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-green-700 bg-green-50 px-3 py-1.5 rounded">
                  MOST like you
                </div>
                {question.options.map((option) => (
                  <button
                    key={option.label}
                    onClick={() => handleSelection(question.id, "most_like", option.label)}
                    disabled={currentStep === "submitting"}
                    className={`w-full text-left rounded-lg border px-4 py-3 text-sm transition-all ${
                      answer.most_like === option.label
                        ? "border-green-500 bg-green-50 text-green-900"
                        : "border-gray-200 text-gray-700 hover:border-green-300 hover:bg-green-50"
                    }`}
                  >
                    <span className="font-medium mr-2">{option.label}.</span>
                    {option.text}
                  </button>
                ))}
              </div>

              {/* Least Like column */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-red-700 bg-red-50 px-3 py-1.5 rounded">
                  LEAST like you
                </div>
                {question.options.map((option) => (
                  <button
                    key={option.label}
                    onClick={() => handleSelection(question.id, "least_like", option.label)}
                    disabled={currentStep === "submitting"}
                    className={`w-full text-left rounded-lg border px-4 py-3 text-sm transition-all ${
                      answer.least_like === option.label
                        ? "border-red-500 bg-red-50 text-red-900"
                        : "border-gray-200 text-gray-700 hover:border-red-300 hover:bg-red-50"
                    }`}
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
                disabled={!answer.most_like || !answer.least_like || currentStep === "submitting"}
                className="min-w-[100px]"
              >
                {currentStep === "submitting" ? (
                  "Submitting..."
                ) : isLastQuestion ? (
                  <>Submit Results <ChevronRight className="ml-1 h-4 w-4" /></>
                ) : (
                  <>Next <ChevronRight className="ml-1 h-4 w-4" /></>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Complete screen
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          Assessment Complete
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Your DISC personality profile has been calculated and saved.
          </p>

          {submitMutation.data && (
            <div className="space-y-3 mt-4">
              <div className="rounded-md bg-indigo-50 p-4">
                <h3 className="text-sm font-semibold text-indigo-900 mb-2">Your Profile</h3>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="font-medium">Dominance (D):</span>{" "}
                    {submitMutation.data.profile.D}%
                  </div>
                  <div>
                    <span className="font-medium">Influence (I):</span>{" "}
                    {submitMutation.data.profile.I}%
                  </div>
                  <div>
                    <span className="font-medium">Steadiness (S):</span>{" "}
                    {submitMutation.data.profile.S}%
                  </div>
                  <div>
                    <span className="font-medium">Conscientiousness (C):</span>{" "}
                    {submitMutation.data.profile.C}%
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-indigo-200">
                  <p className="text-xs text-indigo-800">
                    <strong>Primary Type:</strong> {submitMutation.data.primary_type}
                    {submitMutation.data.secondary_type && (
                      <span> · <strong>Secondary:</strong> {submitMutation.data.secondary_type}</span>
                    )}
                  </p>
                </div>
              </div>

              <div className="rounded-md bg-green-50 p-4">
                <h3 className="text-sm font-semibold text-green-900 mb-2">Top Job Matches</h3>
                <div className="space-y-2">
                  {submitMutation.data.job_matches.slice(0, 3).map((match) => (
                    <div key={match.job_type} className="flex justify-between items-center">
                      <span className="text-xs text-green-800">{match.job_type}</span>
                      <span className="text-xs font-semibold text-green-700">{match.match_score}%</span>
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
