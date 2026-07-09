"use client";

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { GraduationCap, Play, ChevronRight, RotateCcw, Trophy, Clock, CheckCircle2, XCircle } from "lucide-react";
import { assessmentApi } from "@/lib/api/assessment";
import type { AssessmentSession, DifficultyLevel } from "@/lib/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";
import { DISCAssessment } from "@/components/disc-assessment";
import { PageContainer } from "@/components/layout/PageContainer";

// ── Difficulty colors ────────────────────────────────────────────────────────

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: "bg-green-100 text-green-800",
  intermediate: "bg-blue-100 text-blue-800",
  advanced: "bg-orange-100 text-orange-800",
  expert: "bg-red-100 text-red-800",
};

const QUESTION_TYPE_COLORS: Record<string, string> = {
  conceptual: "bg-purple-100 text-purple-800",
  scenario: "bg-sky-100 text-sky-800",
  coding: "bg-emerald-100 text-emerald-800",
  system_design: "bg-amber-100 text-amber-800",
};

// ── Setup View ───────────────────────────────────────────────────────────────

function SetupView({ onStart, onStartDISC }: { onStart: (mode: "job_targeted" | "skill_based", skills: string[], difficulty: DifficultyLevel, count: number) => void; onStartDISC: () => void }) {
  const [mode, setMode] = useState<"job_targeted" | "skill_based">("skill_based");
  const [difficulty, setDifficulty] = useState<DifficultyLevel>("intermediate");
  const [count, setCount] = useState(5);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);

  const skillsQuery = assessmentApi.availableSkills;

  // Simple fetch for skills
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);
  useEffect(() => {
    skillsQuery().then((data) => setAvailableSkills(data.skills)).catch(() => {});
  }, [skillsQuery]);

  const toggleSkill = (skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  return (
    <PageContainer variant="form">
      <div className="text-center">
        <div className="inline-flex items-center justify-center h-16 w-16 rounded-full bg-indigo-100 mb-4">
          <GraduationCap className="h-8 w-8 text-indigo-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">Technical Assessment Trainer</h2>
        <p className="mt-1 text-sm text-gray-500">Practice technical questions tailored to your target roles and skills.</p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-3 justify-center">
        <button
          onClick={() => setMode("skill_based")}
          className={cn(
            "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            mode === "skill_based" ? "bg-indigo-600 text-white shadow-md" : "bg-white text-gray-600 border hover:bg-gray-50"
          )}
        >
          Practice by Skill
        </button>
        <button
          onClick={() => setMode("job_targeted")}
          className={cn(
            "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            mode === "job_targeted" ? "bg-indigo-600 text-white shadow-md" : "bg-white text-gray-600 border hover:bg-gray-50"
          )}
        >
          Target a Job
        </button>
        <button
          onClick={onStartDISC}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-purple-600 text-white border hover:bg-purple-700 shadow-md"
        >
          DISC Assessment
        </button>
      </div>

      {/* Skill picker */}
      <div>
        <Label className="mb-2 block">Select skills to practice</Label>
        <div className="flex flex-wrap gap-2">
          {availableSkills.map((skill) => (
            <button
              key={skill}
              onClick={() => toggleSkill(skill)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm transition-colors",
                selectedSkills.includes(skill) ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              {skill}
            </button>
          ))}
        </div>
      </div>

      {/* Difficulty */}
      <div>
        <Label className="mb-2 block">Difficulty</Label>
        <div className="flex gap-2">
          {(["beginner", "intermediate", "advanced", "expert"] as DifficultyLevel[]).map((d) => (
            <button
              key={d}
              onClick={() => setDifficulty(d)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm capitalize transition-colors",
                difficulty === d ? DIFFICULTY_COLORS[d] : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              )}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Question count */}
      <div>
        <Label className="mb-2 block">Questions: {count}</Label>
        <input
          type="range"
          min={3}
          max={15}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          className="w-full accent-indigo-600"
        />
      </div>

      <Button onClick={() => onStart(mode, selectedSkills, difficulty, count)} className="w-full" size="lg">
        <Play className="mr-2 h-4 w-4" />
        Start Assessment
      </Button>
    </PageContainer>
  );
}

// ── Active Session View ──────────────────────────────────────────────────────

function SessionView({
  session,
  onSubmitAnswer,
  onNextQuestions,
  onComplete,
  onBack,
}: {
  session: AssessmentSession;
  onSubmitAnswer: (questionId: string, answer: { selected_option?: string; freeform_text?: string }) => void;
  onNextQuestions: () => void;
  onComplete: () => void;
  onBack: () => void;
}) {
  const answeredIds = new Set(session.answers.map((a) => a.question_id));
  const currentQuestion = session.questions.find((q) => !answeredIds.has(q.question_id));
  const lastScore = session.scores.length > 0 ? session.scores[session.scores.length - 1] : null;

  const [freeformAnswer, setFreeformAnswer] = useState("");
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [showingFeedback, setShowingFeedback] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFreeformAnswer(prev => prev !== "" ? "" : prev);
    setSelectedOption(prev => prev !== null ? null : prev);
    setShowingFeedback(prev => prev !== false ? false : prev);
  }, [currentQuestion?.question_id]);

  if (!currentQuestion) {
    return (
      <div className="text-center space-y-4 py-8">
        <Trophy className="h-12 w-12 mx-auto text-amber-500" />
        <h3 className="text-lg font-semibold">All questions answered!</h3>
        <p className="text-sm text-gray-500">
          {session.overall_score !== null ? `Final score: ${session.overall_score}/100` : "Review your results or generate more questions."}
        </p>
        <div className="flex gap-3 justify-center">
          <Button onClick={onNextQuestions} variant="outline">More Questions</Button>
          <Button onClick={onComplete}>Finish Session</Button>
        </div>
        <Button variant="ghost" onClick={onBack} className="text-gray-400">Back to Setup</Button>
      </div>
    );
  }

  const questionIdx = session.answers.length;
  const total = session.questions.length;

  return (
    <div className="space-y-4">
      {/* Progress */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm">Exit</button>
        <div className="flex-1">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Question {questionIdx + 1} of {total}</span>
            <Badge className={cn("text-[10px]", DIFFICULTY_COLORS[session.current_difficulty])}>{session.current_difficulty}</Badge>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full">
            <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${(questionIdx / total) * 100}%` }} />
          </div>
        </div>
      </div>

      {/* Feedback from previous answer */}
      {showingFeedback && lastScore && (
        <Card className={cn("border-2", lastScore.score >= 80 ? "border-green-300 bg-green-50" : lastScore.score >= 50 ? "border-yellow-300 bg-yellow-50" : "border-red-300 bg-red-50")}>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              {lastScore.is_correct === true && <CheckCircle2 className="h-5 w-5 text-green-600" />}
              {lastScore.is_correct === false && <XCircle className="h-5 w-5 text-red-600" />}
              <span className="font-semibold text-lg">{lastScore.score}/100</span>
            </div>
            <p className="text-sm text-gray-700">{lastScore.feedback}</p>
            {lastScore.improvements.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-amber-700 mb-1">Improvements</p>
                <ul className="text-xs text-gray-600 space-y-0.5">
                  {lastScore.improvements.map((s, i) => <li key={i}>- {s}</li>)}
                </ul>
              </div>
            )}
            {lastScore.model_answer && (
              <details className="text-xs">
                <summary className="cursor-pointer font-medium text-gray-700">Model Answer</summary>
                <p className="mt-1 text-gray-600 whitespace-pre-line">{lastScore.model_answer}</p>
              </details>
            )}
            <Button size="sm" className="w-full" onClick={() => setShowingFeedback(false)}>
              Next Question <ChevronRight className="ml-1 h-3 w-3" />
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Question card */}
      {!showingFeedback && (
        <Card>
          <CardContent className="p-5 space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge className={cn("text-xs", QUESTION_TYPE_COLORS[currentQuestion.question_type])}>
                {currentQuestion.question_type.replace("_", " ")}
              </Badge>
              <Badge variant="outline" className="text-xs">{currentQuestion.topic}</Badge>
              {currentQuestion.time_limit_seconds && (
                <Badge variant="outline" className="text-xs"><Clock className="mr-1 h-3 w-3" />{currentQuestion.time_limit_seconds}s</Badge>
              )}
            </div>

            <p className="text-base font-medium text-gray-900 leading-relaxed">{currentQuestion.question_text}</p>

            {currentQuestion.answer_format === "multiple_choice" && currentQuestion.options.length > 0 && (
              <div className="space-y-2">
                {currentQuestion.options.map((opt) => (
                  <button
                    key={opt.label}
                    onClick={() => setSelectedOption(opt.label)}
                    className={cn(
                      "w-full text-left rounded-lg border p-3 transition-colors",
                      selectedOption === opt.label ? "border-indigo-500 bg-indigo-50" : "border-gray-200 hover:border-gray-300"
                    )}
                  >
                    <span className="font-medium mr-2">{opt.label}.</span>
                    <span className="text-sm">{opt.text}</span>
                  </button>
                ))}
              </div>
            )}

            {currentQuestion.answer_format === "freeform" && (
              <textarea
                value={freeformAnswer}
                onChange={(e) => setFreeformAnswer(e.target.value)}
                placeholder="Type your answer here..."
                className="w-full min-h-[120px] rounded-lg border border-gray-200 p-3 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-y"
              />
            )}

            <Button
              onClick={() => {
                if (currentQuestion.answer_format === "multiple_choice") {
                  if (!selectedOption) { toast.error("Select an answer"); return; }
                  onSubmitAnswer(currentQuestion.question_id, { selected_option: selectedOption });
                } else {
                  if (!freeformAnswer.trim()) { toast.error("Write your answer"); return; }
                  onSubmitAnswer(currentQuestion.question_id, { freeform_text: freeformAnswer });
                }
                setShowingFeedback(true);
              }}
              className="w-full"
              disabled={currentQuestion.answer_format === "multiple_choice" ? !selectedOption : !freeformAnswer.trim()}
            >
              Submit Answer
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Results View ─────────────────────────────────────────────────────────────

function ResultsView({ session, onNewSession }: { session: AssessmentSession; onNewSession: () => void }) {
  return (
    <PageContainer variant="form">
      <div className="text-center">
        <div className={cn(
          "inline-flex items-center justify-center h-20 w-20 rounded-full mb-4",
          (session.overall_score ?? 0) >= 80 ? "bg-green-100" : (session.overall_score ?? 0) >= 50 ? "bg-yellow-100" : "bg-red-100"
        )}>
          <span className={cn(
            "text-2xl font-bold",
            (session.overall_score ?? 0) >= 80 ? "text-green-700" : (session.overall_score ?? 0) >= 50 ? "text-yellow-700" : "text-red-700"
          )}>
            {session.overall_score ?? 0}
          </span>
        </div>
        <h2 className="text-xl font-bold">Session Complete</h2>
        <p className="text-sm text-gray-500">
          {session.questions.length} questions | {session.mode === "job_targeted" ? "Job-Targeted" : "Skill-Based"} | {session.difficulty}
        </p>
      </div>

      {Object.keys(session.topic_breakdown).length > 0 && (
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Topic Breakdown</p>
            <div className="space-y-2">
              {Object.entries(session.topic_breakdown).map(([topic, score]) => (
                <div key={topic} className="flex items-center gap-3">
                  <span className="text-sm text-gray-700 w-40 truncate">{topic}</span>
                  <div className="flex-1 h-2 bg-gray-200 rounded-full">
                    <div
                      className={cn("h-full rounded-full", score >= 80 ? "bg-green-500" : score >= 50 ? "bg-yellow-500" : "bg-red-500")}
                      style={{ width: `${score}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium w-10 text-right">{score}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-4 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Question Review</p>
          {session.questions.map((q) => {
            const score = session.scores.find((s) => s.question_id === q.question_id);
            return (
              <details key={q.question_id} className="border rounded-lg">
                <summary className="px-3 py-2 cursor-pointer flex items-center gap-2">
                  <Badge className={cn("text-[10px]", QUESTION_TYPE_COLORS[q.question_type])}>{q.question_type.replace("_", " ")}</Badge>
                  <span className="text-sm text-gray-700 truncate flex-1">{q.question_text}</span>
                  {score && (
                    <span className={cn("text-xs font-bold", score.score >= 80 ? "text-green-600" : score.score >= 50 ? "text-yellow-600" : "text-red-600")}>
                      {score.score}
                    </span>
                  )}
                </summary>
                {score && (
                  <div className="px-3 pb-3 space-y-2 text-sm">
                    <p className="text-gray-600">{score.feedback}</p>
                    {score.model_answer && (
                      <div className="bg-gray-50 rounded-md p-2">
                        <p className="text-xs font-medium text-gray-500 mb-1">Model Answer</p>
                        <p className="text-gray-700 whitespace-pre-line">{score.model_answer}</p>
                      </div>
                    )}
                  </div>
                )}
              </details>
            );
          })}
        </CardContent>
      </Card>

      <Button onClick={onNewSession} className="w-full" size="lg">
        <RotateCcw className="mr-2 h-4 w-4" />Start New Session
      </Button>
    </PageContainer>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

type PageView = "setup" | "session" | "results" | "disc";

export default function AssessmentPage() {
  const [view, setView] = useState<PageView>("setup");
  const [session, setSession] = useState<AssessmentSession | null>(null);

  const startMutation = useMutation({
    mutationFn: assessmentApi.start,
    onSuccess: (data) => { setSession(data); setView("session"); },
    onError: () => toast.error("Failed to start session. Is the backend running?"),
  });

  const answerMutation = useMutation({
    mutationFn: ({ sessionId, answer }: { sessionId: string; answer: { question_id: string; selected_option?: string; freeform_text?: string } }) =>
      assessmentApi.submitAnswer(sessionId, answer),
    onSuccess: (data) => {
      if (session) {
        setSession({
          ...session,
          scores: [...session.scores, data.score],
          answers: [...session.answers, { question_id: data.score.question_id, answered_at: new Date().toISOString() }],
          status: data.session_completed ? "completed" : "in_progress",
          overall_score: data.overall_score ?? null,
        });
        if (data.session_completed) setView("results");
      }
    },
    onError: () => toast.error("Failed to submit answer"),
  });

  const nextMutation = useMutation({
    mutationFn: (id: string) => assessmentApi.nextQuestions(id),
    onSuccess: (data) => setSession(data),
    onError: () => toast.error("Failed to generate more questions"),
  });

  const completeMutation = useMutation({
    mutationFn: (id: string) => assessmentApi.complete(id),
    onSuccess: (data) => { setSession(data); setView("results"); },
    onError: () => toast.error("Failed to complete session"),
  });

  const handleStart = (mode: "job_targeted" | "skill_based", skills: string[], difficulty: DifficultyLevel, count: number) => {
    startMutation.mutate({ mode, target_skills: skills, difficulty, question_count: count });
  };

  const handleStartDISC = () => { setView("disc"); };

  const handleBack = () => { setSession(null); setView("setup"); };

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Assessment Trainer</h1>
        <p className="mt-0.5 text-sm text-gray-500">Practice technical questions to prepare for interviews.</p>
      </div>

      {view === "setup" && <SetupView onStart={handleStart} onStartDISC={handleStartDISC} />}
      {view === "disc" && (
        <div className="flex justify-center">
          <DISCAssessment onComplete={() => setView("setup")} />
        </div>
      )}
      {view === "session" && session && (
        <SessionView
          session={session}
          onSubmitAnswer={(questionId, answer) => answerMutation.mutate({ sessionId: session.session_id, answer: { question_id: questionId, ...answer } })}
          onNextQuestions={() => nextMutation.mutate(session.session_id)}
          onComplete={() => completeMutation.mutate(session.session_id)}
          onBack={handleBack}
        />
      )}
      {view === "results" && session && <ResultsView session={session} onNewSession={handleBack} />}
    </div>
  );
}
