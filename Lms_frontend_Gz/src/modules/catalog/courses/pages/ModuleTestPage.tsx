import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import {
  useListEnrollmentsQuery,
  useGetUnlockStateQuery,
  useCompleteItemMutation,
} from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { useGetMyTestQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { StudentAssessmentRunner } from "@/modules/catalog/courses/components/assessment/StudentAssessmentRunner";
import { AssessmentErrorBoundary } from "@/modules/catalog/courses/components/assessment/AssessmentErrorBoundary";
import { Icon, PageLoader } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

interface ChapterStatusItem {
  topic_id: string;
  title: string;
  isPassed: boolean;
  hasTest: boolean;
}

export function ModuleTestPage() {
  const { courseId, moduleId } = useParams<{ courseId: string; moduleId: string }>();

  // 1. Fetch course & version detail
  const {
    data: course,
    isLoading: isCourseLoading,
    isError: isCourseError,
    error: courseError,
  } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
  });
  const publishedVersion = course?.versions?.find((v) => v.status === "published");
  const versionId = publishedVersion?.version_id;
  const {
    data: versionDetail,
    isLoading: isVersionLoading,
    isError: isVersionError,
    error: versionError,
  } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId }
  );

  const { data: enrollmentsData, isLoading: isEnrollmentsLoading } = useListEnrollmentsQuery({ status: "active", per_page: 50 });
  const { data: myCourses, isLoading: isMyCoursesLoading } = useListMyCoursesQuery();

  const enrollment = useMemo(() => {
    const list = enrollmentsData?.items ?? [];
    const courseMatch = myCourses?.find((c) => String(c.course_id) === String(courseId));
    if (courseMatch?.enrollment_id) {
      const found = list.find((e) => String(e.enrollment_id) === String(courseMatch.enrollment_id));
      if (found) return found;
    }
    const directMatch = list.find((e: any) => String(e.course_id) === String(courseId));
    if (directMatch) return directMatch;
    return null;
  }, [enrollmentsData, myCourses, courseId]);

  const { data: unlockState, isLoading: isUnlockLoading } = useGetUnlockStateQuery(
    enrollment?.enrollment_id ?? "",
    { skip: !enrollment?.enrollment_id }
  );

  const [completeItemMutation] = useCompleteItemMutation();

  // Find module from versionDetail or unlockState
  const currentModule = useMemo(() => {
    if (versionDetail?.modules) {
      const found = versionDetail.modules.find((m) => String(m.module_id) === String(moduleId));
      if (found) return found;
    }
    if (unlockState?.modules) {
      return unlockState.modules.find((m) => String(m.module_id) === String(moduleId));
    }
    return null;
  }, [versionDetail, unlockState, moduleId]);

  // Find module unlock data from unlockState to check chapter test passing status
  const moduleUnlock = useMemo(() => {
    if (!unlockState?.modules) return null;
    return unlockState.modules.find((m) => String(m.module_id) === String(moduleId));
  }, [unlockState, moduleId]);

  // Real topics list with completion / test passed state
  const topicsList = useMemo(() => {
    if (moduleUnlock?.topics && moduleUnlock.topics.length > 0) {
      return moduleUnlock.topics.map((t: any) => {
        const modTopic = (currentModule as any)?.topics?.find((ct: any) => String(ct.topic_id) === String(t.topic_id));
        return {
          ...t,
          topic_test_id: t.topic_test_id ?? modTopic?.topic_test_id,
        };
      });
    }
    return (currentModule as any)?.topics ?? [];
  }, [moduleUnlock, currentModule]);

  // Enforce module test prerequisites according to business rules:
  // - Chapters with configured tests must have passed those tests.
  // - Chapters without configured tests must follow the explicitly defined completion rule.
  // - The module test must remain locked until all required prerequisites are satisfied.
  const chaptersStatus: ChapterStatusItem[] = useMemo(() => {
    return topicsList.map((t: any, idx: number) => {
      const hasTest = Boolean(t.topic_test_id);
      const isPassed = hasTest ? Boolean(t.test_passed) : Boolean(t.completed);
      return {
        topic_id: t.topic_id,
        title: t.title || `Chapter ${idx + 1}`,
        isPassed,
        hasTest,
      };
    });
  }, [topicsList]);

  const allChapterTestsPassed =
    chaptersStatus.length > 0 && chaptersStatus.every((c: ChapterStatusItem) => c.isPassed);
  const unpassedChapters = chaptersStatus.filter((c: ChapterStatusItem) => !c.isPassed);

  const moduleTestId = (currentModule as any)?.module_test_id;

  // Real module test details from assessment service
  const { data: testDetail } = useGetMyTestQuery(String(moduleTestId ?? ""), {
    skip: !moduleTestId,
  });

  // State: whether student is currently taking the test questions
  const [isTakingTest, setIsTakingTest] = useState(false);

  // Real backend configuration
  const questionCount = testDetail?.question_count ?? 20;
  const durationMinutes = testDetail?.duration_minutes ?? 30;
  const passMarkPercent = testDetail?.pass_mark_percent ?? 70;
  const attemptsAllowed =
    testDetail?.attempts_left != null
      ? Number(testDetail.attempts_left) + Number(testDetail.attempts_used || 0)
      : 3;
  const attemptsLeft = testDetail?.attempts_left;

  const courseTitle = course?.title || "Course Room";
  const moduleTitle = currentModule?.title || "Module Test";

  const handleModuleTestPassed = async () => {
    if (!enrollment?.enrollment_id) {
      console.warn("[ModuleTestPage] Enrollment unavailable; skipping completion mutation.");
      return;
    }
    if (moduleId) {
      try {
        await completeItemMutation({
          enrollmentId: enrollment.enrollment_id,
          topicItemId: moduleId,
        }).unwrap();
      } catch {
        // Handled silently
      }
    }
  };

  if (isCourseLoading || (versionId && isVersionLoading)) {
    return <PageLoader label="Loading module test configuration..." />;
  }

  if (isCourseError || (!isCourseLoading && !course)) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white rounded-2xl border border-red-200 text-center space-y-4 shadow-sm">
        <div className="w-12 h-12 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="alert-triangle" size={24} />
        </div>
        <h3 className="text-lg font-bold text-slate-800">Course Access Restricted</h3>
        <p className="text-sm text-slate-500">
          {(courseError as any)?.data?.message ||
            "Unable to load course details. Please verify your enrollment or institutional approval."}
        </p>
        <Link
          to="/courses/my"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#00663C] text-white rounded-xl text-sm font-semibold hover:bg-[#00522F]"
        >
          <Icon name="arrow-left" size={16} /> Back to My Courses
        </Link>
      </div>
    );
  }

  // Handle no published curriculum version
  if (!publishedVersion) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-amber-200 rounded-2xl shadow-card text-center space-y-4">
        <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="alert-triangle" size={24} />
        </div>
        <h3 className="text-lg font-bold text-slate-800">Curriculum Not Published</h3>
        <p className="text-sm text-slate-500">
          This course does not have a published curriculum version available yet. Students can only access published courses.
        </p>
        <Link
          to="/courses/my"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#00663C] text-white rounded-xl text-sm font-semibold hover:bg-[#00522F]"
        >
          <Icon name="arrow-left" size={16} /> Back to My Courses
        </Link>
      </div>
    );
  }

  if (isEnrollmentsLoading || (enrollment?.enrollment_id && isUnlockLoading)) {
    return <PageLoader label="Loading module test configuration..." />;
  }

  // Handle missing active enrollment for this course
  if (!isEnrollmentsLoading && !isMyCoursesLoading && enrollmentsData && !enrollment) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-amber-200 rounded-2xl shadow-card text-center space-y-4">
        <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="alert-triangle" size={24} />
        </div>
        <h3 className="text-lg font-bold text-slate-800">Course Enrollment Required</h3>
        <p className="text-sm text-slate-500">
          You are not actively enrolled in this course. Assessment attempts and progress can only be recorded for enrolled students.
        </p>
        <Link
          to="/courses/my"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#00663C] text-white rounded-xl text-sm font-semibold hover:bg-[#00522F]"
        >
          <Icon name="arrow-left" size={16} /> Back to My Courses
        </Link>
      </div>
    );
  }

  if (isVersionError) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white rounded-2xl border border-amber-200 text-center space-y-4 shadow-sm">
        <div className="w-12 h-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="alert-triangle" size={24} />
        </div>
        <h3 className="text-lg font-bold text-slate-800">Curriculum Structure Unavailable</h3>
        <p className="text-sm text-slate-500">
          {(versionError as any)?.data?.message ||
            "Could not load the syllabus structure for this course version."}
        </p>
        <Link
          to={`/courses/${courseId}/learn`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#00663C] text-white rounded-xl text-sm font-semibold hover:bg-[#00522F]"
        >
          <Icon name="arrow-left" size={16} /> Return to Course Room
        </Link>
      </div>
    );
  }

  if (!currentModule && !isCourseLoading && !isVersionLoading) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white rounded-2xl border border-amber-200 text-center space-y-4 shadow-sm">
        <div className="w-12 h-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="info" size={24} />
        </div>
        <h3 className="text-lg font-bold text-slate-800">Module Not Found</h3>
        <p className="text-sm text-slate-500">
          The requested module could not be found in this course syllabus.
        </p>
        <Link
          to={`/courses/${courseId}/learn`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#00663C] text-white rounded-xl text-sm font-semibold hover:bg-[#00522F]"
        >
          <Icon name="arrow-left" size={16} /> Return to Course Room
        </Link>
      </div>
    );
  }

  // If student clicked "Start module test" (or has an ongoing open attempt), render the assessment runner
  if (isTakingTest || (testDetail?.open_attempt_id && isTakingTest)) {
    return (
      <AssessmentErrorBoundary courseId={courseId}>
        <StudentAssessmentRunner
          testId={moduleTestId}
          testTitle={testDetail?.title || moduleTitle}
          courseId={courseId ?? ""}
          courseTitle={courseTitle}
          contextTitle={moduleTitle}
          contextType="module"
          passMarkPercent={passMarkPercent}
          onTestPassed={handleModuleTestPassed}
          returnUrl={`/courses/${courseId}/learn`}
        />
      </AssessmentErrorBoundary>
    );
  }

  return (
    <AssessmentErrorBoundary courseId={courseId}>
      <div className="max-w-4xl mx-auto space-y-6 pb-12 pt-2">
      {/* 1. Header with Breadcrumb: Courses / Course Name / Module Name */}
      <div className="pb-3 border-b border-slate-200 space-y-1">
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <Link to="/courses/my" className="hover:text-[#00663C] transition-colors">
            Courses
          </Link>
          <span>/</span>
          <Link to={`/courses/${courseId}/learn`} className="hover:text-[#00663C] transition-colors truncate max-w-xs">
            {courseTitle}
          </Link>
          <span>/</span>
          <span className="text-slate-800 font-bold truncate max-w-xs">{moduleTitle}</span>
        </div>
        <h2 className="text-xl font-bold text-[#0A1530]">Module test: {moduleTitle}</h2>
      </div>

      {/* 2. Screen 9 Design: Centered Test Overview Card */}
      <div className="max-w-xl mx-auto rounded-3xl border border-[#E4EAE7] bg-white p-8 md:p-10 text-center shadow-sm space-y-6">
        {/* Trophy Badge Icon */}
        <div className="w-16 h-16 rounded-full bg-[#E7F3EC] text-[#00663C] flex items-center justify-center mx-auto shadow-2xs">
          <Icon name="award" size={32} />
        </div>

        <div>
          <h3 className="text-xl font-bold text-[#0A1530]">{moduleTitle} Assessment</h3>
          <p className="text-xs text-slate-500 mt-1">
            Comprehensive evaluation covering all core topics and concepts in this module.
          </p>
        </div>

        {/* Big 3 Stats: Questions / Duration / Pass mark */}
        <div className="flex items-center justify-center gap-8 md:gap-12 py-3 border-y border-slate-100">
          <div className="flex flex-col items-center">
            <b className="text-2xl md:text-3xl font-bold text-[#0A1530] leading-tight">{questionCount}</b>
            <span className="text-xs font-semibold text-slate-500 mt-0.5">Questions</span>
          </div>
          <div className="flex flex-col items-center">
            <b className="text-2xl md:text-3xl font-bold text-[#0A1530] leading-tight">{durationMinutes} min</b>
            <span className="text-xs font-semibold text-slate-500 mt-0.5">Duration</span>
          </div>
          <div className="flex flex-col items-center">
            <b className="text-2xl md:text-3xl font-bold text-[#0A1530] leading-tight">{passMarkPercent}%</b>
            <span className="text-xs font-semibold text-slate-500 mt-0.5">Pass mark</span>
          </div>
        </div>

        {/* Chapter Completion Checklist */}
        <div className="space-y-2.5 text-left pt-1">
          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
            Module Prerequisites Checklist
          </h4>

          {chaptersStatus.length === 0 ? (
            <p className="text-xs text-slate-400 italic">No chapter prerequisites defined for this module.</p>
          ) : (
            chaptersStatus.map((ch: ChapterStatusItem, idx: number) => (
              <div
                key={ch.topic_id + idx}
                className={cn(
                  "flex items-center gap-3 p-3.5 rounded-xl border text-xs font-semibold transition-colors",
                  ch.isPassed
                    ? "bg-[#F8FAF9] border-[#E4EAE7] text-[#2F3A55]"
                    : "bg-slate-50/70 border-slate-200 text-slate-500"
                )}
              >
                <span
                  className={cn(
                    "w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-xs transition-colors",
                    ch.isPassed
                      ? "bg-[#00663C] text-white"
                      : "border-2 border-slate-300 bg-white"
                  )}
                >
                  {ch.isPassed && <Icon name="check" size={12} />}
                </span>
                <span className="flex-1 truncate">
                  {ch.title} {ch.hasTest ? `test ${ch.isPassed ? "passed" : "not passed yet"}` : `lesson ${ch.isPassed ? "completed" : "not completed yet"}`}
                </span>
                {!ch.isPassed && (
                  <Link
                    to={ch.hasTest ? `/courses/${courseId}/chapters/${ch.topic_id}/test` : `/courses/${courseId}/learn`}
                    className="text-[11px] font-bold text-[#00663C] hover:underline shrink-0"
                  >
                    {ch.hasTest ? "Take test" : "Go to lesson"}
                  </Link>
                )}
              </div>
            ))
          )}
        </div>

        {/* Start Button */}
        <div className="space-y-3 pt-2">
          <button
            type="button"
            disabled={!allChapterTestsPassed || !moduleTestId}
            onClick={() => setIsTakingTest(true)}
            className={cn(
              "w-full inline-flex items-center justify-center gap-2 py-3 rounded-xl text-xs font-bold transition-all shadow-xs",
              allChapterTestsPassed && moduleTestId
                ? "bg-[#00663C] text-white hover:bg-[#00522F] cursor-pointer shadow-md"
                : "bg-slate-200 text-slate-400 cursor-not-allowed"
            )}
          >
            {allChapterTestsPassed && moduleTestId ? (
              <>
                <Icon name="play" size={15} />
                {testDetail?.open_attempt_id ? "Resume module test" : "Start module test"}
              </>
            ) : (
              <>
                <Icon name="lock" size={15} />
                Start module test
              </>
            )}
          </button>

          {/* Locked Explanation */}
          {!moduleTestId && (
            <p className="text-xs text-slate-600 bg-slate-100 p-2.5 rounded-xl border border-slate-200">
              No assessment has been configured by the instructor for this module yet.
            </p>
          )}

          {!allChapterTestsPassed && unpassedChapters.length > 0 && (
            <p className="text-xs text-amber-700 bg-amber-50 p-2.5 rounded-xl border border-amber-200">
              Complete and satisfy all chapter prerequisites in this module to unlock the module test. Missing:{" "}
              <b>{unpassedChapters.map((c: ChapterStatusItem) => c.title).join(", ")}</b>.
            </p>
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
    </AssessmentErrorBoundary>
  );
}
