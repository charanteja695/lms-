import { useState, useEffect } from "react";
import { Modal, Button, Alert } from "@/shared/ui";
import {
  AssessmentQuestionManager,
  type ManagedQuestionItem,
} from "@/modules/catalog/course-tests/components/AssessmentQuestionManager";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import {
  useCreateTestMutation,
  useUpdateTestMutation,
  useReplaceSectionsMutation,
  useSubmitTestMutation,
  useApproveTestMutation,
  useGetTestQuery,
} from "@/modules/assessments/tests/api/testsApi";
import {
  useCreateQuestionMutation,
  useUpdateQuestionMutation,
  useSubmitQuestionMutation,
  useApproveQuestionMutation,
  useListQuestionsQuery,
} from "@/modules/assessments/questions/api/questionsApi";
import { useUpdateTopicMutation } from "@/modules/catalog/courses/api/curriculumApi";
import { useNotify } from "@/core/hooks/useNotify";
import type { TopicDetail } from "@/modules/catalog/courses/curriculumTypes";

export interface ChapterTestSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  chapter: TopicDetail;
  moduleTitle?: string;
  courseId: string;
  versionId: string;
  moduleId: string;
  onSaved?: () => void;
}

export function ChapterTestSetupModal({
  isOpen,
  onClose,
  chapter,
  moduleTitle,
  courseId,
  versionId,
  moduleId,
  onSaved,
}: ChapterTestSetupModalProps) {
  const notify = useNotify();

  // Test Settings
  const [durationMinutes, setDurationMinutes] = useState(15);
  const [passMarkPercent, setPassMarkPercent] = useState(70);
  const [maxAttempts, setMaxAttempts] = useState(3);

  const [questions, setQuestions] = useState<ManagedQuestionItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Existing test if linked
  const existingTestId = chapter.topic_test_id;
  const { data: existingTest } = useGetTestQuery(
    existingTestId ?? "",
    { skip: !existingTestId, refetchOnMountOrArgChange: true }
  );

  const { data: bankData } = useListQuestionsQuery({ per_page: 100 }, { skip: !isOpen });

  const [createTest] = useCreateTestMutation();
  const [updateTest] = useUpdateTestMutation();
  const [replaceSections] = useReplaceSectionsMutation();
  const [submitTest] = useSubmitTestMutation();
  const [approveTest] = useApproveTestMutation();
  const [createQuestion] = useCreateQuestionMutation();
  const [updateQuestion] = useUpdateQuestionMutation();
  const [submitQuestion] = useSubmitQuestionMutation();
  const [approveQuestion] = useApproveQuestionMutation();
  const [updateTopic] = useUpdateTopicMutation();

  // Initialize questions
  useEffect(() => {
    if (!isOpen) {
      setIsLoaded(false);
      return;
    }
    if (isLoaded) return;

    let loaded: ManagedQuestionItem[] = [];

    // 1. Primary: Load directly from existing test slots in database
    if (existingTest?.sections && existingTest.sections.length > 0) {
      const slots = existingTest.sections.flatMap((s) => s.slots || []);
      if (slots.length > 0) {
        loaded = slots.map((slot, sIdx) => {
          const matched = bankData?.items?.find((q) => String(q.question_id) === String(slot.question_id));
          const opts = (matched as any)?.options?.map((o: any) => ({ id: o.id || "a", text: o.text || "" })) || [
            { id: "a", text: "Option A" },
            { id: "b", text: "Option B" },
            { id: "c", text: "Option C" },
            { id: "d", text: "Option D" },
          ];
          return {
            id: slot.question_id ? String(slot.question_id) : `chap-slot-${sIdx}`,
            text: matched?.text || `Chapter Question #${slot.position || sIdx + 1}`,
            questionType: matched?.question_type || "mcq_single",
            marks: slot.marks || matched?.default_marks || 2,
            options: opts,
            correctAnswer: (matched as any)?.answer_key?.correct || "a",
            explanation: (matched as any)?.explanation || "",
          };
        });
      }
    }

    // 2. Fallback: Try localStorage if test slots were not yet configured
    if (loaded.length === 0) {
      try {
        const saved = localStorage.getItem(`chapter_questions_${chapter.topic_id}`);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) {
            loaded = parsed;
          }
        }
      } catch {
        // ignore
      }
    }

    // 3. Fallback: Seed with 2 default starter questions if completely empty
    if (loaded.length === 0) {
      loaded = [
        {
          id: `draft-chap-seed-1`,
          text: `Which core concept is central to understanding ${chapter.title}?`,
          questionType: "mcq_single",
          marks: 2,
          options: [
            { id: "a", text: "Fundamental architecture and syntax" },
            { id: "b", text: "Deprecation rules" },
            { id: "c", text: "Unrelated external utilities" },
            { id: "d", text: "Non-standard overrides" },
          ],
          correctAnswer: "a",
          explanation: "Mastering the fundamental architecture is essential.",
        },
        {
          id: `draft-chap-seed-2`,
          text: `What is the recommended best practice demonstrated in ${chapter.title}?`,
          questionType: "mcq_single",
          marks: 2,
          options: [
            { id: "a", text: "Write clean, modular, and maintainable code" },
            { id: "b", text: "Bypass error validations" },
            { id: "c", text: "Hardcode credentials" },
            { id: "d", text: "Ignore unit tests" },
          ],
          correctAnswer: "a",
          explanation: "Clean and modular patterns ensure scalability.",
        },
      ];
    }

    if (existingTest) {
      if (existingTest.duration_minutes) setDurationMinutes(existingTest.duration_minutes);
      if (existingTest.pass_mark_percent) setPassMarkPercent(existingTest.pass_mark_percent);
      if (existingTest.max_attempts) setMaxAttempts(existingTest.max_attempts);
    }

    if (loaded.length > 0 || !isLoaded) {
      setQuestions(loaded);
      setIsLoaded(true);
    }
  }, [isOpen, isLoaded, chapter.topic_id, existingTest, bankData]);

  // Persist draft questions to localStorage
  const updateQuestionsAndPersist = (newQuestions: ManagedQuestionItem[]) => {
    setQuestions(newQuestions);
    try {
      localStorage.setItem(`chapter_questions_${chapter.topic_id}`, JSON.stringify(newQuestions));
    } catch {
      // ignore
    }
  };

  const handleSaveQuestion = async (draft: McqDraft & { questionType?: string }) => {
    const newItem: ManagedQuestionItem = {
      id: draft.questionId || `draft-chap-q-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      text: draft.text,
      questionType: draft.questionType || "mcq_single",
      marks: draft.marks,
      options: draft.options,
      correctAnswer: draft.correct,
      explanation: draft.explanation,
    };

    if (draft.questionId) {
      updateQuestionsAndPersist(
        questions.map((q) => (q.id === draft.questionId ? newItem : q))
      );
      notify.success("Question updated");
    } else {
      updateQuestionsAndPersist([...questions, newItem]);
      notify.success("Question added");
    }
  };

  const handleDeleteQuestion = async (questionId?: string, index?: number) => {
    let nextList: ManagedQuestionItem[];
    if (questionId) {
      nextList = questions.filter((q) => q.id !== questionId);
    } else if (index !== undefined) {
      nextList = questions.filter((_, idx) => idx !== index);
    } else {
      return;
    }
    updateQuestionsAndPersist(nextList);
    notify.success("Question removed");
  };

  const handleImportDrafts = async (
    drafts: McqDraft[],
    _onProgress: (completed: number, total: number) => void
  ) => {
    const importedItems: ManagedQuestionItem[] = drafts.map((d, i) => ({
      id: `draft-import-chap-${Date.now()}-${i}`,
      text: d.text,
      questionType: "mcq_single",
      marks: d.marks,
      options: d.options,
      correctAnswer: d.correct,
      explanation: d.explanation,
    }));

    updateQuestionsAndPersist([...questions, ...importedItems]);
    notify.success(`Imported ${drafts.length} questions to Chapter Test!`);
  };

  // Final Save & Publish of Chapter Test
  const handleSaveAndPublishTest = async () => {
    if (questions.length === 0) {
      setSaveError("Please add at least one question to the chapter test.");
      return;
    }

    try {
      setIsSavingAll(true);
      setSaveError(null);

      // 1. Create or retrieve test in assessment service
      let testId = existingTestId;
      if (!testId) {
        const createdTest = await createTest({
          title: `${chapter.title} · Chapter Quiz`,
          kind: "topic",
          target_id: chapter.topic_id,
          duration_minutes: durationMinutes,
          pass_mark_percent: passMarkPercent,
          max_attempts: maxAttempts,
          time_mode: "overall",
          proctoring_level: "none",
        }).unwrap();
        testId = createdTest.test_id;
      } else {
        await updateTest({
          testId,
          body: {
            duration_minutes: durationMinutes,
            pass_mark_percent: passMarkPercent,
            max_attempts: maxAttempts,
          },
        }).unwrap();
      }

      // 2. Create questions in question bank and collect slot inputs
      const slots = [];
      for (const q of questions) {
        try {
          let qid = q.id;
          const isDraftId = !qid || qid.startsWith("draft-") || qid.startsWith("imported-") || qid.startsWith("chap-slot-") || qid.startsWith("auto-");

          if (isDraftId) {
            const createdQ = await createQuestion({
              question_type: "mcq_single",
              text: q.text,
              body: { options: q.options || [] },
              answer_key: { correct: q.correctAnswer || "a" },
              explanation: q.explanation || null,
              default_marks: q.marks,
              topics: [chapter.title.toLowerCase().replace(/\s+/g, "-")],
            }).unwrap();

            try {
              await submitQuestion(createdQ.question_id).unwrap();
              await approveQuestion({ questionId: createdQ.question_id }).unwrap();
            } catch {
              // Already submitted/approved
            }
            qid = createdQ.question_id;
          } else if (qid) {
            try {
              await updateQuestion({
                questionId: qid,
                body: {
                  text: q.text,
                  body: { options: q.options || [] },
                  answer_key: { correct: q.correctAnswer || "a" },
                  explanation: q.explanation || null,
                  default_marks: q.marks,
                },
              }).unwrap();
            } catch (uErr) {
              console.warn("Could not update question in bank:", uErr);
            }
          }

          slots.push({
            slot_type: "fixed" as const,
            question_id: qid,
            marks: q.marks,
          });
        } catch (err: any) {
          console.warn("Could not save question in bank:", err);
        }
      }

      // 3. Attach slots to test paper
      if (slots.length > 0 && testId) {
        await replaceSections({
          testId,
          sections: [
            {
              title: `${chapter.title} Quiz Questions`,
              slots,
            },
          ],
        }).unwrap();
      }

      // 4. Submit & Approve test paper
      if (testId) {
        try {
          await submitTest(testId).unwrap();
          await approveTest({ testId }).unwrap();
        } catch (approveErr) {
          console.warn("Test submission/approval notice:", approveErr);
        }
      }

      // 5. Link test to chapter in catalog service
      if (testId) {
        await updateTopic({
          courseId,
          versionId,
          moduleId,
          topicId: chapter.topic_id,
          body: {
            topic_test_id: testId,
            pass_mark: passMarkPercent,
          },
        }).unwrap();
      }

      notify.success("Chapter Test configured and linked successfully!");
      if (onSaved) onSaved();
      onClose();
    } catch (err: any) {
      console.error("Save chapter test error:", err);
      setSaveError(err?.data?.message || err?.message || "Failed to configure chapter test.");
    } finally {
      setIsSavingAll(false);
    }
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={`Configure Chapter Test: ${chapter.title}`}
      size="xl"
    >
      <div className="space-y-6 max-h-[80vh] overflow-y-auto px-1 pr-2">
        {saveError && (
          <Alert tone="danger" title="Configuration Error">
            {saveError}
          </Alert>
        )}

        {/* Test Parameters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Duration (Minutes)
            </label>
            <input
              type="number"
              min={5}
              max={180}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Pass Mark (%)
            </label>
            <input
              type="number"
              min={10}
              max={100}
              value={passMarkPercent}
              onChange={(e) => setPassMarkPercent(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Max Retake Attempts
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={maxAttempts}
              onChange={(e) => setMaxAttempts(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Total Questions
            </label>
            <div className="flex items-center gap-2 pt-1.5">
              <span className="text-sm font-bold text-navy-950">{questions.length} Questions</span>
              {chapter.topic_test_id && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Linked
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Questions Manager */}
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <div>
              <h4 className="text-sm font-bold text-slate-900">Chapter Test Question Paper</h4>
              <p className="text-xs text-slate-500">
                {moduleTitle ? `${moduleTitle} · ` : ""}Add, edit, or import multiple-choice questions for this chapter.
              </p>
            </div>
          </div>

          <AssessmentQuestionManager
            contextTitle={chapter.title}
            contextType="chapter"
            questions={questions}
            onSaveQuestion={handleSaveQuestion}
            onDeleteQuestion={handleDeleteQuestion}
            onImportDrafts={handleImportDrafts}
          />
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-200">
          <Button variant="secondary" onClick={onClose} disabled={isSavingAll}>
            Cancel
          </Button>

          <Button
            variant="primary"
            onClick={handleSaveAndPublishTest}
            loading={isSavingAll}
            className="gap-2"
          >
            Save & Link Chapter Test
          </Button>
        </div>
      </div>
    </Modal>
  );
}
