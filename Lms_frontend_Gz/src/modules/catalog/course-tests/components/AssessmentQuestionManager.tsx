import { useState, useMemo } from "react";
import { Button, Icon } from "@/shared/ui";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { ManualQuestionModal } from "@/modules/catalog/course-tests/components/ManualQuestionModal";
import { UnifiedImportQuestionsModal } from "@/modules/catalog/course-tests/components/UnifiedImportQuestionsModal";
import { AutoGenerateQuestionsModal } from "@/modules/catalog/course-tests/components/AutoGenerateQuestionsModal";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { cn } from "@/core/lib/cn";

export interface ManagedQuestionItem {
  id?: string;
  text: string;
  questionType?: string;
  marks: number;
  options?: Array<{ id: string; text: string }>;
  correctAnswer?: string;
  explanation?: string;
}

export interface AssessmentQuestionManagerProps {
  questions: ManagedQuestionItem[];
  contextTitle: string;
  contextType: "chapter" | "module" | "final";
  targetQuestionCount?: number;
  onSaveQuestion: (question: McqDraft & { questionType?: string }) => Promise<void>;
  onDeleteQuestion: (questionId?: string, index?: number) => Promise<void>;
  onImportDrafts: (
    drafts: McqDraft[],
    onProgress: (completed: number, total: number) => void
  ) => Promise<unknown>;
  className?: string;
}

export function AssessmentQuestionManager({
  questions,
  contextTitle,
  contextType,
  targetQuestionCount,
  onSaveQuestion,
  onDeleteQuestion,
  onImportDrafts,
  className,
}: AssessmentQuestionManagerProps) {
  // Modal states
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<{
    item: ManagedQuestionItem;
    index: number;
  } | null>(null);
  const [deletingQuestion, setDeletingQuestion] = useState<{
    item: ManagedQuestionItem;
    index: number;
  } | null>(null);

  // Compute metrics
  const totalQuestions = questions.length;
  const totalMarks = useMemo(
    () => questions.reduce((acc, q) => acc + (Number(q.marks) || 0), 0),
    [questions]
  );

  const targetMet = targetQuestionCount ? totalQuestions >= targetQuestionCount : true;

  const handleConfirmDelete = async () => {
    if (!deletingQuestion) return;
    await onDeleteQuestion(deletingQuestion.item.id, deletingQuestion.index);
    setDeletingQuestion(null);
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* 1. Header Toolbar with Question Management Options */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div>
          <h4 className="text-sm font-bold text-slate-900">Questions</h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Add questions manually, import in bulk, or generate with AI.
          </p>
        </div>

        {/* The Action Buttons near the question management area */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Option 1: + Add Question (Manual Entry) */}
          <Button
            type="button"
            icon="plus"
            onClick={() => setIsAddModalOpen(true)}
            className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold shadow-2xs text-xs"
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

      {/* 2. Metrics & Status Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3">
        <div className="flex items-center gap-3 text-xs">
          <span className="font-bold text-slate-800">
            {totalQuestions} {totalQuestions === 1 ? "question" : "questions"}
          </span>
          <span>·</span>
          <span className="font-medium text-slate-600">
            {totalMarks} total {totalMarks === 1 ? "mark" : "marks"}
          </span>
          {targetQuestionCount !== undefined && targetQuestionCount > 0 && (
            <>
              <span>·</span>
              <span
                className={cn(
                  "font-semibold",
                  targetMet ? "text-emerald-700" : "text-amber-700"
                )}
              >
                Target: {targetQuestionCount} questions ({totalQuestions} of {targetQuestionCount})
              </span>
            </>
          )}
        </div>

        {targetQuestionCount !== undefined && !targetMet && (
          <div className="flex items-center gap-1.5 text-xs text-amber-700 font-medium">
            <Icon name="alertCircle" size={14} className="shrink-0" />
            <span>Add at least {targetQuestionCount - totalQuestions} more to publish</span>
          </div>
        )}
      </div>

      {/* 3. Question List */}
      {questions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-[#2563EB] mb-3">
            <Icon name="clipboardCheck" size={24} />
          </div>
          <h4 className="text-sm font-bold text-slate-800">No questions added yet</h4>
          <p className="text-xs text-slate-500 mt-1 mb-5 max-w-sm mx-auto">
            Choose an option above to manually write questions, import an Excel/CSV/JSON file, or auto-generate with AI.
          </p>
          <div className="flex items-center justify-center gap-2.5">
            <Button
              type="button"
              icon="plus"
              size="sm"
              onClick={() => setIsAddModalOpen(true)}
              className="bg-[#2563EB] text-white"
            >
              + Add Question
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="fileSpreadsheet"
              onClick={() => setIsImportModalOpen(true)}
            >
              Import Questions
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="sparkles"
              onClick={() => setIsAiModalOpen(true)}
            >
              Auto-Generate
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map((q, idx) => {
            const isMcq = !q.questionType || q.questionType.includes("mcq") || q.questionType === "true_false";

            return (
              <div
                key={q.id || idx}
                className="rounded-2xl border border-slate-200 bg-white p-4.5 shadow-2xs space-y-3 transition-colors hover:border-slate-300"
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-3 pb-2.5 border-b border-slate-100">
                  <div className="flex items-start gap-2.5">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-700 shrink-0 mt-0.5">
                      {idx + 1}
                    </span>
                    <div>
                      <p className="text-xs font-bold text-slate-900 leading-snug">{q.text}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1">
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                          {q.questionType?.replace("_", " ") || "MCQ"}
                        </span>
                        <span className="text-[11px] font-semibold text-slate-500">
                          {q.marks} {q.marks === 1 ? "mark" : "marks"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions: Edit & Delete */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      icon="edit"
                      onClick={() => setEditingQuestion({ item: q, index: idx })}
                      className="text-xs font-semibold"
                    >
                      Edit
                    </Button>
                    <button
                      type="button"
                      onClick={() => setDeletingQuestion({ item: q, index: idx })}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer transition-colors"
                      title="Delete question"
                    >
                      <Icon name="trash" size={15} />
                    </button>
                  </div>
                </div>

                {/* Options display for MCQs */}
                {isMcq && q.options && q.options.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                    {q.options.map((opt) => {
                      const isCorrect =
                        String(opt.id).toLowerCase() === String(q.correctAnswer).toLowerCase();
                      return (
                        <div
                          key={opt.id}
                          className={cn(
                            "flex items-center gap-2.5 p-2 rounded-xl border text-xs",
                            isCorrect
                              ? "border-emerald-300 bg-emerald-50/50 text-emerald-900 font-semibold"
                              : "border-slate-200 bg-slate-50/30 text-slate-700"
                          )}
                        >
                          <span
                            className={cn(
                              "flex h-4.5 w-4.5 items-center justify-center rounded-full text-[10px] font-bold shrink-0",
                              isCorrect
                                ? "bg-emerald-600 text-white"
                                : "border border-slate-300 text-slate-500"
                            )}
                          >
                            {opt.id.toUpperCase()}
                          </span>
                          <span className="truncate">{opt.text}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Optional Explanation */}
                {q.explanation && (
                  <div className="text-[11px] text-slate-500 bg-slate-50 p-2 rounded-xl border border-slate-100">
                    <strong className="text-slate-700">Explanation: </strong>
                    {q.explanation}
                  </div>
                )}
              </div>
            );
          })}
        </div>
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
                  text: editingQuestion.item.text,
                  questionType: editingQuestion.item.questionType,
                  options: editingQuestion.item.options || [],
                  correct: editingQuestion.item.correctAnswer || "a",
                  marks: editingQuestion.item.marks,
                  explanation: editingQuestion.item.explanation || "",
                }
              : null
          }
          questionNumber={editingQuestion ? editingQuestion.index + 1 : totalQuestions + 1}
          onSave={onSaveQuestion}
        />
      )}

      {/* Unified Import Questions Modal */}
      {isImportModalOpen && (
        <UnifiedImportQuestionsModal
          existingQuestions={questions.map((q) => q.text)}
          onClose={() => setIsImportModalOpen(false)}
          onImport={onImportDrafts}
        />
      )}

      {/* Auto-Generate Questions Modal */}
      {isAiModalOpen && (
        <AutoGenerateQuestionsModal
          isOpen={isAiModalOpen}
          onClose={() => setIsAiModalOpen(false)}
          contextTitle={contextTitle}
          contextType={contextType}
          onSaveQuestions={async (drafts) => {
            await onImportDrafts(drafts, () => {});
          }}
        />
      )}

      {/* Delete Question Confirmation */}
      {deletingQuestion && (
        <ConfirmModal
          isOpen={Boolean(deletingQuestion)}
          title="Remove Question?"
          description="Are you sure you want to remove this question? This action cannot be undone."
          confirmLabel="Remove"
          tone="danger"
          onConfirm={handleConfirmDelete}
          onClose={() => setDeletingQuestion(null)}
        />
      )}
    </div>
  );
}
