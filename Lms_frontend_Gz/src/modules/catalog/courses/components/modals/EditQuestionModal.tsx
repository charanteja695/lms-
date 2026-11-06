import { useState, useEffect } from "react";
import { Icon } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export interface QuestionData {
  id?: string;
  type: "mcq" | "coding";
  question: string;
  options?: string[];
  correctAnswerIndex?: number;
  testCases?: string;
  explanation: string;
  marks: number;
  difficulty: "Easy" | "Medium" | "Hard";
}

interface EditQuestionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: QuestionData) => Promise<void>;
  initialData?: QuestionData | null;
  questionNumber?: number;
}

export function EditQuestionModal({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  questionNumber = 1,
}: EditQuestionModalProps) {
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState<string[]>(["", "", ""]);
  const [correctIndex, setCorrectIndex] = useState(0);
  const [testCases, setTestCases] = useState("");
  const [explanation, setExplanation] = useState("");
  const [marks, setMarks] = useState(2);
  const [difficulty, setDifficulty] = useState<"Easy" | "Medium" | "Hard">("Easy");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const type = initialData?.type || "mcq";

  useEffect(() => {
    if (initialData) {
      setQuestion(initialData.question || "");
      setOptions(initialData.options && initialData.options.length > 0 ? initialData.options : ["", "", ""]);
      setCorrectIndex(initialData.correctAnswerIndex ?? 0);
      setTestCases(initialData.testCases || "");
      setExplanation(initialData.explanation || "");
      setMarks(initialData.marks ?? 2);
      setDifficulty(initialData.difficulty || "Easy");
    } else {
      setQuestion("");
      setOptions(["", "", ""]);
      setCorrectIndex(0);
      setTestCases("");
      setExplanation("");
      setMarks(2);
      setDifficulty("Easy");
    }
    setError(null);
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleOptionChange = (idx: number, val: string) => {
    setOptions((prev) => {
      const next = [...prev];
      next[idx] = val;
      return next;
    });
  };

  const handleAddOption = () => {
    if (options.length < 6) {
      setOptions((prev) => [...prev, ""]);
    }
  };

  const handleRemoveOption = (idx: number) => {
    if (options.length > 2) {
      setOptions((prev) => prev.filter((_, i) => i !== idx));
      if (correctIndex >= idx && correctIndex > 0) {
        setCorrectIndex(correctIndex - 1);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) {
      setError("Question text is required");
      return;
    }
    if (type === "mcq" && options.some((o) => !o.trim())) {
      setError("All option fields must be filled");
      return;
    }
    try {
      setIsSaving(true);
      setError(null);
      await onSubmit({
        id: initialData?.id,
        type,
        question: question.trim(),
        options: type === "mcq" ? options.map((o) => o.trim()) : undefined,
        correctAnswerIndex: type === "mcq" ? correctIndex : undefined,
        testCases: type === "coding" ? testCases.trim() : undefined,
        explanation: explanation.trim(),
        marks: Number(marks) || 2,
        difficulty,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to save question");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs overflow-y-auto">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden my-8 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between border-b border-slate-100 p-5 pb-4">
          <div>
            <h3 className="text-base font-bold text-[#0A1530]">
              {initialData?.id ? "Edit question" : "Add question"}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Question {questionNumber} · {type === "mcq" ? "Multiple Choice" : "Coding Problem"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-rose-50 p-3 text-xs font-semibold text-rose-700 border border-rose-200">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Question *</label>
            <textarea
              rows={3}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What is React?"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C] resize-none"
            />
          </div>

          {type === "mcq" && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-slate-800">Answer options *</label>
                <span className="text-[11px] text-slate-500">Select the circle for the correct answer</span>
              </div>
              <div className="space-y-2">
                {options.map((opt, idx) => (
                  <div key={idx} className="flex items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => setCorrectIndex(idx)}
                      className={cn(
                        "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 cursor-pointer transition-colors",
                        correctIndex === idx
                          ? "border-[#00663C] bg-[#00663C]"
                          : "border-slate-300 hover:border-slate-400"
                      )}
                    >
                      {correctIndex === idx && <span className="w-2 h-2 rounded-full bg-white" />}
                    </button>
                    <input
                      type="text"
                      required
                      value={opt}
                      onChange={(e) => handleOptionChange(idx, e.target.value)}
                      placeholder={`Option ${idx + 1}`}
                      className="flex-1 rounded-xl border border-slate-300 px-3.5 py-1.5 text-xs text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
                    />
                    {options.length > 2 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveOption(idx)}
                        className="p-1 text-slate-400 hover:text-rose-600 rounded-lg cursor-pointer"
                      >
                        <Icon name="trash" size={15} />
                      </button>
                    )}
                  </div>
                ))}
                {options.length < 6 && (
                  <button
                    type="button"
                    onClick={handleAddOption}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#00663C] hover:underline pt-1 cursor-pointer"
                  >
                    <Icon name="plus" size={14} /> Add option
                  </button>
                )}
              </div>
            </div>
          )}

          {type === "coding" && (
            <div>
              <label className="block text-xs font-bold text-slate-800 mb-1.5">Test Cases / Examples</label>
              <textarea
                rows={3}
                value={testCases}
                onChange={(e) => setTestCases(e.target.value)}
                placeholder={'test 1  input ["Ana","Ravi"]  expected <li>Ana</li>\ntest 2  input []  expected nothing'}
                className="w-full font-mono text-xs rounded-xl border border-slate-300 px-3.5 py-2 text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C] resize-none bg-slate-900 text-slate-100"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Explanation</label>
            <textarea
              rows={2}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              placeholder="Why this is the correct answer"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C] resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-800 mb-1.5">Marks</label>
              <input
                type="number"
                min={1}
                max={100}
                value={marks}
                onChange={(e) => setMarks(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-800 mb-1.5">Difficulty</label>
              <div className="flex rounded-xl border border-slate-300 overflow-hidden bg-slate-50 p-0.5">
                {(["Easy", "Medium", "Hard"] as const).map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setDifficulty(lvl)}
                    className={cn(
                      "flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer",
                      difficulty === lvl
                        ? "bg-white text-[#00663C] shadow-2xs font-bold"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs"
            >
              {isSaving ? "Saving..." : "Save question"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
