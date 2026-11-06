import { useMemo } from "react";

import { useGetTestQuery, useGetValidationQuery, useListTestsQuery } from "@/modules/assessments/tests/api/testsApi";
import type { TestListItem } from "@/modules/assessments/tests/types";
import type { CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";

export type CourseTestKind = "topic" | "final";

/** Prefer the draft being edited, then the published one; never a retired one. */
function current(tests: TestListItem[]): TestListItem | undefined {
  const live = tests.filter((test) => test.status !== "retired");
  return live.find((test) => test.status === "draft") ?? live.find((test) => test.status === "in_review") ?? live.find((test) => test.status === "published");
}

/** Which test this page edits: a topic's test or the course's final test, with where it sits in the course. */
export function useCourseTest(kind: CourseTestKind, courseId: string, topicId: string | undefined, version: CourseVersionDetail | undefined) {
  const targetId = kind === "final" ? courseId : topicId ?? "";
  const list = useListTestsQuery({ kind, target_id: targetId, page: 1, per_page: 20 }, { skip: !targetId });
  const listed = useMemo(() => current(list.data?.items ?? []), [list.data]);
  const published = useMemo(() => (list.data?.items ?? []).find((test) => test.status === "published"), [list.data]);
  const test = useGetTestQuery(listed?.test_id ?? "", { skip: !listed });
  const validation = useGetValidationQuery(listed?.test_id ?? "", { skip: !listed || listed.status === "published" });

  const place = useMemo(() => {
    if (kind === "final" || !version) return null;
    for (const [m, module] of version.modules.entries()) {
      const t = module.topics.findIndex((topic) => topic.topic_id === topicId);
      const topic = module.topics[t];
      if (topic) return { module, topic, code: `${m + 1}.${t + 1}` };
    }
    return null;
  }, [kind, topicId, version]);

  return {
    targetId,
    test: test.data,
    validation: validation.data,
    /** Another, published test for the same target (being replaced by this draft). */
    publishedOther: published && published.test_id !== listed?.test_id ? published : undefined,
    place,
    isLoading: list.isLoading || (Boolean(listed) && test.isLoading),
  };
}
