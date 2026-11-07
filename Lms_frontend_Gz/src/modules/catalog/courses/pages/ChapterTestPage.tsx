import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import {
  useListEnrollmentsQuery,
  useCompleteItemMutation,
} from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { StudentAssessmentRunner } from "@/modules/catalog/courses/components/assessment/StudentAssessmentRunner";
import { AssessmentErrorBoundary } from "@/modules/catalog/courses/components/assessment/AssessmentErrorBoundary";
import { Icon, PageLoader } from "@/shared/ui";

export function ChapterTestPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>();

  // 1. Fetch course & latest published version detail to locate real chapter and its topic_test_id
  const {
    data: course,
    isLoading: isCourseLoading,
    isError: isCourseError,
    error: courseError,
  } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
  });

  const publishedVersion = course?.versions?.find((v) => v.status === "published");
  const versionId = publishedVersion?.version_id || course?.versions?.[course.versions.length - 1]?.version_id;

  const {
    data: versionDetail,
    isLoading: isVersionLoading,
    isError: isVersionError,
  } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId }
  );

  const { data: enrollmentsData } = useListEnrollmentsQuery({ status: "active", per_page: 50 });
  const { data: myCourses } = useListMyCoursesQuery();
  const [completeItemMutation] = useCompleteItemMutation();

  const enrollment = useMemo(() => {
    const list = enrollmentsData?.items ?? [];
    const courseMatch = myCourses?.find((c) => String(c.course_id) === String(courseId));
    if (courseMatch?.enrollment_id) {
      const found = list.find((e) => String(e.enrollment_id) === String(courseMatch.enrollment_id));
      if (found) return found;
    }
    return list[0];
  }, [enrollmentsData, myCourses, courseId]);

  // Find active chapter from version
  const currentChapter = useMemo(() => {
    if (!versionDetail?.modules) return null;
    for (const m of versionDetail.modules) {
      for (const t of m.topics ?? []) {
        if (String(t.topic_id) === String(chapterId)) {
          return { ...t, moduleTitle: m.title, moduleId: m.module_id };
        }
      }
    }
    return null;
  }, [versionDetail, chapterId]);

  const testId = currentChapter?.topic_test_id;

  const handleTestPassed = async () => {
    if (enrollment?.enrollment_id && chapterId) {
      try {
        await completeItemMutation({
          enrollmentId: enrollment.enrollment_id,
          topicItemId: chapterId,
        }).unwrap();
      } catch {
        // Handled silently
      }
    }
  };

  if (isCourseLoading || (versionId && isVersionLoading)) {
    return <PageLoader label="Loading chapter assessment..." />;
  }

  // Handle course access denied or error
  if (isCourseError || !course) {
    const errorMsg =
      (courseError as any)?.data?.message ||
      ((courseError as any)?.status === 403
        ? "Your institution has not been granted access to this course yet."
        : "Failed to load course details.");

    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-rose-200 rounded-2xl shadow-card text-center space-y-4">
        <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="alertTriangle" size={24} />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Course Access Restricted</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">{errorMsg}</p>
        <div className="pt-2">
          <Link
            to="/courses/my"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] transition-colors"
          >
            Back to My Courses
          </Link>
        </div>
      </div>
    );
  }

  // Handle curriculum version error
  if (isVersionError || (!versionDetail && versionId)) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-amber-200 rounded-2xl shadow-card text-center space-y-4">
        <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="alertTriangle" size={24} />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Curriculum Structure Unavailable</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Could not load the published curriculum structure for this course.
        </p>
        <div className="pt-2">
          <Link
            to={`/courses/${courseId}/learn`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] transition-colors"
          >
            Back to Course Room
          </Link>
        </div>
      </div>
    );
  }

  // Handle chapter not found
  if (!currentChapter) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-slate-200 rounded-2xl shadow-card text-center space-y-4">
        <div className="w-12 h-12 bg-slate-100 text-slate-500 rounded-full flex items-center justify-center mx-auto">
          <Icon name="fileText" size={24} />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Chapter Not Found</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          The requested chapter was not found in this course curriculum.
        </p>
        <div className="pt-2">
          <Link
            to={`/courses/${courseId}/learn`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] transition-colors"
          >
            Back to Course Room
          </Link>
        </div>
      </div>
    );
  }

  // Handle chapter without test configured
  if (!testId) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-slate-200 rounded-2xl shadow-card text-center space-y-4">
        <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto">
          <Icon name="fileText" size={24} />
        </div>
        <h2 className="text-lg font-bold text-slate-900">No Assessment Configured</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          No test has been configured by the instructor for &ldquo;{currentChapter.title}&rdquo; yet.
        </p>
        <div className="pt-2">
          <Link
            to={`/courses/${courseId}/learn`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] transition-colors"
          >
            Continue Lessons
          </Link>
        </div>
      </div>
    );
  }

  const courseTitle = course?.title || "Course Room";
  const chapterTitle = currentChapter?.title || "Chapter Assessment";

  return (
    <AssessmentErrorBoundary returnUrl={`/courses/${courseId}/learn`} fallbackTitle="Chapter Assessment Error">
      <StudentAssessmentRunner
        testId={testId}
        testTitle={chapterTitle}
        courseId={courseId ?? ""}
        courseTitle={courseTitle}
        contextTitle={chapterTitle}
        contextType="chapter"
        parentModuleId={currentChapter?.moduleId}
        passMarkPercent={70}
        onTestPassed={handleTestPassed}
        returnUrl={`/courses/${courseId}/learn`}
      />
    </AssessmentErrorBoundary>
  );
}
