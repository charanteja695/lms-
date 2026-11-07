import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  usePrepareAttemptMutation,
  useStartAttemptMutation,
  useResumeAttemptMutation,
  useSaveAnswerMutation,
  useSubmitAttemptMutation,
  useLazyGetResultQuery,
} from "@/modules/assessments/attempts/api/attemptsApi";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { Icon, PageLoader } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import { AssessmentErrorBoundary } from "./AssessmentErrorBoundary";

export interface QuestionOption {
  id: string;
  text: string;
}

export interface LoadedQuestion {
  question_id: string;
  position: number;
  question_type: string;
  text: string;
  marks: number;
  codeSnippet?: string;
  options: QuestionOption[];
  selectedOptionId?: string;
}

interface StudentAssessmentRunnerProps {
  testId?: string | null;
  testTitle?: string;
  courseId: string;
  courseTitle: string;
  contextTitle: string;
  contextType: "chapter" | "module";
  parentModuleId?: string;
  passMarkPercent?: number;
  onTestPassed?: () => void;
  returnUrl?: string;
}

export function StudentAssessmentRunner({
  testId,
  testTitle,
  courseId,
  courseTitle,
  contextTitle,
  contextType,
  parentModuleId,
  passMarkPercent = 70,
  onTestPassed,
  returnUrl,
}: StudentAssessmentRunnerProps) {
  const navigate = useNavigate();
  const notify = useNotify();
  const finalReturnUrl = returnUrl || `/courses/${courseId}/learn`;

  const [prepareAttempt, { isLoading: isPreparingAttempt }] = usePrepareAttemptMutation();
  const [startAttempt, { isLoading: isStartingAttempt }] = useStartAttemptMutation();
  const [resumeAttempt] = useResumeAttemptMutation();
  const [saveAnswerMutation] = useSaveAnswerMutation();
  const [submitAttemptMutation, { isLoading: isSubmittingAttempt }] = useSubmitAttemptMutation();
  const [fetchResult] = useLazyGetResultQuery();

  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<LoadedQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [markedForReview, setMarkedForReview] = useState<string[]>([]);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{
    score: number;
    totalMarks: number;
    pct: number;
    passed: boolean;
  } | null>(null);

  const [isConfirmSubmitOpen, setIsConfirmSubmitOpen] = useState(false);
  const [isExitModalOpen, setIsExitModalOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [resultFetchError, setResultFetchError] = useState<string | null>(null);
  const [isFetchingResult, setIsFetchingResult] = useState(false);
  const hasInitializedRef = useRef<string | null>(null);

  // 1. Initialize or resume attempt against the server
  useEffect(() => {
    if (!testId) {
      setIsInitializing(false);
      return;
    }
    if (hasInitializedRef.current === testId) return;
    hasInitializedRef.current = testId;

    async function initTest() {
      setIsInitializing(true);
      try {
        setLoadError(null);
        // Prepare/fetch attempt from assessment service
        const prepRes = await prepareAttempt({ testId: String(testId), startNow: true }).unwrap();
        const currentAttempt = prepRes.attempt;
        if (!currentAttempt?.attempt_id) {
          setLoadError("Could not initialize assessment attempt.");
          return;
        }
        setAttemptId(currentAttempt.attempt_id);

        // Start or resume to fetch paper with real approved questions and server remaining time
        let paper;
        try {
          paper = await startAttempt(currentAttempt.attempt_id).unwrap();
        } catch {
          paper = await resumeAttempt(currentAttempt.attempt_id).unwrap();
        }

        const durationSec =
          paper.attempt?.remaining_seconds ?? currentAttempt.remaining_seconds ?? 15 * 60;
        setSecondsRemaining(durationSec);

        // Map real questions from question bank
        const mappedQuestions: LoadedQuestion[] = (paper.questions ?? []).map((q: any, idx: number) => {
          let opts: QuestionOption[] = [];
          if (q.body?.options && Array.isArray(q.body.options)) {
            opts = q.body.options.map((o: any) => ({
              id: String(o.id ?? o.key ?? ""),
              text: String(o.text ?? o.label ?? o.value ?? ""),
            }));
          }

          let codeSnippet = q.body?.code || q.code || undefined;
          let questionText = q.text || "Assessment Question";

          // If question text has markdown code block, extract code snippet
          const codeBlockMatch = questionText.match(/```(?:[a-zA-Z]*)\n([\s\S]*?)```/);
          if (codeBlockMatch) {
            codeSnippet = codeBlockMatch[1];
            questionText = questionText.replace(/```(?:[a-zA-Z]*)\n[\s\S]*?```/, "").trim();
          }

          return {
            question_id: String(q.question_id),
            position: q.position || idx + 1,
            question_type: q.question_type || "mcq_single",
            text: questionText,
            marks: q.marks || 10,
            codeSnippet,
            options: opts,
            selectedOptionId: q.answer?.response?.selected ? String(q.answer.response.selected) : undefined,
          };
        });

        setQuestions(mappedQuestions);

        // Restore any existing saved answers
        const initialAnswers: Record<string, string> = {};
        const initialFlags: string[] = [];
        mappedQuestions.forEach((mq) => {
          if (mq.selectedOptionId) {
            initialAnswers[mq.question_id] = mq.selectedOptionId;
          }
        });
        (paper.questions ?? []).forEach((q: any) => {
          if (q.answer?.flagged) {
            initialFlags.push(String(q.question_id));
          }
        });

        setAnswers(initialAnswers);
        setMarkedForReview(initialFlags);
      } catch (err: any) {
        console.error("Failed to start assessment attempt:", err);
        setLoadError(err?.data?.message || err?.message || "Failed to load assessment.");
      } finally {
        setIsInitializing(false);
      }
    }

    initTest();
  }, [testId, prepareAttempt, startAttempt, resumeAttempt]);

  // 2. Server-validated Countdown Timer
  useEffect(() => {
    if (secondsRemaining === null || secondsRemaining <= 0 || testResult) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          handleFinalSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [secondsRemaining, testResult]);

  // 3. Browser Back & Tab Close Confirmation (beforeunload)
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!testResult && attemptId && questions.length > 0) {
        e.preventDefault();
        e.returnValue = "Leave this test? Your answers are saved and you can resume while the timer is running.";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [testResult, attemptId, questions.length]);

  // 4. Autosave Answer directly to server
  const handleSelectOption = async (optionId: string) => {
    const currentQ = questions[currentIndex];
    if (!currentQ || !attemptId) return;

    setAnswers((prev) => ({ ...prev, [currentQ.question_id]: optionId }));

    try {
      await saveAnswerMutation({
        attemptId,
        questionId: currentQ.question_id,
        response: { selected: optionId },
        revision: 0,
        flagged: markedForReview.includes(currentQ.question_id),
      }).unwrap();
    } catch {
      // Saved locally in state if network glitch
    }
  };

  const handleToggleReview = async () => {
    const currentQ = questions[currentIndex];
    if (!currentQ || !attemptId) return;

    const isFlagged = markedForReview.includes(currentQ.question_id);
    const newFlags = isFlagged
      ? markedForReview.filter((id) => id !== currentQ.question_id)
      : [...markedForReview, currentQ.question_id];
    setMarkedForReview(newFlags);

    try {
      const selectedOption = answers[currentQ.question_id];
      await saveAnswerMutation({
        attemptId,
        questionId: currentQ.question_id,
        response: selectedOption ? { selected: selectedOption } : null,
        revision: 0,
        flagged: !isFlagged,
      }).unwrap();
    } catch {
      // Flag state kept in component memory
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  // 5. Submit Attempt to Server and Safe Result Retrieval
  const loadAttemptResult = async (targetAttemptId: string) => {
    setIsFetchingResult(true);
    setResultFetchError(null);
    try {
      const res = await fetchResult(targetAttemptId).unwrap();
      const r = (res as any)?.result || res;
      if (!r) {
        throw new Error("Assessment result is not available yet.");
      }

      const score = Number(r?.score ?? r?.total_marks_awarded ?? 0);
      const totalMarks = Number(r?.max_score ?? r?.max_marks ?? r?.total_marks ?? (questions.length * 10));
      const pct = Math.round(
        Number(r?.percent ?? r?.percentage ?? (totalMarks > 0 ? (score / totalMarks) * 100 : 0))
      );
      const passed = Boolean(r?.result === "pass" || r?.passed || pct >= passMarkPercent);

      setTestResult({ score, totalMarks, pct, passed });

      if (passed) {
        notify.success(`Congratulations! Passed with ${pct}%.`);
        if (onTestPassed) {
          onTestPassed();
        }
      } else {
        notify.error(`Test score: ${pct}%. Pass mark is ${passMarkPercent}%.`);
      }
    } catch (err: any) {
      console.error("Failed to retrieve assessment result:", err);
      const errMsg =
        err?.data?.message ||
        err?.message ||
        "Failed to retrieve your assessment result. Your attempt was submitted successfully.";
      setResultFetchError(errMsg);
    } finally {
      setIsFetchingResult(false);
    }
  };

  const handleFinalSubmit = async () => {
    if (!attemptId) return;

    try {
      await submitAttemptMutation(attemptId).unwrap();
      await loadAttemptResult(attemptId);
    } catch (err: any) {
      notify.error(err?.data?.message || err?.message || "Failed to submit assessment.");
    }
  };

  if (isInitializing || isPreparingAttempt || isStartingAttempt) {
    return <PageLoader label={`Loading ${contextType} assessment...`} />;
  }

  if (isFetchingResult) {
    return <PageLoader label="Calculating your assessment results..." />;
  }

  if (resultFetchError && attemptId) {
    return (
      <div className="max-w-4xl mx-auto space-y-6 pb-12 pt-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium pb-3 border-b border-slate-200">
          <Link to="/courses/my" className="hover:text-[#00663C] transition-colors">
            Courses
          </Link>
          <span>/</span>
          <Link to={finalReturnUrl} className="hover:text-[#00663C] transition-colors">
            {courseTitle}
          </Link>
          <span>/</span>
          <span className="text-slate-800 font-bold">{contextTitle}</span>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-white p-10 text-center max-w-lg mx-auto space-y-4 shadow-2xs">
          <div className="w-14 h-14 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto ring-1 ring-amber-200">
            <Icon name="alertTriangle" size={28} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-[#0A1530]">Retrieving Assessment Result</h3>
            <p className="text-xs text-amber-800 bg-amber-50 p-2.5 rounded-xl border border-amber-200 mt-2 max-w-sm mx-auto leading-relaxed">
              {resultFetchError}
            </p>
          </div>
          <div className="pt-2 flex items-center justify-center gap-3">
            <button
              type="button"
              disabled={isFetchingResult}
              onClick={() => loadAttemptResult(attemptId)}
              className="px-5 py-2.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors disabled:opacity-60"
            >
              {isFetchingResult ? "Checking..." : "Retry Result"}
            </button>
            <button
              type="button"
              onClick={() => navigate(finalReturnUrl)}
              className="px-4 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors"
            >
              Back to course
            </button>
          </div>
        </div>
      </div>
    );
  }

  // If error starting attempt or accessing test
  if (loadError) {
    return (
      <div className="max-w-4xl mx-auto space-y-6 pb-12 pt-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium pb-3 border-b border-slate-200">
          <Link to="/courses/my" className="hover:text-[#00663C] transition-colors">
            Courses
          </Link>
          <span>/</span>
          <Link to={finalReturnUrl} className="hover:text-[#00663C] transition-colors">
            {courseTitle}
          </Link>
          <span>/</span>
          <span className="text-slate-800 font-bold">{contextTitle}</span>
        </div>

        {/* Error State */}
        <div className="rounded-2xl border border-rose-200 bg-white p-10 text-center max-w-lg mx-auto space-y-4 shadow-2xs">
          <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto ring-1 ring-rose-200">
            <Icon name="alertTriangle" size={28} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-[#0A1530]">Assessment Unavailable</h3>
            <p className="text-xs text-rose-700 bg-rose-50 p-2.5 rounded-xl border border-rose-200 mt-2 max-w-sm mx-auto leading-relaxed">
              {loadError}
            </p>
          </div>
          <div className="pt-2 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors"
            >
              Retry
            </button>
            <button
              type="button"
              onClick={() => navigate(finalReturnUrl)}
              className="px-5 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
            >
              Back to course
            </button>
          </div>
        </div>
      </div>
    );
  }

  // If no questions in test bank or test not configured (only after initialization completes)
  if (!testId || (!isInitializing && questions.length === 0)) {
    return (
      <div className="max-w-4xl mx-auto space-y-6 pb-12 pt-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium pb-3 border-b border-slate-200">
          <Link to="/courses/my" className="hover:text-[#00663C] transition-colors">
            Courses
          </Link>
          <span>/</span>
          <Link to={finalReturnUrl} className="hover:text-[#00663C] transition-colors">
            {courseTitle}
          </Link>
          <span>/</span>
          <span className="text-slate-800 font-bold">{contextTitle}</span>
        </div>

        {/* Empty State */}
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center max-w-lg mx-auto space-y-4 shadow-2xs">
          <div className="w-14 h-14 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
            <Icon name="fileText" size={28} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-[#0A1530]">No questions available yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
              {`This ${contextType} currently has no approved questions configured in the exam bank. Please check back later or review the course materials.`}
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate(finalReturnUrl)}
            className="px-5 py-2.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
          >
            Back to course
          </button>
        </div>
      </div>
    );
  }

  const currentQ = questions[currentIndex] || questions[0];
  if (!currentQ) {
    return (
      <div className="max-w-4xl mx-auto p-8 text-center text-slate-500">
        Question data is loading...
      </div>
    );
  }
  const minutes = Math.floor((secondsRemaining ?? 0) / 60);
  const seconds = (secondsRemaining ?? 0) % 60;
  const timeFormatted = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  const isTimeCritical = (secondsRemaining ?? 0) < 120;
  const answeredCount = Object.keys(answers).length;
  const progressPercent = Math.round(((currentIndex + 1) / questions.length) * 100);
  const displayTitle = testTitle || contextTitle;

  return (
    <AssessmentErrorBoundary returnUrl={finalReturnUrl} fallbackTitle={`${contextType === "chapter" ? "Chapter" : "Module"} Test Error`}>
      <div className="max-w-5xl mx-auto space-y-5 pb-12 pt-2">
      {/* 1. Header with Breadcrumb and Exit Button */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-slate-200">
        <div className="space-y-1">
          {/* Breadcrumb: Courses / Course Name / Context Name */}
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Link to="/courses/my" className="hover:text-[#00663C] transition-colors">
              Courses
            </Link>
            <span>/</span>
            <Link to={finalReturnUrl} className="hover:text-[#00663C] transition-colors truncate max-w-xs">
              {courseTitle}
            </Link>
            <span>/</span>
            <span className="text-slate-800 font-bold truncate max-w-xs">{contextTitle}</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-500">
              {contextType === "chapter" ? "Chapter test" : "Module test"} · {displayTitle}
            </span>
          </div>
          <h2 className="text-xl font-bold text-[#0A1530]">
            Question {currentIndex + 1} of {questions.length}
          </h2>
        </div>

        <div className="flex items-center gap-3">
          {/* Exit test button */}
          <button
            type="button"
            onClick={() => setIsExitModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors shadow-2xs"
          >
            <Icon name="arrowLeft" size={14} />
            Exit test
          </button>

          {/* Server-validated countdown timer */}
          <span
            className={cn(
              "inline-flex items-center gap-2 font-mono font-bold text-sm px-4 py-1.5 rounded-full border shadow-2xs transition-colors",
              isTimeCritical
                ? "bg-rose-50 text-rose-700 border-rose-300 animate-pulse"
                : "bg-emerald-50 text-[#00663C] border-emerald-200"
            )}
          >
            <Icon name="clock" size={16} />
            {timeFormatted}
          </span>
        </div>
      </div>

      {/* 2. Question Progress Bar */}
      <div className="flex items-center gap-3">
        <b className="text-xs font-bold text-[#0A1530] whitespace-nowrap">
          Question {currentIndex + 1} of {questions.length}
        </b>
        <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full bg-[#00663C] rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <span className="text-xs font-medium text-slate-400">{progressPercent}%</span>
      </div>

      {testResult ? (
        /* Result Screen */
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center max-w-md mx-auto space-y-6 shadow-sm">
          <div
            className={cn(
              "w-16 h-16 rounded-2xl flex items-center justify-center mx-auto shadow-xs",
              testResult.passed ? "bg-emerald-50 text-[#00663C]" : "bg-rose-50 text-rose-600"
            )}
          >
            <Icon name={testResult.passed ? "award" : "alertTriangle"} size={32} />
          </div>

          <div>
            <h3 className="text-xl font-bold text-[#0A1530]">
              {testResult.passed
                ? `${contextType === "chapter" ? "Chapter" : "Module"} Test Passed!`
                : "Assessment Not Passed"}
            </h3>
            <p className="text-xs text-slate-500 mt-1.5">
              You scored <b className="text-[#0A1530] text-sm">{testResult.pct}%</b> ({testResult.score}/{testResult.totalMarks} marks). Pass mark is {passMarkPercent}%.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => navigate(finalReturnUrl)}
              className="flex-1 py-2.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
            >
              Back to course
            </button>
            {testResult.passed && contextType === "chapter" && parentModuleId && (
              <button
                type="button"
                onClick={() => navigate(`/courses/${courseId}/modules/${parentModuleId}/test`)}
                className="px-4 py-2.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Module Test
              </button>
            )}
          </div>
        </div>
      ) : (
        /* Active Question & Palette Split View */
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
          {/* Left: Question Card (8 cols) */}
          <div className="md:col-span-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-5">
            <div className="flex items-start justify-between gap-4">
              <h4 className="text-base font-bold text-[#0A1530] leading-snug">
                {currentQ.text}
              </h4>
              <span className="shrink-0 px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[11px] font-semibold">
                {currentQ.marks} marks
              </span>
            </div>

            {/* Code Snippet if present */}
            {currentQ.codeSnippet && (
              <pre className="bg-[#0D1530] text-[#D6E2FF] p-4 rounded-xl font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800">
                <code>{currentQ.codeSnippet}</code>
              </pre>
            )}

            {/* MCQ Options */}
            <div className="space-y-2.5 pt-1">
              {currentQ.options.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No option choices specified for this question.</p>
              ) : (
                currentQ.options.map((opt) => {
                  const isSelected = answers[currentQ.question_id] === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => handleSelectOption(opt.id)}
                      className={cn(
                        "flex items-center gap-3.5 p-3.5 rounded-xl border text-xs font-semibold cursor-pointer transition-all",
                        isSelected
                          ? "border-[#00663C] bg-[#E7F3EC] text-[#0A1530] shadow-2xs font-bold"
                          : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50/70"
                      )}
                    >
                      <span
                        className={cn(
                          "w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors",
                          isSelected ? "border-[#00663C] bg-[#00663C]" : "border-slate-300"
                        )}
                      >
                        {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </span>
                      <span>{opt.text}</span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Navigation and Review Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-5 border-t border-slate-100">
              <button
                type="button"
                onClick={handleToggleReview}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-colors cursor-pointer",
                  markedForReview.includes(currentQ.question_id)
                    ? "bg-amber-100 text-amber-800 border border-amber-300"
                    : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                )}
              >
                <Icon name="flag" size={14} /> Mark for review
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={currentIndex === 0}
                  onClick={handlePrev}
                  className="px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  Previous
                </button>

                {currentIndex < questions.length - 1 ? (
                  <button
                    type="button"
                    onClick={handleNext}
                    className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
                  >
                    Next
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsConfirmSubmitOpen(true)}
                    className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
                  >
                    Submit test
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Right: Question Palette (4 cols) */}
          <aside className="md:col-span-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs space-y-4">
            <h3 className="text-sm font-bold text-[#0A1530]">Questions</h3>

            {/* Numbers Grid */}
            <div className="grid grid-cols-5 gap-2">
              {questions.map((q, idx) => {
                const isAnswered = answers[q.question_id] !== undefined;
                const isCurrent = currentIndex === idx;
                const isFlagged = markedForReview.includes(q.question_id);

                return (
                  <button
                    key={q.question_id}
                    type="button"
                    onClick={() => setCurrentIndex(idx)}
                    className={cn(
                      "aspect-square rounded-xl text-xs font-bold flex items-center justify-center transition-all cursor-pointer relative",
                      isCurrent && "ring-2 ring-[#00663C] ring-offset-2",
                      isFlagged
                        ? "bg-[#FEF1D6] text-[#9A5B00] border border-[#9A5B00]"
                        : isAnswered
                        ? "bg-[#A5D5BC] text-[#00522F] border border-[#A5D5BC]"
                        : "border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                    )}
                  >
                    {idx + 1}
                    {isFlagged && isAnswered && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#9A5B00] absolute top-1 right-1" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Design Legend */}
            <div className="flex flex-wrap items-center gap-3 pt-2 text-[11px] text-slate-500 border-t border-slate-100">
              <span className="inline-flex items-center gap-1.5">
                <i className="w-2.5 h-2.5 rounded-xs bg-[#00663C]" />
                Current
              </span>
              <span className="inline-flex items-center gap-1.5">
                <i className="w-2.5 h-2.5 rounded-xs bg-[#A5D5BC]" />
                Answered
              </span>
              <span className="inline-flex items-center gap-1.5">
                <i className="w-2.5 h-2.5 rounded-xs bg-[#FEF1D6] border border-[#9A5B00]" />
                Review
              </span>
            </div>

            <p className="text-xs text-slate-400 font-medium">Answers save as you go.</p>

            <button
              type="button"
              onClick={() => setIsConfirmSubmitOpen(true)}
              disabled={isSubmittingAttempt}
              className="w-full py-2.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs transition-colors"
            >
              {isSubmittingAttempt ? "Submitting..." : "Submit test"}
            </button>
          </aside>
        </div>
      )}

      {/* Leave Test Confirmation Dialog */}
      <ConfirmModal
        isOpen={isExitModalOpen}
        onClose={() => setIsExitModalOpen(false)}
        onConfirm={() => {
          setIsExitModalOpen(false);
          navigate(finalReturnUrl);
        }}
        title="Leave this test?"
        description="Leave this test? Your answers are saved and you can resume while the timer is running."
        confirmLabel="Leave"
      />

      {/* Submit Test Confirmation Dialog */}
      <ConfirmModal
        isOpen={isConfirmSubmitOpen}
        onClose={() => setIsConfirmSubmitOpen(false)}
        onConfirm={() => {
          setIsConfirmSubmitOpen(false);
          handleFinalSubmit();
        }}
        title={`Submit ${contextType === "chapter" ? "Chapter" : "Module"} Test?`}
        description={`You have answered ${answeredCount} of ${questions.length} questions (${questions.length - answeredCount} unanswered). You cannot change your answers after submission.`}
        confirmLabel="Confirm & Submit"
      />
      </div>
    </AssessmentErrorBoundary>
  );
}
