import { useState, useMemo, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useUpdateTopicMutation } from "@/modules/catalog/courses/api/curriculumApi";
import {
  useGetTestQuery,
  useCreateTestMutation,
  useReplaceSectionsMutation,
  useSubmitTestMutation,
  useApproveTestMutation,
} from "@/modules/assessments/tests/api/testsApi";
import {
  useListQuestionsQuery,
  useCreateQuestionMutation,
  useUpdateQuestionMutation,
  useSubmitQuestionMutation,
  useApproveQuestionMutation,
  useImportQuestionsMutation,
} from "@/modules/assessments/questions/api/questionsApi";
import { ManualQuestionModal } from "@/modules/catalog/course-tests/components/ManualQuestionModal";
import { UnifiedImportQuestionsModal } from "@/modules/catalog/course-tests/components/UnifiedImportQuestionsModal";
import { AutoGenerateQuestionsModal } from "@/modules/catalog/course-tests/components/AutoGenerateQuestionsModal";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { CoursePageHeader } from "@/modules/catalog/courses/components/common/CoursePageHeader";
import { Button, Icon, PageLoader } from "@/shared/ui";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";

export interface ReviewItem {
  id?: string;
  type: "mcq" | "coding";
  question: string;
  options?: string[];
  correctAnswerIndex?: number;
  testCases?: string;
  explanation: string;
  marks: number;
  difficulty?: "Easy" | "Medium" | "Hard";
  status: "approved" | "pending";
}

export function QuestionReviewPage() {
  const { courseId, moduleId, chapterId } = useParams<{
    courseId: string;
    moduleId: string;
    chapterId: string;
  }>();
  const navigate = useNavigate();
  const notify = useNotify();

  const { data: course, isLoading: isCourseLoading } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
  });
  const versionId = course?.versions?.[course.versions.length - 1]?.version_id;

  const { data: versionDetail, isLoading: isVersionLoading } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId }
  );

  const currentModule = versionDetail?.modules?.find((m) => m.module_id === moduleId) || versionDetail?.modules?.[0];
  const currentChapter = currentModule?.topics?.find((t) => t.topic_id === chapterId) || currentModule?.topics?.[0];

  const resolvedModuleId = moduleId || currentModule?.module_id;
  const resolvedChapterId = chapterId || currentChapter?.topic_id;
  const topicTestId = currentChapter?.topic_test_id;

  // Real test definition query from assessment service
  const { data: testDefinition, refetch: refetchTest } = useGetTestQuery(
    topicTestId ? String(topicTestId) : "",
    { skip: !topicTestId, refetchOnMountOrArgChange: true }
  );

  // Real question bank query from assessment service
  const { data: existingBankData, refetch: refetchBank } = useListQuestionsQuery(
    { per_page: 100 },
    { refetchOnMountOrArgChange: true }
  );

  const [createTest] = useCreateTestMutation();
  const [replaceSections] = useReplaceSectionsMutation();
  const [submitTest] = useSubmitTestMutation();
  const [approveTest] = useApproveTestMutation();
  const [createQuestion] = useCreateQuestionMutation();
  const [updateQuestion] = useUpdateQuestionMutation();
  const [submitQuestion] = useSubmitQuestionMutation();
  const [approveQuestion] = useApproveQuestionMutation();
  const [updateTopic] = useUpdateTopicMutation();

  // Initialize questions
  const [questions, setQuestions] = useState<ReviewItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    let loaded: ReviewItem[] = [];

    // 1. Primary: Load directly from backend test definition slots
    if (testDefinition?.sections && testDefinition.sections.length > 0) {
      const slots = testDefinition.sections.flatMap((s) => s.slots || []);
      if (slots.length > 0) {
        loaded = slots.map((slot, sIdx) => {
          const matched = existingBankData?.items?.find((q) => String(q.question_id) === String(slot.question_id));
          const opts = (matched as any)?.options?.map((o: any) => o.text) || [
            "Option A",
            "Option B",
            "Option C",
            "Option D",
          ];
          return {
            id: slot.question_id ? String(slot.question_id) : `q-slot-${sIdx}`,
            type: matched?.question_type === "coding" ? ("coding" as const) : ("mcq" as const),
            question: matched?.text || `Question #${slot.position || sIdx + 1}`,
            options: opts,
            correctAnswerIndex: 0,
            explanation: (matched as any)?.explanation || "",
            marks: slot.marks || matched?.default_marks || 2,
            difficulty: (matched && matched.difficulty <= 2
              ? "Easy"
              : matched && matched.difficulty >= 4
              ? "Hard"
              : "Medium") as any,
            status: "approved" as const,
          };
        });
      }
    }

    // 2. Fallback: Check if user generated or added questions for this chapter in local storage
    if (loaded.length === 0 && resolvedChapterId) {
      try {
        const saved = localStorage.getItem(`generated_questions_${resolvedChapterId}`);
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

    // 3. Fallback: check existing bank questions matching this course topic
    if (loaded.length === 0 && existingBankData?.items && existingBankData.items.length > 0) {
      const slug = course?.slug?.toLowerCase() || "";
      const matched = existingBankData.items.filter(
        (q) =>
          q.topics &&
          q.topics.some((t) => slug.includes(t.toLowerCase()) || t.toLowerCase().includes(slug))
      );

      const pool = matched.length > 0 ? matched : [];
      if (pool.length > 0) {
        loaded = pool.map((q) => {
          const opts = (q as any).options?.map((o: any) => o.text) || [];
          return {
            id: q.question_id,
            type: q.question_type === "coding" ? "coding" : "mcq",
            question: q.text,
            options: opts,
            correctAnswerIndex: 0,
            explanation: (q as any).explanation || "",
            marks: q.default_marks || 2,
            difficulty: q.difficulty <= 2 ? "Easy" : q.difficulty >= 4 ? "Hard" : "Medium",
            status: "approved" as const,
          };
        });
      }
    }

    if (loaded.length > 0 || !isLoaded) {
      setQuestions(loaded);
      setIsLoaded(true);
    }
  }, [testDefinition, existingBankData?.items, resolvedChapterId, course?.slug, isLoaded]);

  // Persist questions to storage
  const persistQuestions = (newQuestions: ReviewItem[]) => {
    setQuestions(newQuestions);
    setHasPublishedSuccess(false);
    if (resolvedChapterId) {
      try {
        localStorage.setItem(`generated_questions_${resolvedChapterId}`, JSON.stringify(newQuestions));
      } catch {
        // ignore
      }
    }
  };

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<{ item: ReviewItem; index: number } | null>(null);
  const [deletingQuestion, setDeletingQuestion] = useState<ReviewItem | null>(null);

  const [importQuestions, { isLoading: isPublishing }] = useImportQuestionsMutation();
  const [hasPublishedSuccess, setHasPublishedSuccess] = useState(false);

  const approvedCount = useMemo(() => questions.filter((q) => q.status === "approved").length, [questions]);
  const pendingCount = useMemo(() => questions.filter((q) => q.status === "pending").length, [questions]);
  const totalMarks = useMemo(() => questions.reduce((acc, q) => acc + q.marks, 0), [questions]);

  const handleApprove = (id?: string) => {
    if (!id) return;
    persistQuestions(
      questions.map((q) => (q.id === id ? { ...q, status: "approved" as const } : q))
    );
    notify.success("Question approved");
  };

  const handleApproveAll = () => {
    persistQuestions(questions.map((q) => ({ ...q, status: "approved" as const })));
    notify.success("All questions marked approved!");
  };

  const handleRegenerate = (id?: string) => {
    if (!id) return;
    persistQuestions(
      questions.map((q) => {
        if (q.id !== id) return q;
        return {
          ...q,
          question: `${q.question} (Regenerated)`,
          status: "pending" as const,
        };
      })
    );
    notify.success("Question regenerated with AI!");
  };

  const handleRegenerateAll = () => {
    persistQuestions(
      questions.map((q) => ({
        ...q,
        question: `${q.question} (Regenerated)`,
        status: "pending" as const,
      }))
    );
    notify.success("All questions refreshed!");
  };

  // Manual Add or Edit handler
  const handleSaveManualQuestion = async (draft: McqDraft & { questionType?: string }) => {
    const isCoding = draft.questionType === "coding";
    const correctLetter = (draft.correct || "a").toLowerCase();
    const correctIdx = correctLetter.charCodeAt(0) - 97;
    const options = (draft.options || []).map((o, idx) => ({
      id: String.fromCharCode(97 + idx),
      text: o.text,
    }));

    try {
      let savedQuestionId = draft.questionId;

      if (editingQuestion && editingQuestion.item.id && !editingQuestion.item.id.startsWith("q-")) {
        // Update question in backend
        await updateQuestion({
          questionId: editingQuestion.item.id,
          body: {
            text: draft.text,
            body: isCoding
              ? { language: "javascript", starter_code: "// solution\n" }
              : { options },
            answer_key: isCoding
              ? { test_cases: [{ input: "1", expected: "1", is_hidden: false }] }
              : { correct: correctLetter },
            explanation: draft.explanation || null,
            default_marks: draft.marks,
          },
        }).unwrap();
        savedQuestionId = editingQuestion.item.id;
      } else {
        // Create new question in backend
        const created = await createQuestion({
          question_type: isCoding ? "coding" : "mcq_single",
          text: draft.text,
          body: isCoding
            ? { language: "javascript", starter_code: "// solution\n" }
            : { options },
          answer_key: isCoding
            ? { test_cases: [{ input: "1", expected: "1", is_hidden: false }] }
            : { correct: correctLetter },
          explanation: draft.explanation || null,
          default_marks: draft.marks,
          topics: [course?.slug || "chapter-test"],
        }).unwrap();
        savedQuestionId = created.question_id;

        try {
          await submitQuestion(created.question_id).unwrap();
          await approveQuestion({ questionId: created.question_id }).unwrap();
        } catch {}
      }

      // Ensure test exists and slot is synced
      let currentTestId = topicTestId;
      if (!currentTestId) {
        const newTest = await createTest({
          title: `${chapterTitle} Exam`,
          kind: "topic",
          target_id: resolvedChapterId,
          duration_minutes: 15,
          pass_mark_percent: 60,
          max_attempts: 3,
          time_mode: "overall",
          proctoring_level: "none",
          sections: [
            {
              title: "Chapter Assessment",
              slots: [{ slot_type: "fixed", question_id: savedQuestionId, count: 1, marks: draft.marks }],
            },
          ],
        }).unwrap();
        currentTestId = newTest.test_id;

        try {
          await submitTest(newTest.test_id).unwrap();
          await approveTest({ testId: newTest.test_id }).unwrap();
        } catch {}

        if (courseId && versionId && resolvedModuleId && resolvedChapterId) {
          await updateTopic({
            courseId,
            versionId,
            moduleId: resolvedModuleId,
            topicId: resolvedChapterId,
            body: { topic_test_id: newTest.test_id },
          }).unwrap();
        }
      } else {
        const cleanSlot = (s: any) => ({
          slot_type: s.slot_type || "fixed",
          question_id: s.question_id,
          count: s.count || 1,
          marks: s.marks || 1,
        });
        const existingSlots = (testDefinition?.sections?.[0]?.slots || []).map(cleanSlot);
        let nextSlots;
        if (editingQuestion) {
          nextSlots = existingSlots.map((s) =>
            s.question_id === savedQuestionId ? { ...s, marks: draft.marks } : s
          );
        } else {
          const filtered = existingSlots.filter((s) => s.question_id !== savedQuestionId);
          nextSlots = [
            ...filtered,
            { slot_type: "fixed" as const, question_id: savedQuestionId, count: 1, marks: draft.marks },
          ];
        }

        await replaceSections({
          testId: String(currentTestId),
          sections: [{ title: "Chapter Assessment", slots: nextSlots }],
        }).unwrap();
      }

      refetchBank();
      refetchTest();

      const newItem: ReviewItem = {
        id: savedQuestionId,
        type: isCoding ? "coding" : "mcq",
        question: draft.text,
        options: draft.options?.map((o) => o.text) || [],
        correctAnswerIndex: Math.max(0, Math.min(3, correctIdx)),
        explanation: draft.explanation || "",
        marks: draft.marks,
        difficulty: "Medium",
        status: "approved",
      };

      if (editingQuestion) {
        const updated = [...questions];
        updated[editingQuestion.index] = newItem;
        persistQuestions(updated);
        notify.success("Question updated and persisted to backend database!");
        setEditingQuestion(null);
      } else {
        persistQuestions([...questions, newItem]);
        notify.success("Question created and persisted to backend database!");
        setIsAddModalOpen(false);
      }
    } catch (err: any) {
      console.error("Failed to persist manual question to backend:", err);
      notify.apiError(err);
    }
  };

  // Bulk Import handler
  const handleImportDrafts = async (
    drafts: McqDraft[],
    _onProgress: (completed: number, total: number) => void
  ) => {
    try {
      const createdIds: string[] = [];
      const newItems: ReviewItem[] = [];

      for (const draft of drafts) {
        if (!draft) continue;
        const correctLetter = (draft.correct || "a").toLowerCase();
        const correctIdx = correctLetter.charCodeAt(0) - 97;
        const options = (draft.options || []).map((o, idx) => ({
          id: String.fromCharCode(97 + idx),
          text: o.text,
        }));

        const created = await createQuestion({
          question_type: "mcq_single",
          text: draft.text,
          body: { options },
          answer_key: { correct: correctLetter },
          explanation: draft.explanation || null,
          default_marks: draft.marks,
          topics: [course?.slug || "chapter-test"],
        }).unwrap();

        try {
          await submitQuestion(created.question_id).unwrap();
          await approveQuestion({ questionId: created.question_id }).unwrap();
        } catch {}

        createdIds.push(created.question_id);
        newItems.push({
          id: created.question_id,
          type: "mcq",
          question: draft.text,
          options: draft.options?.map((o) => o.text) || [],
          correctAnswerIndex: Math.max(0, Math.min(3, correctIdx)),
          explanation: draft.explanation || "",
          marks: draft.marks,
          difficulty: "Medium",
          status: "approved",
        });
      }

      // Sync with test slots
      let currentTestId = topicTestId;
      if (!currentTestId) {
        const newTest = await createTest({
          title: `${chapterTitle} Exam`,
          kind: "topic",
          target_id: resolvedChapterId,
          duration_minutes: 15,
          pass_mark_percent: 60,
          max_attempts: 3,
          time_mode: "overall",
          proctoring_level: "none",
          sections: [
            {
              title: "Chapter Assessment",
              slots: createdIds.map((qid) => ({ slot_type: "fixed" as const, question_id: qid, count: 1, marks: 2 })),
            },
          ],
        }).unwrap();
        currentTestId = newTest.test_id;

        try {
          await submitTest(newTest.test_id).unwrap();
          await approveTest({ testId: newTest.test_id }).unwrap();
        } catch {}

        if (courseId && versionId && resolvedModuleId && resolvedChapterId) {
          await updateTopic({
            courseId,
            versionId,
            moduleId: resolvedModuleId,
            topicId: resolvedChapterId,
            body: { topic_test_id: newTest.test_id },
          }).unwrap();
        }
      } else {
        const cleanSlot = (s: any) => ({
          slot_type: s.slot_type || "fixed",
          question_id: s.question_id,
          count: s.count || 1,
          marks: s.marks || 1,
        });
        const existingSlots = (testDefinition?.sections?.[0]?.slots || []).map(cleanSlot);
        const existingQids = new Set(existingSlots.map((s) => s.question_id));
        const newSlots = createdIds
          .filter((qid) => !existingQids.has(qid))
          .map((qid) => ({ slot_type: "fixed" as const, question_id: qid, count: 1, marks: 2 }));
        const nextSlots = [...existingSlots, ...newSlots];

        await replaceSections({
          testId: String(currentTestId),
          sections: [{ title: "Chapter Assessment", slots: nextSlots }],
        }).unwrap();
      }

      refetchBank();
      refetchTest();
      persistQuestions([...questions, ...newItems]);
      notify.success(`Successfully imported and persisted ${drafts.length} questions to database!`);
    } catch (err: any) {
      console.error("Bulk import persistence error:", err);
      notify.apiError(err);
    }
  };

  const handleDeleteQuestion = async () => {
    if (!deletingQuestion) return;
    try {
      if (topicTestId) {
        const cleanSlot = (s: any) => ({
          slot_type: s.slot_type || "fixed",
          question_id: s.question_id,
          count: s.count || 1,
          marks: s.marks || 1,
        });
        const existingSlots = (testDefinition?.sections?.[0]?.slots || []).map(cleanSlot);
        const nextSlots = existingSlots.filter((s) => String(s.question_id) !== String(deletingQuestion.id));
        if (nextSlots.length > 0) {
          await replaceSections({
            testId: String(topicTestId),
            sections: [{ title: "Chapter Assessment", slots: nextSlots }],
          }).unwrap();
        }
      }
      refetchBank();
      refetchTest();
      persistQuestions(questions.filter((q) => String(q.id) !== String(deletingQuestion.id)));
      notify.success("Question removed and updated in database!");
      setDeletingQuestion(null);
    } catch (err: any) {
      console.error("Failed to delete question from backend:", err);
      notify.apiError(err);
    }
  };

  const handlePublishApproved = async () => {
    const approved = questions.filter((q) => q.status === "approved");
    if (approved.length === 0) {
      notify.error("No approved questions to publish. Please approve questions first.");
      return;
    }

    try {
      const qList = approved.map((q) => {
        if (q.type === "coding") {
          return {
            question_type: "coding",
            text: q.question,
            body: {
              language: "javascript",
              starter_code: "// Write your solution below\n",
              ...(q.explanation?.trim() ? { description: q.explanation.trim() } : {}),
            },
            answer_key: {
              test_cases: [
                { input: "1", expected: "1", is_hidden: false }
              ],
            },
            default_marks: Number(q.marks) || 10,
            difficulty: q.difficulty === "Easy" ? 1 : q.difficulty === "Hard" ? 5 : 3,
            topics: [course?.slug?.trim() || "general"],
            ...(q.explanation?.trim() ? { explanation: q.explanation.trim() } : {}),
          };
        } else {
          const options = (q.options || []).map((optText, oIdx) => ({
            id: String.fromCharCode(97 + oIdx), // 'a', 'b', 'c', 'd'
            text: optText,
          }));
          const correctId = String.fromCharCode(97 + (q.correctAnswerIndex ?? 0));
          return {
            question_type: "mcq_single",
            text: q.question,
            body: { options },
            answer_key: { correct: correctId },
            ...(q.explanation?.trim() ? { explanation: q.explanation.trim() } : {}),
            default_marks: Number(q.marks) || 2,
            difficulty: q.difficulty === "Easy" ? 1 : q.difficulty === "Hard" ? 5 : 3,
            topics: [course?.slug?.trim() || "general"],
            ...(q.explanation?.trim() ? { explanation: q.explanation.trim() } : {}),
          };
        }
      });

      const res = await importQuestions({
        questions: qList,
        key: "pub-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8),
      }).unwrap();

      notify.success(`Successfully published ${res.created} questions to the Assessment Bank!`);
      setHasPublishedSuccess(true);
      refetchBank();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  if (isCourseLoading || isVersionLoading) {
    return <PageLoader label="Loading question review..." />;
  }

  const moduleTitle = currentModule?.title || "Module";
  const chapterTitle = currentChapter?.title || "Chapter";

  const backUrl =
    courseId && resolvedModuleId
      ? `/courses/${courseId}/modules/${resolvedModuleId}/chapters`
      : `/courses/${courseId}`;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* 1. Universal Breadcrumbs & Back Navigation Header */}
      <CoursePageHeader
        breadcrumbs={[
          { label: "Courses", href: "/courses" },
          { label: course?.title || "Course", href: `/courses/${courseId}` },
          { label: moduleTitle, href: `/courses/${courseId}?tab=modules` },
          { label: chapterTitle, href: backUrl },
          { label: "Chapter Test Questions", current: true },
        ]}
        title={`Chapter Test Questions · ${chapterTitle}`}
        description="Step 4 of 5: Add questions manually, import in bulk via Excel/CSV/JSON, or auto-generate with AI."
        backHref={backUrl}
        actions={
          <div className="flex items-center gap-2">
            {questions.length > 0 && (
              <button
                type="button"
                onClick={handlePublishApproved}
                disabled={isPublishing || approvedCount === 0 || hasPublishedSuccess}
                className={cn(
                  "inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold shadow-xs transition-colors",
                  hasPublishedSuccess
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-300 cursor-default"
                    : "bg-[#00663C] text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer"
                )}
              >
                <Icon
                  name={isPublishing ? "refresh" : "check"}
                  size={14}
                  className={isPublishing ? "animate-spin" : ""}
                />
                <span>
                  {isPublishing
                    ? "Publishing..."
                    : hasPublishedSuccess
                    ? `Published to bank (${approvedCount})`
                    : `Publish ${approvedCount} approved to bank`}
                </span>
              </button>
            )}
            <button
              type="button"
              onClick={() => navigate(`/courses/${courseId}?tab=final_exam&step=5`)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-900 text-xs font-bold text-white hover:bg-slate-800 cursor-pointer shadow-xs"
            >
              <span>Continue to Step 5 (Final exam)</span>
              <Icon name="arrow-right" size={14} />
            </button>
          </div>
        }
      />

      {/* 2. Top Question Creation Options Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div>
          <h4 className="text-sm font-bold text-[#0A1530]">Question Management</h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Three independent ways to build your chapter test questions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Option 1: + Add Question */}
          <Button
            type="button"
            icon="plus"
            onClick={() => setIsAddModalOpen(true)}
            className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold text-xs shadow-2xs"
          >
            + Add Question
          </Button>

          {/* Option 2: Import Questions */}
          <Button
            type="button"
            variant="secondary"
            icon="fileSpreadsheet"
            onClick={() => setIsImportModalOpen(true)}
            className="border-slate-300 bg-white text-slate-700 hover:bg-slate-50 font-bold text-xs"
          >
            Import Questions
          </Button>

          {/* Option 3: Auto-Generate Questions */}
          <Button
            type="button"
            variant="secondary"
            icon="sparkles"
            onClick={() => setIsAiModalOpen(true)}
            className="border-indigo-200 bg-indigo-50/70 text-indigo-700 hover:bg-indigo-100 font-bold text-xs"
          >
            Auto-Generate Questions
          </Button>
        </div>
      </div>

      {/* Success Banner after publishing */}
      {hasPublishedSuccess && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#00663C] text-white flex items-center justify-center shrink-0">
              <Icon name="check" size={16} />
            </div>
            <div>
              <h4 className="text-xs font-bold text-[#00663C]">Questions Published to Assessment Bank!</h4>
              <p className="text-[11px] text-emerald-800">
                Step 4 is complete. You can now configure the Final Exam in Step 5 using these questions.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate(`/courses/${courseId}?tab=final_exam&step=5`)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
          >
            <span>Continue to Step 5 (Final exam)</span>
            <Icon name="arrow-right" size={14} />
          </button>
        </div>
      )}

      {/* When Empty: Clean empty state with the 3 creation options */}
      {questions.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-14 text-center shadow-2xs">
          <Icon name="clipboardCheck" size={36} className="mx-auto text-slate-300 mb-3" />
          <h3 className="text-base font-bold text-slate-900 mb-1">No questions added yet</h3>
          <p className="text-xs text-slate-500 mb-6 max-w-md mx-auto leading-relaxed">
            Enter a question manually, import multiple questions from an Excel, CSV, or JSON file, or generate questions automatically from chapter materials.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              type="button"
              icon="plus"
              onClick={() => setIsAddModalOpen(true)}
              className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold"
            >
              + Add Question
            </Button>
            <Button
              type="button"
              variant="secondary"
              icon="fileSpreadsheet"
              onClick={() => setIsImportModalOpen(true)}
            >
              Import Questions
            </Button>
            <Button
              type="button"
              variant="secondary"
              icon="sparkles"
              onClick={() => setIsAiModalOpen(true)}
            >
              Auto-Generate Questions
            </Button>
          </div>
        </div>
      ) : (
        <>
          {/* Status Bar */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4 text-xs">
              <span className="font-bold text-[#0A1530]">{questions.length} total questions</span>
              <span className="text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full font-bold">
                {approvedCount} approved
              </span>
              {pendingCount > 0 && (
                <span className="text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full font-bold">
                  {pendingCount} pending
                </span>
              )}
              <span className="text-slate-400 font-medium">{totalMarks} total marks</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRegenerateAll}
                className="px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Regenerate all
              </button>
              <button
                type="button"
                onClick={handleApproveAll}
                className="px-3.5 py-1.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
              >
                Approve all
              </button>
            </div>
          </div>

          {/* Question List */}
          <div className="space-y-4">
            {questions.map((q, idx) => {
              const isApproved = q.status === "approved";

              return (
                <div
                  key={q.id || idx}
                  className={cn(
                    "rounded-2xl border bg-white p-5 shadow-2xs transition-all",
                    isApproved ? "border-slate-200" : "border-amber-200 ring-2 ring-amber-50"
                  )}
                >
                  {/* Top row */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
                    <div className="flex items-center gap-2.5">
                      <span className="w-6 h-6 rounded-md bg-slate-100 text-slate-700 text-xs font-bold flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600">
                        {q.type}
                      </span>
                      <span className="text-[11px] text-slate-400 font-medium">
                        {q.marks} {q.marks === 1 ? "mark" : "marks"} · {q.difficulty}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "px-2.5 py-0.5 rounded-full text-[11px] font-bold",
                          isApproved ? "bg-[#E7F3EC] text-[#00663C]" : "bg-amber-100 text-amber-800"
                        )}
                      >
                        {isApproved ? "Approved" : "Pending review"}
                      </span>
                    </div>
                  </div>

                  {/* Question content */}
                  <div className="pt-3.5 space-y-3">
                    <p className="text-sm font-semibold text-slate-900 leading-relaxed">{q.question}</p>

                    {/* MCQ Options */}
                    {q.type === "mcq" && q.options && q.options.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                        {q.options.map((opt, oIdx) => {
                          const isCorrect = oIdx === (q.correctAnswerIndex ?? 0);
                          return (
                            <div
                              key={oIdx}
                              className={cn(
                                "flex items-center gap-2.5 p-2.5 rounded-xl border text-xs font-medium",
                                isCorrect
                                  ? "border-emerald-300 bg-emerald-50/50 text-[#00663C] font-semibold"
                                  : "border-slate-200 text-slate-700 bg-slate-50/30"
                              )}
                            >
                              <span
                                className={cn(
                                  "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0",
                                  isCorrect ? "bg-[#00663C] text-white" : "border border-slate-300 text-slate-500"
                                )}
                              >
                                {String.fromCharCode(65 + oIdx)}
                              </span>
                              <span className="truncate">{opt}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Coding testcases */}
                    {q.type === "coding" && q.testCases && (
                      <div className="rounded-xl bg-slate-900 text-emerald-400 p-3 text-xs font-mono whitespace-pre-wrap">
                        {q.testCases}
                      </div>
                    )}

                    {/* Explanation */}
                    {q.explanation && (
                      <div className="text-xs text-slate-500 bg-slate-50 p-2.5 rounded-xl border border-slate-200/60">
                        <b className="text-slate-700">Explanation:</b> {q.explanation}
                      </div>
                    )}
                  </div>

                  {/* Card actions */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-3.5 mt-3 border-t border-slate-100">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleRegenerate(q.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                        title="Regenerate this question"
                      >
                        <Icon name="refresh" size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingQuestion({ item: q, index: idx })}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                        title="Edit question"
                      >
                        <Icon name="edit" size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeletingQuestion(q)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                        title="Delete question"
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </div>

                    {!isApproved && (
                      <button
                        type="button"
                        onClick={() => handleApprove(q.id)}
                        className="px-3.5 py-1.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs inline-flex items-center gap-1.5"
                      >
                        <Icon name="check" size={13} />
                        <span>Approve question</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Manual Question Modal (for + Add Question and Edit Question) */}
      {(isAddModalOpen || editingQuestion) && (
        <ManualQuestionModal
          isOpen={Boolean(isAddModalOpen || editingQuestion)}
          onClose={() => {
            setIsAddModalOpen(false);
            setEditingQuestion(null);
          }}
          initialData={
            editingQuestion
              ? {
                  questionId: editingQuestion.item.id,
                  text: editingQuestion.item.question,
                  questionType: editingQuestion.item.type === "coding" ? "coding" : "mcq_single",
                  options: (editingQuestion.item.options || []).map((opt, i) => ({
                    id: String.fromCharCode(97 + i),
                    text: opt,
                  })),
                  correct: String.fromCharCode(97 + (editingQuestion.item.correctAnswerIndex ?? 0)),
                  marks: editingQuestion.item.marks,
                  explanation: editingQuestion.item.explanation || "",
                }
              : null
          }
          questionNumber={editingQuestion ? editingQuestion.index + 1 : questions.length + 1}
          onSave={handleSaveManualQuestion}
        />
      )}

      {/* Unified Import Questions Modal */}
      {isImportModalOpen && (
        <UnifiedImportQuestionsModal
          existingQuestions={questions.map((q) => q.question)}
          onClose={() => setIsImportModalOpen(false)}
          onImport={handleImportDrafts}
        />
      )}

      {/* Auto-Generate Questions Modal */}
      {isAiModalOpen && (
        <AutoGenerateQuestionsModal
          isOpen={isAiModalOpen}
          onClose={() => setIsAiModalOpen(false)}
          contextTitle={chapterTitle}
          contextType="chapter"
          onSaveQuestions={async (drafts) => {
            await handleImportDrafts(drafts, () => {});
          }}
        />
      )}

      {/* Delete Question Confirmation */}
      {deletingQuestion && (
        <ConfirmModal
          isOpen={Boolean(deletingQuestion)}
          title="Remove question?"
          description="Are you sure you want to remove this question from the review set?"
          confirmLabel="Remove"
          tone="danger"
          onConfirm={handleDeleteQuestion}
          onClose={() => setDeletingQuestion(null)}
        />
      )}
    </div>
  );
}
