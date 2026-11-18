import { Navigate, useParams, type RouteObject } from "react-router-dom";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { PageLoader } from "@/shared/ui";

function CurriculumBuilderEntry() {
  const { data, isLoading } = useListCoursesQuery({ per_page: 5 });
  if (isLoading) return <PageLoader label="Opening Curriculum Builder..." />;
  const firstCourse = data?.items?.[0];
  if (firstCourse) {
    return <Navigate to={`/courses/${firstCourse.course_id}?tab=modules`} replace />;
  }
  return <Navigate to="/courses" replace />;
}

function RedirectToCourseHub() {
  const { courseId = "" } = useParams();
  return <Navigate to={`/courses/${courseId}`} replace />;
}

const base = "/courses/:courseId/versions/:versionId";

/** Building one course version: redirects legacy builder routes to the modern Course Hub. */
export const builderRoutes: RouteObject[] = [
  { path: "/catalog/builder", element: <CurriculumBuilderEntry /> },
  { path: base, element: <RedirectToCourseHub /> },
  { path: `${base}/publish`, element: <RedirectToCourseHub /> },
  { path: `${base}/topics/:topicId/test`, element: <RedirectToCourseHub /> },
  { path: `${base}/final-test`, element: <RedirectToCourseHub /> },
  { path: `${base}/tests/:testId/programs/new`, element: <RedirectToCourseHub /> },
  { path: `${base}/tests/:testId/programs/:questionId`, element: <RedirectToCourseHub /> },
];
