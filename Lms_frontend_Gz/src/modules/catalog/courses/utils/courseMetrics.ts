import type { Course } from "@/modules/catalog/courses/types";
import type { CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";

export interface ParsedCourseSummary {
  level: "Beginner" | "Intermediate" | "Advanced";
  duration: string;
  passPercentage: string;
  cleanDescription: string;
  category: string;
  instructor: string;
  learningOutcomes: string[];
  prerequisites: string[];
}

export function parseCourseSummary(summary?: string | null): ParsedCourseSummary {
  if (!summary) {
    return {
      level: "Beginner",
      duration: "0h",
      passPercentage: "70%",
      cleanDescription: "",
      category: "Technology",
      instructor: "Staff Instructor",
      learningOutcomes: [],
      prerequisites: [],
    };
  }

  let level: "Beginner" | "Intermediate" | "Advanced" = "Beginner";
  if (summary.includes("[Advanced]") || summary.toLowerCase().includes("advanced")) {
    level = "Advanced";
  } else if (summary.includes("[Intermediate]") || summary.toLowerCase().includes("intermediate")) {
    level = "Intermediate";
  }

  const durationMatch = summary.match(/\[([0-9]+\s*(?:hours|hour|h|min|minutes))\]/i);
  const duration = durationMatch && durationMatch[1] ? durationMatch[1] : "0h";

  const passMatch = summary.match(/\[Pass:\s*([0-9]+%?)\]/i);
  const passPercentage = passMatch && passMatch[1] ? passMatch[1] : "70%";

  const catMatch = summary.match(/\[Category:\s*([^\]]+)\]/i);
  const category = catMatch && catMatch[1] ? catMatch[1].trim() : "Technology";

  const instMatch = summary.match(/\[Instructor:\s*([^\]]+)\]/i);
  const instructor = instMatch && instMatch[1] ? instMatch[1].trim() : "Staff Instructor";

  const cleanDescription = summary
    .replace(/\[(?:Beginner|Intermediate|Advanced)\]/gi, "")
    .replace(/\[[0-9]+\s*(?:hours|hour|h|min|minutes)\]/gi, "")
    .replace(/\[Pass:\s*[0-9]+%?\]/gi, "")
    .replace(/\[Category:\s*[^\]]+\]/gi, "")
    .replace(/\[Instructor:\s*[^\]]+\]/gi, "")
    .trim();

  return {
    level,
    duration,
    passPercentage,
    cleanDescription,
    category,
    instructor,
    learningOutcomes: [
      "Master the core fundamental and advanced concepts",
      "Hands-on exercises and real-world project assignments",
      "Pass chapter checkpoints and end-of-module tests",
      "Qualify for verified graduation certificate",
    ],
    prerequisites: [
      "Basic computer literacy and internet access",
      "Curiosity and willingness to complete hands-on labs",
    ],
  };
}

export interface CourseMetrics {
  moduleCount: number;
  chapterCount: number;
  itemsCount: number;
  duration: string;
  enrolledStudentsCount: number;
}

export function computeVersionMetrics(
  course: Course | null | undefined,
  versionDetail: CourseVersionDetail | null | undefined,
  enrolledStudentsCount: number = 0
): CourseMetrics {
  const modules = versionDetail?.modules ?? [];
  const moduleCount = modules.length;
  let chapterCount = 0;
  let itemsCount = 0;

  for (const m of modules) {
    const topics = m.topics ?? [];
    chapterCount += topics.length;
    for (const t of topics) {
      itemsCount += (t.items ?? []).length;
    }
  }

  const parsed = parseCourseSummary(course?.summary);

  return {
    moduleCount,
    chapterCount,
    itemsCount,
    duration: parsed.duration,
    enrolledStudentsCount,
  };
}

export interface CourseStepsStatus {
  step1Done: boolean;
  step2Done: boolean;
  step3Done: boolean;
  step4Done: boolean;
  step5Done: boolean;
  allDone: boolean;
  currentStepId: number;
  missingStepsText: string[];
}

export function computeCourseStepsStatus(
  course: Course | null | undefined,
  versionDetail: CourseVersionDetail | null | undefined,
  hasApprovedQuestions: boolean = false
): CourseStepsStatus {
  const step1Done = Boolean(course?.title?.trim() && course?.slug?.trim());
  const modules = versionDetail?.modules ?? [];
  const step2Done = modules.length >= 1;

  let totalChapters = 0;
  for (const m of modules) {
    const topics = m.topics ?? [];
    totalChapters += topics.length;
  }
  const step3Done = totalChapters >= 1;
  const step4Done = Boolean(hasApprovedQuestions);
  const step5Done = Boolean(versionDetail?.rule?.final_test_id);

  const missingStepsText: string[] = [];
  if (!step1Done) missingStepsText.push("Step 1 (Course details)");
  if (!step2Done) missingStepsText.push("Step 2 (Modules)");
  if (!step3Done) missingStepsText.push("Step 3 (Chapters)");
  if (!step4Done) missingStepsText.push("Step 4 (Approve questions)");
  if (!step5Done) missingStepsText.push("Step 5 (Final exam)");

  const allDone = step1Done && step2Done && step3Done && step4Done && step5Done;

  let currentStepId = 1;
  if (!step1Done) currentStepId = 1;
  else if (!step2Done) currentStepId = 2;
  else if (!step3Done) currentStepId = 3;
  else if (!step4Done) currentStepId = 4;
  else if (!step5Done) currentStepId = 5;
  else currentStepId = 5;

  return {
    step1Done,
    step2Done,
    step3Done,
    step4Done,
    step5Done,
    allDone,
    currentStepId,
    missingStepsText,
  };
}
