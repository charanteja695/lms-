import { useCallback } from "react";

import { useApproveQuestionMutation, useCreateQuestionMutation, useSubmitQuestionMutation, useUpdateQuestionMutation } from "@/modules/assessments/questions/api/questionsApi";
import { useReplaceSectionsMutation } from "@/modules/assessments/tests/api/testsApi";
import type { SectionInput, SlotInput } from "@/modules/assessments/tests/sectionTypes";
import type { Test } from "@/modules/assessments/tests/types";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export interface McqDraft {
  /** Set when editing a question already on the test. */
  questionId?: string;
  text: string;
  options: Array<{ id: string; text: string }>;
  correct: string;
  explanation: string;
  marks: number;
}

/** The test's sections as the API takes them back (one "Questions" section when there is none yet). */
function sectionInputs(test: Test): SectionInput[] {
  const sections = test.sections.map((section) => ({
    title: section.title,
    instructions: section.instructions,
    time_limit_minutes: section.time_limit_minutes,
    slots: section.slots.map((slot): SlotInput => ({ slot_type: slot.slot_type, question_id: slot.question_id, criteria: slot.criteria, count: slot.count, marks: slot.marks })),
  }));
  return sections.length ? sections : [{ title: "Questions", slots: [] }];
}

/**
 * Adds, edits and removes the questions of a course test. A new question goes into the bank, is approved (a super
 * admin may approve their own work) and only then placed on the paper, so the paper never holds an unusable question.
 */
export function useTestQuestions(test: Test | undefined) {
  const { can } = useCan();
  const [createQuestion] = useCreateQuestionMutation();
  const [updateQuestion] = useUpdateQuestionMutation();
  const [submitQuestion] = useSubmitQuestionMutation();
  const [approveQuestion] = useApproveQuestionMutation();
  const [replaceSections] = useReplaceSectionsMutation();

  const publishQuestion = useCallback(
    async (questionId: string) => {
      await submitQuestion(questionId).unwrap();
      if (can("content.review")) await approveQuestion({ questionId }).unwrap();
    },
    [approveQuestion, can, submitQuestion],
  );

  const addToPaper = useCallback(
    async (questionId: string, marks: number) => {
      if (!test) return;
      const [first, ...rest] = sectionInputs(test);
      const sections: SectionInput[] = [{ ...(first ?? { title: "Questions", slots: [] }), slots: [...(first?.slots ?? []), { slot_type: "fixed", question_id: questionId, marks }] }, ...rest];
      await replaceSections({ testId: test.test_id, sections }).unwrap();
    },
    [replaceSections, test],
  );

  const removeFromPaper = useCallback(
    async (sectionIndex: number, slotIndex: number) => {
      if (!test) return;
      const sections = sectionInputs(test)
        .map((section, s) => (s === sectionIndex ? { ...section, slots: section.slots.filter((_, i) => i !== slotIndex) } : section))
        .filter((section) => section.slots.length > 0); // a section cannot be empty
      await replaceSections({ testId: test.test_id, sections }).unwrap();
    },
    [replaceSections, test],
  );

  const saveMcq = useCallback(
    async (draft: McqDraft) => {
      const content = { text: draft.text, body: { options: draft.options }, answer_key: { correct: draft.correct }, explanation: draft.explanation || null };
      if (draft.questionId) {
        await updateQuestion({ questionId: draft.questionId, body: { ...content, default_marks: draft.marks } }).unwrap();
        await publishQuestion(draft.questionId);
        return draft.questionId;
      }
      const created = await createQuestion({ question_type: "mcq_single", ...content, default_marks: draft.marks }).unwrap();
      await publishQuestion(created.question_id);
      await addToPaper(created.question_id, draft.marks);
      return created.question_id;
    },
    [addToPaper, createQuestion, publishQuestion, updateQuestion],
  );

  const importMcqs = useCallback(
    async (
      drafts: McqDraft[],
      onProgress?: (completed: number, total: number) => void
    ) => {
      if (!test || !drafts.length) return [];
      const createdSlots: SlotInput[] = [];
      let done = 0;
      for (const draft of drafts) {
        const content = {
          text: draft.text,
          body: { options: draft.options },
          answer_key: { correct: draft.correct },
          explanation: draft.explanation || null,
        };
        const created = await createQuestion({
          question_type: "mcq_single",
          ...content,
          default_marks: draft.marks,
        }).unwrap();
        await publishQuestion(created.question_id);
        createdSlots.push({
          slot_type: "fixed",
          question_id: created.question_id,
          marks: draft.marks,
        });
        done++;
        onProgress?.(done, drafts.length);
      }
      const [first, ...rest] = sectionInputs(test);
      const sections: SectionInput[] = [
        {
          ...(first ?? { title: "Questions", slots: [] }),
          slots: [...(first?.slots ?? []), ...createdSlots],
        },
        ...rest,
      ];
      await replaceSections({ testId: test.test_id, sections }).unwrap();
      return createdSlots;
    },
    [createQuestion, publishQuestion, replaceSections, test]
  );

  return { saveMcq, importMcqs, addToPaper, removeFromPaper, publishQuestion };
}
