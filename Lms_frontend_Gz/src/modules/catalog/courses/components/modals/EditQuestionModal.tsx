import { useState, useEffect } from "react";
import { HelpCircle, X, Plus } from "lucide-react";
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
        testCases: type === "coding" ? testCases : undefined,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs overflow-y-auto animate-in fade-in duration-200">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden my-8 animate-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between border-b border-slate-100 p-5 bg-gradient-to-r from-slate-50 via-white to-indigo-50/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100/80 text-[#6366F1] flex items-center justify-center shrink-0">
              <HelpCircle className="w-5 h-5 text-[#6366F1]" />
            </div>
            <div>
              <h3 className="text-base font-bold text-navy-950">
                {initialData?.id ? "Edit Question" : "Add Question"}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Question {questionNumber} · {type === "mcq" ? "Multiple Choice" : "Coding Problem"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="rounded-xl bg-rose-50 p-3 text-xs font-semibold text-rose-700 border border-rose-200">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">Question *</label>
            <textarea
              rows={3}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What is the difference between state and props in React?"
              className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-navy-950 placeholder:text-slate-400 focus:border-[#6366F1] focus:ring-2 focus:ring-indigo-100 focus:outline-none resize-none transition"
            />
          </div>

          {type === "mcq" && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-slate-700">Answer Options *</label>
                <span className="text-[11px] text-slate-500">Select the radio circle for correct option</span>
              </div>
              <div className="space-y-2.5">
                {options.map((opt, idx) => (
                  <div key={idx} className="flex items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => setCorrectIndex(idx)}
                      className={cn(
                        "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 cursor-pointer transition-all",
                        correctIndex === idx
                          ? "border-[#6366F1] bg-[#6366F1]"
                          : "border-slate-300 hover:border-slate-400 bg-white"
                      )}
                    >
                      {correctIndex === idx && <span className="w-2 h-2 rounded-full bg-white" />}
                    </button>
                    <input
                      type="text"
                      required
                      value={opt}
                      onChange={(e) => handleOptionChange(idx, e.target.value)}
                      placeholder={`Option ${String.fromCharCode(65 + idx)}`}
                      className="flex-1 rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-navy-950 placeholder:text-slate-400 focus:border-[#6366F1] focus:ring-2 focus:ring-indigo-100 focus:outline-none transition"
                    />
                    {options.length > 2 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveOption(idx)}
                        className="p-1 text-slate-400 hover:text-rose-600 transition cursor-pointer"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}

                {options.length < 6 && (
                  <button
                    type="button"
                    onClick={handleAddOption}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-[#6366F1] hover:text-[#4F46E5] pt-1 cursor-pointer transition"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Option</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {type === "coding" && (
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Test Cases (Input / Expected Output)
              </label>
              <textarea
                rows={4}
                value={testCases}
                onChange={(e) => setTestCases(e.target.value)}
                placeholder="Input: [2, 7, 11, 15], target = 9&#10;Output: [0, 1]"
                className="w-full font-mono text-xs rounded-xl border border-slate-800 px-3.5 py-2.5 text-slate-100 focus:border-[#6366F1] focus:ring-2 focus:ring-indigo-100 focus:outline-none resize-none bg-slate-900 transition"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">Explanation / Solution Guide</label>
            <textarea
              rows={2}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              placeholder="Why this answer is correct..."
              className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-navy-950 placeholder:text-slate-400 focus:border-[#6366F1] focus:ring-2 focus:ring-indigo-100 focus:outline-none resize-none transition"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">Marks</label>
              <input
                type="number"
                min={1}
                max={100}
                value={marks}
                onChange={(e) => setMarks(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-navy-950 font-semibold focus:border-[#6366F1] focus:ring-2 focus:ring-indigo-100 focus:outline-none transition"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">Difficulty</label>
              <div className="flex rounded-xl border border-slate-200 overflow-hidden bg-slate-50 p-1">
                {(["Easy", "Medium", "Hard"] as const).map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setDifficulty(lvl)}
                    className={cn(
                      "flex-1 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer",
                      difficulty === lvl
                        ? "bg-white text-[#6366F1] shadow-xs"
                        : "text-slate-500 hover:text-slate-800"
                    )}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2.5 rounded-xl bg-[#6366F1] hover:bg-[#4F46E5] text-xs font-bold text-white shadow-xs cursor-pointer transition disabled:opacity-50"
            >
              {isSaving ? "Saving..." : "Save Question"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
