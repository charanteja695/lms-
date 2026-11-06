import { useState } from "react";
import { Modal, Button, Icon } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";

export interface AutoGenerateQuestionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  contextTitle: string;
  contextType: "chapter" | "module" | "final";
  onSaveQuestions: (drafts: McqDraft[]) => Promise<void>;
}

export function AutoGenerateQuestionsModal({
  isOpen,
  onClose,
  contextTitle,
  contextType,
  onSaveQuestions,
}: AutoGenerateQuestionsModalProps) {
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState<"Easy" | "Medium" | "Hard" | "Mixed">("Mixed");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([
    "MCQ",
    "Multiple select",
    "True or false",
  ]);
  const [marksPerQuestion, setMarksPerQuestion] = useState(2);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDrafts, setGeneratedDrafts] = useState<McqDraft[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  const allTypes = [
    "MCQ",
    "Multiple select",
    "True or false",
    "Code output",
    "Coding",
  ];

  const handleToggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const handleGenerate = () => {
    setIsGenerating(true);
    // Simulate generation with context-relevant questions
    setTimeout(() => {
      const results: McqDraft[] = Array.from({ length: numQuestions }).map((_, i) => {
        const optionPool = [
          `Core architectural concept defined within ${contextTitle}.`,
          `Standard declarative pattern for state and lifecycle consistency.`,
          `Mutates internal references synchronously across execution loops.`,
          `Only executed during static compilation phase.`,
        ];

        return {
          text: `In context of ${contextTitle}, which statement represents best practice? (Generated Question #${i + 1})`,
          options: [
            { id: "a", text: optionPool[0] || "" },
            { id: "b", text: optionPool[1] || "" },
            { id: "c", text: optionPool[2] || "" },
            { id: "d", text: optionPool[3] || "" },
          ],
          correct: "a",
          explanation: `In ${contextTitle}, standard declarative architectures enforce predictable execution and stability.`,
          marks: marksPerQuestion,
        };
      });

      setGeneratedDrafts(results);
      setIsGenerating(false);
    }, 800);
  };

  const handleRegenerateItem = (index: number) => {
    setGeneratedDrafts((prev) =>
      prev.map((item, idx) => {
        if (idx !== index) return item;
        return {
          ...item,
          text: `Refreshed analysis on ${contextTitle}: What is the primary characteristic? (Regenerated #${idx + 1})`,
        };
      })
    );
  };

  const handleRemoveItem = (index: number) => {
    setGeneratedDrafts((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleSaveApproved = async () => {
    if (generatedDrafts.length === 0) return;
    try {
      setIsSaving(true);
      await onSaveQuestions(generatedDrafts);
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={`Auto-Generate Questions with AI · ${contextTitle}`}
      size="xl"
    >
      <div className="space-y-5">
        {generatedDrafts.length === 0 ? (
          /* Step 1: Configuration form */
          <div className="space-y-5">
            <div className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shrink-0">
                  <Icon name="sparkles" size={20} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-indigo-950">
                    AI Question Generator for {contextType.toUpperCase()}
                  </h4>
                  <p className="text-[11px] text-indigo-800">
                    Generate verified questions based on {contextTitle} materials and syllabus.
                  </p>
                </div>
              </div>
            </div>

            {/* Questions count and difficulty */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Question Count
                </label>
                <div className="flex items-center gap-2">
                  {[5, 10, 15, 20].map((count) => (
                    <button
                      key={count}
                      type="button"
                      onClick={() => setNumQuestions(count)}
                      className={cn(
                        "flex-1 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-colors border",
                        numQuestions === count
                          ? "border-[#2563EB] bg-[#2563EB] text-white"
                          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                      )}
                    >
                      {count}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Difficulty
                </label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value as any)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:outline-none"
                >
                  <option value="Mixed">Mixed (Recommended)</option>
                  <option value="Easy">Easy</option>
                  <option value="Medium">Medium</option>
                  <option value="Hard">Hard</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Marks per question
                </label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={marksPerQuestion}
                  onChange={(e) => setMarksPerQuestion(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-[#2563EB] focus:outline-none"
                />
              </div>
            </div>

            {/* Question types pills */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-2">
                Question Types to Include
              </label>
              <div className="flex flex-wrap gap-2">
                {allTypes.map((type) => {
                  const isSelected = selectedTypes.includes(type);
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => handleToggleType(type)}
                      className={cn(
                        "px-3 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition-colors border",
                        isSelected
                          ? "border-[#2563EB] bg-blue-50 text-[#2563EB] font-bold"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                      )}
                    >
                      {type}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="button"
                loading={isGenerating}
                onClick={handleGenerate}
                className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold"
              >
                Generate {numQuestions} Questions
              </Button>
            </div>
          </div>
        ) : (
          /* Step 2: Generated questions preview */
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-900">
                  {generatedDrafts.length} Questions Generated
                </span>
                <span className="text-xs text-slate-500">
                  ({generatedDrafts.length * marksPerQuestion} total marks)
                </span>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setGeneratedDrafts([])}
              >
                Reconfigure Generator
              </Button>
            </div>

            <div className="max-h-80 overflow-y-auto space-y-3 pr-1">
              {generatedDrafts.map((draft, idx) => (
                <div
                  key={idx}
                  className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3 shadow-2xs"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <span className="flex h-5 w-5 items-center justify-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-700 shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <div>
                        <p className="text-xs font-bold text-slate-900 leading-snug">
                          {draft.text}
                        </p>
                        <span className="text-[10px] text-slate-400 font-medium">
                          {draft.marks} marks · Correct: Option {draft.correct?.toUpperCase()}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleRegenerateItem(idx)}
                        className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                        title="Regenerate this question"
                      >
                        <Icon name="refresh" size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveItem(idx)}
                        className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                        title="Remove question"
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Options */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-[11px]">
                    {draft.options.map((opt) => {
                      const isCorrect = opt.id === draft.correct;
                      return (
                        <div
                          key={opt.id}
                          className={cn(
                            "flex items-center gap-2 p-2 rounded-lg border",
                            isCorrect
                              ? "border-emerald-300 bg-emerald-50/60 text-emerald-800 font-semibold"
                              : "border-slate-200 bg-slate-50/40 text-slate-600"
                          )}
                        >
                          <span
                            className={cn(
                              "flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold shrink-0",
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
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
              <Button type="button" variant="secondary" onClick={onClose} disabled={isSaving}>
                Cancel
              </Button>
              <Button
                type="button"
                loading={isSaving}
                onClick={() => void handleSaveApproved()}
                className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold"
              >
                Add {generatedDrafts.length} Questions to Test
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
