import { useState, useEffect } from "react";
import { Icon, Modal, Button } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";

export interface ManualQuestionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (question: McqDraft & { questionType?: string }) => Promise<void>;
  initialData?: (McqDraft & { questionType?: string }) | null;
  questionNumber?: number;
}

export function ManualQuestionModal({
  isOpen,
  onClose,
  onSave,
  initialData,
  questionNumber = 1,
}: ManualQuestionModalProps) {
  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] = useState<string>("mcq_single");
  const [optionA, setOptionA] = useState("");
  const [optionB, setOptionB] = useState("");
  const [optionC, setOptionC] = useState("");
  const [optionD, setOptionD] = useState("");
  const [correctAnswer, setCorrectAnswer] = useState<string>("a");
  const [marks, setMarks] = useState<number>(1);
  const [explanation, setExplanation] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) {
      setQuestionText(initialData.text || "");
      setQuestionType(initialData.questionType || "mcq_single");

      const opts = initialData.options || [];
      const findOpt = (id: string, fallbackIdx: number) => {
        const byId = opts.find((o) => o.id.toLowerCase() === id);
        if (byId) return byId.text;
        return opts[fallbackIdx]?.text || "";
      };

      setOptionA(findOpt("a", 0));
      setOptionB(findOpt("b", 1));
      setOptionC(findOpt("c", 2));
      setOptionD(findOpt("d", 3));
      setCorrectAnswer(String(initialData.correct || "a").toLowerCase());
      setMarks(initialData.marks ?? 1);
      setExplanation(initialData.explanation || "");
    } else {
      setQuestionText("");
      setQuestionType("mcq_single");
      setOptionA("");
      setOptionB("");
      setOptionC("");
      setOptionD("");
      setCorrectAnswer("a");
      setMarks(1);
      setExplanation("");
    }
    setError(null);
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuestion = questionText.trim();
    if (!trimmedQuestion) {
      setError("Question text is required.");
      return;
    }

    if (questionType === "mcq_single" || questionType === "mcq_multi") {
      if (!optionA.trim() || !optionB.trim()) {
        setError("Both Option A and Option B are required.");
        return;
      }
      if (!correctAnswer) {
        setError("Please select the correct answer.");
        return;
      }
    }

    if (marks <= 0 || isNaN(marks)) {
      setError("Marks must be a positive number.");
      return;
    }

    const optionsList: Array<{ id: string; text: string }> = [
      { id: "a", text: optionA.trim() },
      { id: "b", text: optionB.trim() },
    ];
    if (optionC.trim()) optionsList.push({ id: "c", text: optionC.trim() });
    if (optionD.trim()) optionsList.push({ id: "d", text: optionD.trim() });

    try {
      setIsSaving(true);
      setError(null);
      await onSave({
        questionId: initialData?.questionId,
        text: trimmedQuestion,
        questionType,
        options: optionsList,
        correct: correctAnswer,
        marks: Number(marks),
        explanation: explanation.trim(),
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to save question. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const isEdit = Boolean(initialData?.questionId || initialData?.text);

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={isEdit ? `Edit Question #${questionNumber}` : "Add Question"}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50/80 p-3 text-xs font-semibold text-rose-700">
            <Icon name="alertCircle" size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Question Type and Marks Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Question Type <span className="text-rose-500">*</span>
            </label>
            <select
              value={questionType}
              onChange={(e) => setQuestionType(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
            >
              <option value="mcq_single">Single Choice (MCQ)</option>
              <option value="mcq_multi">Multiple Select (MCQ)</option>
              <option value="true_false">True / False</option>
              <option value="fill_in">Fill in the Blank</option>
              <option value="coding">Coding Problem</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Marks <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={marks}
              onChange={(e) => setMarks(Number(e.target.value))}
              required
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
            />
          </div>
        </div>

        {/* Question Text */}
        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1.5">
            Question Text <span className="text-rose-500">*</span>
          </label>
          <textarea
            rows={3}
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            placeholder="Type your question here..."
            required
            className="w-full rounded-xl border border-slate-300 bg-white p-3 text-xs font-medium text-slate-800 placeholder-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
          />
        </div>

        {/* Options (for MCQ and True/False) */}
        {questionType !== "coding" && questionType !== "fill_in" && (
          <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">Answer Options</span>
              <span className="text-[11px] font-semibold text-slate-500">
                Select the radio button for the correct answer
              </span>
            </div>

            {/* Option A */}
            <div className="flex items-center gap-3">
              <label
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg border text-xs font-bold shrink-0 cursor-pointer transition-colors",
                  correctAnswer === "a"
                    ? "border-emerald-600 bg-emerald-600 text-white shadow-2xs"
                    : "border-slate-300 bg-white text-slate-600 hover:border-slate-400"
                )}
                title="Mark A as correct answer"
              >
                <input
                  type="radio"
                  name="correctAnswer"
                  value="a"
                  checked={correctAnswer === "a"}
                  onChange={() => setCorrectAnswer("a")}
                  className="sr-only"
                />
                A
              </label>
              <input
                type="text"
                value={optionA}
                onChange={(e) => setOptionA(e.target.value)}
                placeholder="Option A text (required)"
                required
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 placeholder-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
              />
            </div>

            {/* Option B */}
            <div className="flex items-center gap-3">
              <label
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg border text-xs font-bold shrink-0 cursor-pointer transition-colors",
                  correctAnswer === "b"
                    ? "border-emerald-600 bg-emerald-600 text-white shadow-2xs"
                    : "border-slate-300 bg-white text-slate-600 hover:border-slate-400"
                )}
                title="Mark B as correct answer"
              >
                <input
                  type="radio"
                  name="correctAnswer"
                  value="b"
                  checked={correctAnswer === "b"}
                  onChange={() => setCorrectAnswer("b")}
                  className="sr-only"
                />
                B
              </label>
              <input
                type="text"
                value={optionB}
                onChange={(e) => setOptionB(e.target.value)}
                placeholder="Option B text (required)"
                required
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 placeholder-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
              />
            </div>

            {/* Option C */}
            <div className="flex items-center gap-3">
              <label
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg border text-xs font-bold shrink-0 cursor-pointer transition-colors",
                  correctAnswer === "c"
                    ? "border-emerald-600 bg-emerald-600 text-white shadow-2xs"
                    : "border-slate-300 bg-white text-slate-600 hover:border-slate-400"
                )}
                title="Mark C as correct answer"
              >
                <input
                  type="radio"
                  name="correctAnswer"
                  value="c"
                  checked={correctAnswer === "c"}
                  onChange={() => setCorrectAnswer("c")}
                  className="sr-only"
                />
                C
              </label>
              <input
                type="text"
                value={optionC}
                onChange={(e) => setOptionC(e.target.value)}
                placeholder="Option C text (optional)"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 placeholder-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
              />
            </div>

            {/* Option D */}
            <div className="flex items-center gap-3">
              <label
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg border text-xs font-bold shrink-0 cursor-pointer transition-colors",
                  correctAnswer === "d"
                    ? "border-emerald-600 bg-emerald-600 text-white shadow-2xs"
                    : "border-slate-300 bg-white text-slate-600 hover:border-slate-400"
                )}
                title="Mark D as correct answer"
              >
                <input
                  type="radio"
                  name="correctAnswer"
                  value="d"
                  checked={correctAnswer === "d"}
                  onChange={() => setCorrectAnswer("d")}
                  className="sr-only"
                />
                D
              </label>
              <input
                type="text"
                value={optionD}
                onChange={(e) => setOptionD(e.target.value)}
                placeholder="Option D text (optional)"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 placeholder-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Explanation */}
        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1.5">
            Explanation <span className="text-slate-400 font-normal">(Optional)</span>
          </label>
          <textarea
            rows={2}
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            placeholder="Explain why the answer is correct (shown to students upon review)..."
            className="w-full rounded-xl border border-slate-300 bg-white p-3 text-xs font-medium text-slate-800 placeholder-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
          />
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            loading={isSaving}
            className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold"
          >
            {isEdit ? "Save Changes" : "+ Add Question"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
