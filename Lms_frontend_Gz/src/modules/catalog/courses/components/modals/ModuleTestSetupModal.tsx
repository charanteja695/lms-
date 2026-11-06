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
import { useUpdateModuleMutation } from "@/modules/catalog/courses/api/curriculumApi";
import { useNotify } from "@/core/hooks/useNotify";
import type { ModuleDetail } from "@/modules/catalog/courses/curriculumTypes";

export interface ModuleTestSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  module: ModuleDetail;
  courseId: string;
  versionId: string;
  onSaved?: () => void;
}

export function ModuleTestSetupModal({
  isOpen,
  onClose,
  module,
  courseId,
  versionId,
  onSaved,
}: ModuleTestSetupModalProps) {
  const notify = useNotify();

  // Test Settings
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [passMarkPercent, setPassMarkPercent] = useState(70);
  const [maxAttempts, setMaxAttempts] = useState(3);
  const [targetQuestionCount, setTargetQuestionCount] = useState(1);

  const [questions, setQuestions] = useState<ManagedQuestionItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Existing test if linked
  const existingTestId = module.module_test_id;
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
  const [updateModule] = useUpdateModuleMutation();

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
        setTargetQuestionCount(slots.length);
        loaded = slots.map((slot, sIdx) => {
          const matched = bankData?.items?.find((q) => String(q.question_id) === String(slot.question_id));
          const opts = (matched as any)?.options?.map((o: any) => ({ id: o.id || "a", text: o.text || "" })) || [
            { id: "a", text: "Option A" },
            { id: "b", text: "Option B" },
            { id: "c", text: "Option C" },
            { id: "d", text: "Option D" },
          ];
          return {
            id: slot.question_id ? String(slot.question_id) : `mod-slot-${sIdx}`,
            text: matched?.text || `Module Question #${slot.position || sIdx + 1}`,
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
        const saved = localStorage.getItem(`module_questions_${module.module_id}`);
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

    if (existingTest) {
      if (existingTest.duration_minutes) setDurationMinutes(existingTest.duration_minutes);
      if (existingTest.pass_mark_percent) setPassMarkPercent(existingTest.pass_mark_percent);
      if (existingTest.max_attempts) setMaxAttempts(existingTest.max_attempts);
    }

    if (loaded.length > 0 || !isLoaded) {
      setQuestions(loaded);
      setIsLoaded(true);
    }
  }, [isOpen, isLoaded, module.module_id, existingTest, bankData]);

  // Persist draft questions to localStorage
  const updateQuestionsAndPersist = (newQuestions: ManagedQuestionItem[]) => {
    setQuestions(newQuestions);
    try {
      localStorage.setItem(`module_questions_${module.module_id}`, JSON.stringify(newQuestions));
    } catch {
      // ignore
    }
  };

  const handleSaveQuestion = async (draft: McqDraft & { questionType?: string }) => {
    const newItem: ManagedQuestionItem = {
      id: draft.questionId || `draft-mod-q-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
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
      id: `draft-import-mod-${Date.now()}-${i}`,
      text: d.text,
      questionType: "mcq_single",
      marks: d.marks,
      options: d.options,
      correctAnswer: d.correct,
      explanation: d.explanation,
    }));

    updateQuestionsAndPersist([...questions, ...importedItems]);
    notify.success(`Imported ${drafts.length} questions to Module Test!`);
  };

  // Final Save & Publish of Module Test
  const handleSaveAndPublishTest = async () => {
    if (questions.length === 0) {
      setSaveError("Please add at least one question to the module test.");
      return;
    }

    if (targetQuestionCount && questions.length < targetQuestionCount) {
      setSaveError(
        `Configured question count is ${targetQuestionCount}. Please add ${targetQuestionCount - questions.length} more question(s) before publishing.`
      );
      return;
    }

    try {
      setIsSavingAll(true);
      setSaveError(null);

      // 1. Create or retrieve test in assessment service
      let testId = existingTestId;
      if (!testId) {
        const createdTest = await createTest({
          title: `${module.title} · Module Assessment`,
          kind: "module",
          target_id: module.module_id,
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
          const isDraftId = !qid || qid.startsWith("draft-") || qid.startsWith("imported-") || qid.startsWith("mod-slot-") || qid.startsWith("auto-");

          if (isDraftId) {
            const createdQ = await createQuestion({
              question_type: "mcq_single",
              text: q.text,
              body: { options: q.options || [] },
              answer_key: { correct: q.correctAnswer || "a" },
              explanation: q.explanation || null,
              default_marks: q.marks,
              topics: [module.title.toLowerCase().replace(/\s+/g, "-")],
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
      if (slots.length > 0) {
        await replaceSections({
          testId,
          sections: [
            {
              title: "Module Questions",
              slots,
            },
          ],
        }).unwrap();
      }

      // 4. Submit and approve test
      try {
        await submitTest(testId).unwrap();
        await approveTest({ testId }).unwrap();
      } catch {
        // Already published
      }

      // 5. Link module_test_id to module in Catalog Service
      await updateModule({
        courseId,
        versionId,
        moduleId: module.module_id,
        body: {
          module_test_id: testId,
          pass_mark: passMarkPercent,
        },
      }).unwrap();

      notify.success("Module test configured and published successfully!");
      onSaved?.();
      onClose();
    } catch (err: any) {
      setSaveError(err?.message || "Failed to save and publish module test.");
    } finally {
      setIsSavingAll(false);
    }
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={`Module Test · ${module.title}`}
      size="xl"
    >
      <div className="space-y-6">
        {saveError && <Alert tone="error">{saveError}</Alert>}

        {/* Timing & Rules Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4.5 space-y-4 shadow-2xs">
          <h5 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Test Configuration
          </h5>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Duration (Mins)
              </label>
              <input
                type="number"
                min={5}
                max={180}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Pass Mark (%)
              </label>
              <input
                type="number"
                min={40}
                max={100}
                value={passMarkPercent}
                onChange={(e) => setPassMarkPercent(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Max Attempts
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={maxAttempts}
                onChange={(e) => setMaxAttempts(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Target Question Count
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={targetQuestionCount}
                onChange={(e) => setTargetQuestionCount(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Unified Question Management Area */}
        <AssessmentQuestionManager
          questions={questions}
          contextTitle={module.title}
          contextType="module"
          targetQuestionCount={targetQuestionCount}
          onSaveQuestion={handleSaveQuestion}
          onDeleteQuestion={handleDeleteQuestion}
          onImportDrafts={handleImportDrafts}
        />

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSavingAll}>
            Cancel
          </Button>
          <Button
            type="button"
            loading={isSavingAll}
            onClick={() => void handleSaveAndPublishTest()}
            className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold"
          >
            Save & Publish Module Test
          </Button>
        </div>
      </div>
    </Modal>
  );
}
