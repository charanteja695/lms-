import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import {
  useListEnrollmentsQuery,
  useCompleteItemMutation,
} from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { StudentAssessmentRunner } from "@/modules/catalog/courses/components/assessment/StudentAssessmentRunner";
import { PageLoader } from "@/shared/ui";

export function ChapterTestPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>();

  // 1. Fetch course & latest version detail to locate real chapter and its topic_test_id
  const { data: course, isLoading: isCourseLoading } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
  });
  const versionId = course?.versions?.[course.versions.length - 1]?.version_id;
  const { data: versionDetail, isLoading: isVersionLoading } = useGetVersionQuery(
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

  if (isCourseLoading || isVersionLoading) {
    return <PageLoader label="Loading chapter assessment..." />;
  }

  const courseTitle = course?.title || "Course Room";
  const chapterTitle = currentChapter?.title || "Chapter Assessment";

  return (
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
  );
}
