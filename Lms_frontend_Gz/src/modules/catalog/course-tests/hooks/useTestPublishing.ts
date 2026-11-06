import { useCallback } from "react";

import { useApproveTestMutation, useCloneTestMutation, useCreateTestMutation, useRetireTestMutation, useSubmitTestMutation } from "@/modules/assessments/tests/api/testsApi";
import type { Test, TestCreateBody, TestListItem } from "@/modules/assessments/tests/types";
import type { CourseTestKind } from "@/modules/catalog/course-tests/hooks/useCourseTest";
import { useUpdateRulesMutation } from "@/modules/catalog/courses/api/coursesApi";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** Starting values for a new course test; every one can be changed on the page. */
// Topic tests teach: the result and each answer with its explanation show right after submitting.
// The final test earns the certificate: the score shows at once, its questions stay private.
const DEFAULTS: Record<CourseTestKind, Pick<TestCreateBody, "duration_minutes" | "max_attempts" | "proctoring_level" | "result_visibility" | "review_policy">> = {
  topic: { duration_minutes: 20, max_attempts: 3, proctoring_level: "none", result_visibility: "immediate", review_policy: "answers" },
  final: { duration_minutes: 90, max_attempts: 3, proctoring_level: "strict", result_visibility: "immediate", review_policy: "none" },
};

/**
 * Creating, changing and publishing a course test. A published test cannot change: "make changes" starts a copy,
 * and publishing the copy retires the old one. The final test is then set on the course's rules.
 */
export function useTestPublishing(kind: CourseTestKind, ids: { courseId: string; versionId: string; targetId: string }) {
  const { can } = useCan();
  const [createTest, creating] = useCreateTestMutation();
  const [cloneTest, cloning] = useCloneTestMutation();
  const [submitTest] = useSubmitTestMutation();
  const [approveTest] = useApproveTestMutation();
  const [retireTest] = useRetireTestMutation();
  const [updateRules] = useUpdateRulesMutation();

  const create = useCallback(
    (title: string) =>
      createTest({
        title,
        kind,
        target_id: ids.targetId,
        time_mode: "overall",
        pass_mark_percent: 60,
        shuffle_questions: true,
        shuffle_options: true,
        ...DEFAULTS[kind],
        // no sections yet: a section must hold a question, so the first question creates it
      }).unwrap(),
    [createTest, ids.targetId, kind],
  );

  const makeChanges = useCallback((test: Test) => cloneTest(test.test_id).unwrap(), [cloneTest]);

  const publish = useCallback(
    async (test: Test, replacing: TestListItem | undefined) => {
      if (test.status === "draft") await submitTest(test.test_id).unwrap();
      if (!can("content.review")) return "submitted" as const;
      // one published test per topic (or course): the one being replaced steps aside first
      if (replacing) await retireTest(replacing.test_id).unwrap();
      await approveTest({ testId: test.test_id }).unwrap();
      if (kind === "final") await updateRules({ courseId: ids.courseId, versionId: ids.versionId, body: { final_test_id: test.test_id } }).unwrap();
      return "published" as const;
    },
    [approveTest, can, ids.courseId, ids.versionId, kind, retireTest, submitTest, updateRules],
  );

  return { create, makeChanges, publish, busy: creating.isLoading || cloning.isLoading };
}
