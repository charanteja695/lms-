import type { CourseTest } from "@/modules/catalog/builder/hooks/useCourseTests";
import type { CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";

export interface BuildIssue {
  key: string;
  /** Where it gets fixed: the outline (modules, topics, lessons), a topic's test, or the final test. */
  kind: "outline" | "test" | "final";
  title: string;
  text: string;
  /** Where to fix it: a topic in the outline, or the final test. */
  topicId?: string;
  final?: boolean;
}

/** "3 more multiple-choice and 1 program", from the counts assessment-service reports. */
export function missingText(test: CourseTest | undefined, needMcq: number, needPrograms: number): string {
  const composition = test?.composition;
  const mcq = Math.max(0, (composition?.required_multiple_choice ?? needMcq) - (composition?.multiple_choice ?? 0));
  const programs = Math.max(0, (composition?.required_programs ?? needPrograms) - (composition?.programs ?? 0));
  const parts = [mcq && `${mcq} more multiple-choice`, programs && `${programs} ${programs === 1 ? "program" : "programs"}`].filter(Boolean);
  return parts.join(" and ");
}

/**
 * What stops this version being published, in course order, for the "Before you publish" panel. It summarises what
 * the servers report (lessons, media readiness, each test's composition); catalog-service checks the same on submit.
 */
export function buildIssues(version: CourseVersionDetail, topicTest: (topicId: string) => CourseTest | undefined, finalTest: CourseTest | undefined): BuildIssue[] {
  const issues: BuildIssue[] = [];
  if (version.modules.length === 0) issues.push({ kind: "outline", key: "no-modules", title: "No modules yet", text: "Add the first module." });
  version.modules.forEach((module, m) => {
    if (module.topics.length === 0) issues.push({ kind: "outline", key: `module-${module.module_id}`, title: `Module ${m + 1} · ${module.title}`, text: "Add at least one topic." });
    module.topics.forEach((topic, t) => {
      const title = `${m + 1}.${t + 1} ${topic.title}`;
      const test = topicTest(topic.topic_id);
      if (topic.items.length === 0) issues.push({ kind: "outline", key: `lessons-${topic.topic_id}`, title, text: "Add lessons: a video or a PDF.", topicId: topic.topic_id });
      const waiting = topic.items.filter((item) => (item.item_type === "video" || item.item_type === "pdf") && !item.media_ready).length;
      if (waiting) issues.push({ kind: "outline", key: `media-${topic.topic_id}`, title, text: `${waiting} upload${waiting === 1 ? " is" : "s are"} still processing or failed.`, topicId: topic.topic_id });
      if (!test) issues.push({ kind: "test", key: `test-${topic.topic_id}`, title, text: "Create its topic test.", topicId: topic.topic_id });
      else if (test.composition && !test.composition.valid) {
        const missing = missingText(test, 5, 1);
        issues.push({ kind: "test", key: `test-${topic.topic_id}`, title, text: missing ? `Its test needs ${missing}.` : "Its test has problems to fix.", topicId: topic.topic_id });
      } else if (test.test.status !== "published") issues.push({ kind: "test", key: `test-${topic.topic_id}`, title, text: "Publish its test.", topicId: topic.topic_id });
    });
  });
  if (!finalTest) issues.push({ kind: "final", key: "final", title: "Final course test", text: "Create the final test.", final: true });
  else if (finalTest.composition && !finalTest.composition.valid) {
    const missing = missingText(finalTest, 10, 2);
    issues.push({ kind: "final", key: "final", title: "Final course test", text: missing ? `Add ${missing}.` : "It has problems to fix.", final: true });
  } else if (finalTest.test.status !== "published") issues.push({ kind: "final", key: "final", title: "Final course test", text: "Publish it.", final: true });
  else if (version.rule.final_test_id !== finalTest.test.test_id) issues.push({ kind: "final", key: "final", title: "Final course test", text: "Set it as this course's final test.", final: true });
  return issues;
}
