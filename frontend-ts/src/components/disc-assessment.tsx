"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Target, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

// DISC Question type
interface DISCQuestion {
  id: string;
  question: string;
  options: { label: string; scores: { D: number; I: number; S: number; C: number } }[];
}

// DISC questions covering different aspects
const DISC_QUESTIONS: DISCQuestion[] = [
  {
    id: "q1",
    question: "In team meetings, I usually...",
    options: [
      { label: "Take charge and drive the discussion", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Energetically share ideas and opinions", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Listen carefully and support others", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Analyze the details and logic", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q2",
    question: "When facing a problem, I prefer to...",
    options: [
      { label: "Take immediate action to solve it", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Brainstorm with others for ideas", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Maintain stability and consensus", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Research and analyze all options", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q3",
    question: "My communication style is typically...",
    options: [
      { label: "Direct and to the point", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Enthusiastic and expressive", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Patient and supportive", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Precise and factual", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q4",
    question: "When working on deadlines, I...",
    options: [
      { label: "Push hard to get results fast", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Stay motivated and energized", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Work steadily to avoid stress", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Plan carefully and track progress", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q5",
    question: "In group projects, I naturally...",
    options: [
      { label: "Step into leadership roles", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Keep the energy and morale high", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Help everyone work together", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Ensure quality and accuracy", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q6",
    question: "When receiving feedback, I tend to...",
    options: [
      { label: "Want to get straight to the point", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Appreciate the recognition", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Take it personally but work on it", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Analyze the specifics carefully", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q7",
    question: "My ideal work environment is...",
    options: [
      { label: "Fast-paced and competitive", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Social and collaborative", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Stable and predictable", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Structured and detailed", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
  {
    id: "q8",
    question: "When making decisions, I...",
    options: [
      { label: "Go with my gut instinct", scores: { D: 3, I: 0, S: 0, C: 0 } },
      { label: "Consider how it affects people", scores: { D: 0, I: 3, S: 0, C: 0 } },
      { label: "Think about team harmony", scores: { D: 0, I: 0, S: 3, C: 0 } },
      { label: "Need all the facts first", scores: { D: 0, I: 0, S: 0, C: 3 } },
    ],
  },
];

interface DISCResult {
  dominance: number;
  influence: number;
  steadiness: number;
  conscientiousness: number;
}

interface DISCAssessmentProps {
  onComplete: (result: DISCResult) => void;
  existingResult?: DISCResult | null;
}

export function DISCAssessment({ onComplete, existingResult }: DISCAssessmentProps) {
  const [currentStep, setCurrentStep] = useState<"intro" | "assessment" | "complete">(
    existingResult ? "complete" : "intro"
  );
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const handleStart = () => setCurrentStep("assessment");

  const handleAnswer = (questionId: string, optionIndex: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: optionIndex }));

    // Move to next question or complete
    const questionIndex = DISC_QUESTIONS.findIndex((q) => q.id === questionId);
    if (questionIndex < DISC_QUESTIONS.length - 1) {
      setCurrentQuestion(questionIndex + 1);
    } else {
      calculateResults();
    }
  };

  const calculateResults = () => {
    let D = 0, I = 0, S = 0, C = 0;

    Object.entries(answers).forEach(([questionId, optionIndex]) => {
      const question = DISC_QUESTIONS.find((q) => q.id === questionId);
      const idx = parseInt(optionIndex);
      if (question && question.options[idx]) {
        D += question.options[idx].scores.D;
        I += question.options[idx].scores.I;
        S += question.options[idx].scores.S;
        C += question.options[idx].scores.C;
      }
    });

    // Normalize to percentages
    const total = D + I + S + C;
    const result: DISCResult = {
      dominance: Math.round((D / total) * 100),
      influence: Math.round((I / total) * 100),
      steadiness: Math.round((S / total) * 100),
      conscientiousness: Math.round((C / total) * 100),
    };

    setCurrentStep("complete");
    onComplete(result);
    toast.success("DISC assessment completed!");
  };

  const handleRetake = () => {
    setAnswers({});
    setCurrentQuestion(0);
    setCurrentStep("intro");
  };

  // Intro screen
  if (currentStep === "intro") {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Target className="h-4 w-4 text-indigo-600" />
            Working Style Assessment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <p className="text-sm text-gray-700">
              Discover your work style with our quick DISC assessment. Understanding your style helps with:
            </p>
            <ul className="text-xs text-gray-600 space-y-1 ml-4 list-disc">
              <li>Finding roles that match your strengths</li>
              <li>Understanding your communication style</li>
              <li>Building better team relationships</li>
            </ul>
            <div className="rounded-md bg-indigo-50 p-3 text-xs text-indigo-800">
              <strong>Takes 2-3 minutes</strong> · 8 questions · No wrong answers
            </div>
            <Button onClick={handleStart} className="w-full">
              Start Assessment
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Assessment screen
  if (currentStep === "assessment") {
    const question = DISC_QUESTIONS[currentQuestion];
    const progress = ((currentQuestion + 1) / DISC_QUESTIONS.length) * 100;

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Target className="h-4 w-4 text-indigo-600" />
              Question {currentQuestion + 1} of {DISC_QUESTIONS.length}
            </CardTitle>
            <button
              onClick={handleRetake}
              className="text-xs text-gray-400 hover:text-gray-600"
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
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm font-medium text-gray-900">{question.question}</p>
            <div className="space-y-2">
              {question.options.map((option, idx) => (
                <button
                  key={idx}
                  onClick={() => handleAnswer(question.id, idx.toString())}
                  className="w-full text-left rounded-lg border border-gray-200 px-4 py-3 text-sm text-gray-700 transition-colors hover:border-indigo-300 hover:bg-indigo-50"
                >
                  {option.label}
                </button>
              ))}
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
            Your working style profile has been calculated and saved.
          </p>
          <div className="rounded-md bg-green-50 p-3 text-xs text-green-800">
            ✓ Results displayed in your Strength Assessment
          </div>
          <Button variant="outline" onClick={handleRetake} className="w-full">
            Retake Assessment
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
