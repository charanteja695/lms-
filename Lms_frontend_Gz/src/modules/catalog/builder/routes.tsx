import { Navigate, useParams, type RouteObject } from "react-router-dom";

function RedirectToCourseHub() {
  const { courseId = "" } = useParams();
  return <Navigate to={`/courses/${courseId}`} replace />;
}

const base = "/courses/:courseId/versions/:versionId";

/** Building one course version: redirects legacy builder routes to the modern Course Hub. */
export const builderRoutes: RouteObject[] = [
  { path: base, element: <RedirectToCourseHub /> },
  { path: `${base}/publish`, element: <RedirectToCourseHub /> },
  { path: `${base}/topics/:topicId/test`, element: <RedirectToCourseHub /> },
  { path: `${base}/final-test`, element: <RedirectToCourseHub /> },
  { path: `${base}/tests/:testId/programs/new`, element: <RedirectToCourseHub /> },
  { path: `${base}/tests/:testId/programs/:questionId`, element: <RedirectToCourseHub /> },
];
