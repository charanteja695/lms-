import { lazy } from "react";
import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const CourseDashboardPage = lazy(() =>
  import("./pages/CourseDashboardPage").then((m) => ({ default: m.CourseDashboardPage }))
);
const CourseFormPage = lazy(() =>
  import("./pages/CourseFormPage").then((m) => ({ default: m.CourseFormPage }))
);
const CourseHubPage = lazy(() =>
  import("./pages/CourseHubPage").then((m) => ({ default: m.CourseHubPage }))
);
const ModuleChaptersPage = lazy(() =>
  import("./pages/ModuleChaptersPage").then((m) => ({ default: m.ModuleChaptersPage }))
);
const AIGeneratorPage = lazy(() =>
  import("./pages/AIGeneratorPage").then((m) => ({ default: m.AIGeneratorPage }))
);
const QuestionReviewPage = lazy(() =>
  import("./pages/QuestionReviewPage").then((m) => ({ default: m.QuestionReviewPage }))
);
const StudentLearningPage = lazy(() =>
  import("./pages/StudentLearningPage").then((m) => ({ default: m.StudentLearningPage }))
);
const ChapterTestPage = lazy(() =>
  import("./pages/ChapterTestPage").then((m) => ({ default: m.ChapterTestPage }))
);
const ModuleTestPage = lazy(() =>
  import("./pages/ModuleTestPage").then((m) => ({ default: m.ModuleTestPage }))
);
const FinalExamPage = lazy(() =>
  import("./pages/FinalExamPage").then((m) => ({ default: m.FinalExamPage }))
);
const MyCoursesCertificatesPage = lazy(() =>
  import("./pages/MyCoursesCertificatesPage").then((m) => ({ default: m.MyCoursesCertificatesPage }))
);

export const courseRoutes: RouteObject[] = [
  // 11. Student Courses & Certificates (Accessible to enrolled learners and platform viewers)
  {
    path: "/courses/my",
    element: page(<MyCoursesCertificatesPage />),
  },

  // 7. Student Learning Room
  {
    path: "/courses/:courseId/learn",
    element: page(<StudentLearningPage />),
  },

  // 8. Student Chapter Test
  {
    path: "/courses/:courseId/chapters/:chapterId/test",
    element: page(<ChapterTestPage />),
  },

  // 9. Student Module Test
  {
    path: "/courses/:courseId/modules/:moduleId/test",
    element: page(<ModuleTestPage />),
  },

  // 10. Student Final Proctored Exam
  {
    path: "/courses/:courseId/exam",
    element: page(<FinalExamPage />),
  },
  {
    path: "/courses/:courseId/final-exam",
    element: page(<FinalExamPage />),
  },

  // Admin & Staff: Course Catalog and Hub (Students redirected to /courses/my)
  {
    element: (
      <RequireRole
        roles={["super_admin", "admin", "institution_head", "staff"]}
        studentRedirect="/courses/my"
      />
    ),
    children: [
      {
        path: "/courses",
        element: page(<CourseDashboardPage />),
      },
      {
        path: "/courses/:courseId/hub",
        element: page(<CourseHubPage />),
      },
      {
        path: "/courses/:courseId",
        element: page(<CourseHubPage />),
      },
      {
        path: "/courses/:courseId/modules/:moduleId",
        element: page(<ModuleChaptersPage />),
      },
      {
        path: "/courses/:courseId/modules/:moduleId/chapters",
        element: page(<ModuleChaptersPage />),
      },
    ],
  },

  // Authoring Only: Create & Edit Course, AI Generation (Strictly super_admin and admin; 403 Access Denied for student/staff)
  {
    element: <RequireRole roles={["super_admin", "admin"]} />,
    children: [
      {
        path: "/courses/new",
        element: page(<CourseFormPage />),
      },
      {
        path: "/courses/:courseId/edit",
        element: page(<CourseFormPage />),
      },
      {
        path: "/courses/:courseId/modules/:moduleId/chapters/:chapterId/ai-generate",
        element: page(<AIGeneratorPage />),
      },
      {
        path: "/courses/:courseId/ai-generator",
        element: page(<AIGeneratorPage />),
      },
    ],
  },

  // Question Review: super_admin, admin, staff (403 for students)
  {
    element: <RequireRole roles={["super_admin", "admin", "staff"]} />,
    children: [
      {
        path: "/courses/:courseId/modules/:moduleId/chapters/:chapterId/questions",
        element: page(<QuestionReviewPage />),
      },
      {
        path: "/courses/:courseId/modules/:moduleId/chapters/:chapterId/review",
        element: page(<QuestionReviewPage />),
      },
      {
        path: "/courses/:courseId/questions/review",
        element: page(<QuestionReviewPage />),
      },
    ],
  },
];
