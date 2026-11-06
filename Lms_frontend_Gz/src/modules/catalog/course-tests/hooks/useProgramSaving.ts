import { useCallback } from "react";

import { useCreateQuestionMutation } from "@/modules/assessments/questions/api/questionsApi";
import type { Difficulty } from "@/modules/code-execution/common/types";
import { useBulkCreateTestCasesMutation, useCreateProblemMutation, usePublishProblemMutation } from "@/modules/code-execution/problems/api/problemsApi";
import type { useTestQuestions } from "@/modules/catalog/course-tests/hooks/useTestQuestions";

export interface CaseDraft {
  input: string;
  expected: string;
}

export interface ProgramDraft {
  title: string;
  difficulty: Difficulty;
  marks: number;
  timeLimitMs: number;
  statement: string;
  inputFormat: string;
  outputFormat: string;
  constraints: string;
  languages: string[];
  samples: CaseDraft[];
  hidden: CaseDraft[];
  /** Hackathon rule: marks only when every test case passes. Otherwise marks per case passed. */
  allOrNothing: boolean;
}

/** One statement for the learner: the task, then its input, output and limits. */
function statementOf(draft: ProgramDraft): string {
  const parts = [draft.statement.trim()];
  if (draft.inputFormat.trim()) parts.push(`### Input\n${draft.inputFormat.trim()}`);
  if (draft.outputFormat.trim()) parts.push(`### Output\n${draft.outputFormat.trim()}`);
  if (draft.constraints.trim()) parts.push(`### Constraints\n${draft.constraints.trim()}`);
  return parts.join("\n\n");
}

/**
 * A program on a course test is a problem in code-execution-service (statement + test cases) plus a coding question
 * in assessment-service pointing at it. Saving creates and publishes both, then puts the question on the paper.
 */
export function useProgramSaving(questions: ReturnType<typeof useTestQuestions>) {
  const [createProblem] = useCreateProblemMutation();
  const [bulkCreateCases] = useBulkCreateTestCasesMutation();
  const [publishProblem] = usePublishProblemMutation();
  const [createQuestion] = useCreateQuestionMutation();

  return useCallback(
    async (draft: ProgramDraft) => {
      const problem = await createProblem({
        title: draft.title.trim(),
        statement: statementOf(draft),
        difficulty: draft.difficulty,
        time_limit_ms: draft.timeLimitMs,
        allowed_languages: draft.languages,
      }).unwrap();
      const cases = [
        ...draft.samples.map((c) => ({ input: c.input, expected: c.expected, is_sample: true })),
        ...draft.hidden.map((c) => ({ input: c.input, expected: c.expected, is_sample: false })),
      ];
      await bulkCreateCases({ problemId: problem.problem_id, testCases: cases }).unwrap();
      await publishProblem(problem.problem_id).unwrap();
      const question = await createQuestion({
        question_type: "coding",
        text: draft.title.trim(),
        body: { problem_id: problem.problem_id, languages: draft.languages },
        answer_key: { scoring: draft.allOrNothing ? "all_or_nothing" : "partial" },
        default_marks: draft.marks,
      }).unwrap();
      await questions.publishQuestion(question.question_id);
      await questions.addToPaper(question.question_id, draft.marks);
      return question.question_id;
    },
    [bulkCreateCases, createProblem, createQuestion, publishProblem, questions],
  );
}
