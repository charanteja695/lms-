import { useState, useMemo } from "react";
import { useGetMyTestQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { StudentAssessmentRunner } from "./StudentAssessmentRunner";
import { AssessmentErrorBoundary } from "./AssessmentErrorBoundary";
import { PageLoader } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import {
  ArrowLeft,
  Award,
  Check,
  Lock,
  Play,
  Shield,
  ExternalLink,
} from "lucide-react";

export interface ActiveAssessmentView {
  type: "chapter" | "module" | "final";
  testId?: string | null;
  moduleId?: string;
  chapterId?: string;
  title: string;
}

interface InlineAssessmentViewProps {
  courseId: string;
  courseTitle: string;
  assessment: ActiveAssessmentView;
  modulesList: any[];
  currentModule?: any;
  currentChapter?: any;
  finalTestDetail?: any;
  unlockState?: any;
  onClose: () => void;
  onTestPassed: () => void;
  onOpenFinalProctoredPage?: () => void;
}

export function InlineAssessmentView({
  courseId,
  courseTitle,
  assessment,
  modulesList,
  currentModule,
  currentChapter,
  finalTestDetail,
  unlockState,
  onClose,
  onTestPassed,
  onOpenFinalProctoredPage,
}: InlineAssessmentViewProps) {
  // 1. Fetch real test details for the active assessment
  const {
    data: fetchedTestDetail,
    isLoading: isTestLoading,
  } = useGetMyTestQuery(String(assessment.testId ?? ""), {
    skip: !assessment.testId,
  });

  const testDetail = fetchedTestDetail || (assessment.type === "final" ? finalTestDetail : null);

  // Real or fallback test parameters
  const questionCount = testDetail?.question_count ?? 20;
  const durationMinutes = testDetail?.duration_minutes ?? 30;
  const passMarkPercent = testDetail?.pass_mark_percent ?? 70;
  const attemptsAllowed =
    testDetail?.attempts_left != null
      ? Number(testDetail.attempts_left) + Number(testDetail.attempts_used || 0)
      : 3;
  const attemptsLeft = testDetail?.attempts_left;
  const openAttemptId = testDetail?.open_attempt_id;

  const [isTakingTest, setIsTakingTest] = useState(Boolean(openAttemptId));

  // 2. Evaluate Prerequisites Checklist based on Assessment Type
  const { isPrereqMet, checklistItems, missingReason } = useMemo(() => {
    if (assessment.type === "chapter") {
      // Rule 1: A chapter must be completed before its configured chapter test becomes available
      const ch = currentChapter;
      const isCompleted = Boolean(ch?.completed) || Boolean(ch?.test_passed);
      const items = [
        {
          id: String(ch?.topic_id || "chap"),
          title: ch?.title || "Chapter Lesson",
          isDone: isCompleted,
          desc: isCompleted ? "Chapter lesson completed ✓" : "Chapter lesson incomplete",
        },
      ];
      return {
        isPrereqMet: isCompleted,
        checklistItems: items,
        missingReason: isCompleted ? null : "Complete the chapter lesson first to unlock this test.",
      };
    }

    if (assessment.type === "module") {
      // Rule 2: All required chapter tests and chapter lessons must be completed before module test is available
      const mod = currentModule;
      const topics = mod?.topics ?? [];
      const items = topics.map((t: any) => {
        const hasTest = Boolean(t.topic_test_id);
        const isDone = hasTest ? Boolean(t.test_passed) : Boolean(t.completed);
        return {
          id: String(t.topic_id),
          title: t.title || "Chapter",
          isDone,
          desc: hasTest
            ? `Chapter test ${isDone ? "passed ✓" : "not passed yet"}`
            : `Lesson ${isDone ? "completed ✓" : "not completed yet"}`,
        };
      });

      const allDone = items.length > 0 && items.every((i: any) => i.isDone);
      const uncompletedTitles = items.filter((i: any) => !i.isDone).map((i: any) => i.title);

      return {
        isPrereqMet: allDone,
        checklistItems: items,
        missingReason: allDone
          ? null
          : `Complete all chapter lessons and pass all chapter tests in this module. Incomplete: ${uncompletedTitles.join(", ")}.`,
      };
    }

    // Rule 5: Final assessment unlocks ONLY after all modules completed and all module tests passed
    const items = modulesList.map((m: any) => {
      const hasModTest = Boolean(m.module_test_id);
      const isTestPassed = !hasModTest || Boolean(m.test_passed);
      const allChaptersDone = (m.topics || []).every((t: any) => {
        const hasTopicTest = Boolean(t.topic_test_id);
        const topicTestPassed = !hasTopicTest || Boolean(t.test_passed);
        return Boolean(t.completed) && topicTestPassed;
      });
      const isDone = Boolean(m.completed) || (allChaptersDone && isTestPassed);

      return {
        id: String(m.module_id),
        title: m.title || "Module",
        isDone,
        desc: hasModTest
          ? `Module test ${isTestPassed ? "passed ✓" : "pending"}`
          : `All lessons ${isDone ? "completed ✓" : "incomplete"}`,
      };
    });

    const backendEligible = unlockState?.eligible_for_final !== false && testDetail?.can_start !== false;
    const allModulesDone = items.length > 0 && items.every((i: any) => i.isDone);
    const uncompletedModules = items.filter((i: any) => !i.isDone).map((i: any) => i.title);

    return {
      isPrereqMet: allModulesDone && backendEligible,
      checklistItems: items,
      missingReason: allModulesDone
        ? null
        : `Complete all course modules and pass all module tests to unlock. Incomplete: ${uncompletedModules.join(", ")}.`,
    };
  }, [assessment.type, currentChapter, currentModule, modulesList, unlockState, testDetail]);

  if (isTestLoading && !testDetail) {
    return (
      <div className="p-12 text-center bg-white rounded-2xl border border-[#E5E7EB]">
        <PageLoader label="Loading assessment configuration..." />
      </div>
    );
  }

  // Active Test Runner Interface
  if (isTakingTest && assessment.testId) {
    return (
      <div className="bg-white rounded-2xl border border-[#E5E7EB] shadow-2xs overflow-hidden flex flex-col">
        {/* Top Header with Back to Lesson button */}
        <div className="p-4 bg-slate-50 border-b border-[#E5E7EB] flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => {
              setIsTakingTest(false);
              onClose();
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
          >
            <ArrowLeft size={14} /> Back to Lesson Video
          </button>

          <div className="flex items-center gap-2 truncate">
            <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 uppercase tracking-wider shrink-0">
              {assessment.type === "chapter"
                ? "Chapter Test"
                : assessment.type === "module"
                ? "Module Test"
                : "Final Exam"}
            </span>
            <span className="text-xs font-bold text-slate-900 truncate">{assessment.title}</span>
          </div>
        </div>

        {/* Student Assessment Runner Container */}
        <div className="p-4 md:p-6">
          <AssessmentErrorBoundary courseId={courseId}>
            <StudentAssessmentRunner
              testId={assessment.testId}
              testTitle={testDetail?.title || assessment.title}
              courseId={courseId}
              courseTitle={courseTitle}
              contextTitle={assessment.title}
              contextType={assessment.type}
              parentModuleId={assessment.moduleId}
              passMarkPercent={passMarkPercent}
              onTestPassed={() => {
                onTestPassed();
              }}
              onClose={() => {
                setIsTakingTest(false);
                onClose();
                onTestPassed();
              }}
              returnUrl={`/courses/${courseId}/learn`}
            />
          </AssessmentErrorBoundary>
        </div>
      </div>
    );
  }

  // Test Overview / Pre-screen Card
  return (
    <div className="bg-white rounded-2xl border border-[#E5E7EB] shadow-2xs overflow-hidden flex flex-col">
      {/* Top Header with Back to Lesson button */}
      <div className="p-4 bg-slate-50 border-b border-[#E5E7EB] flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
        >
          <ArrowLeft size={14} /> Back to Lesson Video
        </button>

        <div className="flex items-center gap-2 truncate">
          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 uppercase tracking-wider shrink-0">
            {assessment.type === "chapter"
              ? "Chapter Test"
              : assessment.type === "module"
              ? "Module Test"
              : "Final Exam"}
          </span>
          <span className="text-xs font-bold text-slate-900 truncate">{assessment.title}</span>
        </div>
      </div>

      {/* Screen 9 Centered Card Design */}
      <div className="max-w-xl mx-auto w-full p-6 md:p-10 text-center space-y-6">
        {/* Trophy / Award Icon */}
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto shadow-2xs ring-1 ring-blue-100">
          <Award size={32} />
        </div>

        <div>
          <h3 className="text-xl font-bold text-slate-900">{assessment.title}</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
            {assessment.type === "chapter"
              ? "Evaluate your understanding of the key concepts covered in this chapter."
              : assessment.type === "module"
              ? "Comprehensive evaluation covering all core topics, exercises, and chapters in this module."
              : "Final comprehensive certification exam evaluating the entire curriculum. Passing earns your verified certificate."}
          </p>
        </div>

        {/* Big 3 Stats: Questions / Duration / Pass mark */}
        <div className="flex items-center justify-center gap-8 md:gap-12 py-3 border-y border-slate-100">
          <div className="flex flex-col items-center">
            <b className="text-2xl md:text-3xl font-bold text-slate-900 leading-tight">{questionCount}</b>
            <span className="text-xs font-semibold text-slate-500 mt-0.5">Questions</span>
          </div>
          <div className="flex flex-col items-center">
            <b className="text-2xl md:text-3xl font-bold text-slate-900 leading-tight">{durationMinutes} min</b>
            <span className="text-xs font-semibold text-slate-500 mt-0.5">Duration</span>
          </div>
          <div className="flex flex-col items-center">
            <b className="text-2xl md:text-3xl font-bold text-slate-900 leading-tight">{passMarkPercent}%</b>
            <span className="text-xs font-semibold text-slate-500 mt-0.5">Pass mark</span>
          </div>
        </div>

        {/* Prerequisites Checklist */}
        <div className="space-y-2 text-left pt-1">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Prerequisites Checklist
            </h4>
            <span className={cn("text-[11px] font-bold", isPrereqMet ? "text-emerald-700" : "text-amber-700")}>
              {isPrereqMet ? "All Prerequisites Met ✓" : "Prerequisites Pending"}
            </span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {checklistItems.map((item: any) => (
              <div
                key={item.id}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-xl border text-xs font-medium transition-colors",
                  item.isDone
                    ? "bg-emerald-50/50 border-emerald-200 text-emerald-900"
                    : "bg-slate-50 border-slate-200 text-slate-600"
                )}
              >
                <span
                  className={cn(
                    "w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-xs",
                    item.isDone ? "bg-emerald-600 text-white" : "border-2 border-slate-300 bg-white"
                  )}
                >
                  {item.isDone && <Check size={12} />}
                </span>
                <span className="flex-1 truncate font-semibold">{item.title}</span>
                <span className="text-[11px] text-slate-500 shrink-0">{item.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Action Button & Explanations */}
        <div className="space-y-3 pt-2">
          {assessment.testId ? (
            isPrereqMet ? (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setIsTakingTest(true)}
                  className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold bg-blue-600 text-white hover:bg-blue-700 cursor-pointer shadow-sm transition-all"
                >
                  <Play size={15} className="fill-current" />
                  <span>{openAttemptId ? "Resume Test" : "Start Test"}</span>
                </button>

                {assessment.type === "final" && onOpenFinalProctoredPage && (
                  <button
                    type="button"
                    onClick={onOpenFinalProctoredPage}
                    className="w-full inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-semibold border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors shadow-2xs"
                  >
                    <Shield size={14} className="text-blue-600" />
                    <span>Launch in Full Dedicated Proctored Screen</span>
                    <ExternalLink size={13} className="text-slate-400" />
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <button
                  type="button"
                  disabled
                  className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed"
                >
                  <Lock size={15} />
                  <span>Assessment Locked</span>
                </button>
                {missingReason && (
                  <p className="text-xs text-amber-800 bg-amber-50 p-3 rounded-xl border border-amber-200 text-left leading-relaxed">
                    <span className="font-bold block mb-0.5">Required to unlock:</span>
                    {missingReason}
                  </p>
                )}
              </div>
            )
          ) : (
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500">
              No assessment has been configured by the instructor for this {assessment.type} yet.
            </div>
          )}

          {/* Attempts Note */}
          <p className="text-xs text-slate-400 font-medium">
            {attemptsLeft != null
              ? `You can attempt this test up to ${attemptsAllowed} times (${attemptsLeft} remaining).`
              : "You can attempt this test up to 3 times."}
          </p>
        </div>
      </div>
    </div>
  );
}
