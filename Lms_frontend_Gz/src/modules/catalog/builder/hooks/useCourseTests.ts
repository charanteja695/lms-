import { useMemo } from "react";

import { useGetCompositionsQuery, useListTestsQuery } from "@/modules/assessments/tests/api/testsApi";
import type { TestCompositionItem } from "@/modules/assessments/tests/reportTypes";
import type { TestListItem } from "@/modules/assessments/tests/types";
import type { CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";

export interface CourseTest {
  test: TestListItem;
  composition: TestCompositionItem | undefined;
}

/** The newest test per target, preferring a published one (only one per target can be published). */
function pick(tests: TestListItem[]): Map<string, TestListItem> {
  const byTarget = new Map<string, TestListItem>();
  for (const test of tests) {
    if (!test.target_id) continue;
    const current = byTarget.get(test.target_id);
    const better = !current || (test.status === "published" && current.status !== "published") || (current.status !== "published" && test.created_at > current.created_at);
    if (better && test.status !== "retired") byTarget.set(test.target_id, test);
  }
  return byTarget;
}

/**
 * Every topic test and the final test of one course version, each with what it holds (multiple choice, programs)
 * against what it needs. Two calls for the topics plus one for the final test, whatever the course size.
 */
export function useCourseTests(courseId: string, version: CourseVersionDetail | undefined) {
  const topicIds = useMemo(() => (version?.modules ?? []).flatMap((module) => module.topics.map((topic) => topic.topic_id)), [version]);
  const topicTests = useListTestsQuery({ kind: "topic", target_ids: topicIds.join(","), page: 1, per_page: 100 }, { skip: topicIds.length === 0 });
  const finalTests = useListTestsQuery({ kind: "final", target_id: courseId, page: 1, per_page: 20 }, { skip: !courseId });

  const byTopic = useMemo(() => pick(topicTests.data?.items ?? []), [topicTests.data]);
  const final = useMemo(() => pick(finalTests.data?.items ?? []).get(courseId), [finalTests.data, courseId]);
  const testIds = useMemo(() => [...[...byTopic.values()].map((test) => test.test_id), ...(final ? [final.test_id] : [])], [byTopic, final]);
  const compositions = useGetCompositionsQuery(testIds, { skip: testIds.length === 0 });
  const compositionById = useMemo(() => new Map((compositions.data ?? []).map((item) => [item.test_id, item])), [compositions.data]);

  const topicTest = (topicId: string): CourseTest | undefined => {
    const test = byTopic.get(topicId);
    return test ? { test, composition: compositionById.get(test.test_id) } : undefined;
  };
  return {
    topicTest,
    finalTest: final ? { test: final, composition: compositionById.get(final.test_id) } : undefined,
    isLoading: topicTests.isLoading || finalTests.isLoading || compositions.isLoading,
  };
}
