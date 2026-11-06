import { Navigate } from "react-router-dom";
import type { RouteObject } from "react-router-dom";

export const enrollmentRoutes: RouteObject[] = [
  { path: "/my-learning", element: <Navigate to="/courses/my" replace /> },
  { path: "/my-learning/:enrollmentId", element: <Navigate to="/courses/my" replace /> },
];
