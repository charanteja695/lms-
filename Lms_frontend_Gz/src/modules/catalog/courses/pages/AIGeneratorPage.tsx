import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import { CoursePageHeader } from "@/modules/catalog/courses/components/common/CoursePageHeader";
import { Icon, PageLoader } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";

export function AIGeneratorPage() {
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

  const currentModule = versionDetail?.modules?.find((m) => m.module_id === moduleId);
  const currentChapter = currentModule?.topics?.find((t) => t.topic_id === chapterId);

  // Settings
  const [numQuestions, setNumQuestions] = useState(8);
  const [difficulty, setDifficulty] = useState<"Easy" | "Mixed" | "Hard">("Mixed");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([
    "MCQ",
    "Multiple select",
    "True or false",
    "Code output",
    "Coding",
  ]);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);

  const allTypes = [
    "MCQ",
    "Multiple select",
    "True or false",
    "Fill in the blank",
    "Code output",
    "Coding",
    "Debugging",
    "Scenario",
  ];

  const handleToggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const chapterTitle = currentChapter?.title || "Chapter Materials";
  const moduleTitle = currentModule?.title || "Module";

  const handleGenerate = async () => {
    try {
      setIsGenerating(true);
      setGenerationError(null);

      const generated = Array.from({ length: numQuestions }).map((_, i) => {
        const isCoding = selectedTypes.includes("Coding") && i % 3 === 2;
        if (isCoding) {
          return {
            id: `gen-code-${Date.now()}-${i}`,
            type: "coding" as const,
            question: `Write a code solution reinforcing concepts taught in ${chapterTitle} (Challenge #${i + 1}).`,
            testCases: `test 1  input: [1, 2] -> expected: 3\ntest 2  input: [0] -> expected: 0`,
            explanation: `Implements the primary requirements and edge cases of ${chapterTitle}.`,
            marks: 10,
            difficulty,
            status: "pending" as const,
          };
        }
        return {
          id: `gen-mcq-${Date.now()}-${i}`,
          type: "mcq" as const,
          question: `In context of ${chapterTitle}, which statement is the most accurate? (Question #${i + 1})`,
          options: [
            `Standard declarative structure provides predictable behavior and lifecycle consistency.`,
            `It mutates internal runtime references synchronously on each cycle.`,
            `It completely removes scoping barriers and writes to global state directly.`,
            `It is only applied during offline static file compilation.`,
          ],
          correctAnswerIndex: 0,
          explanation: `In ${chapterTitle}, clean declarative design ensures predictable state and execution flow.`,
          marks: 2,
          difficulty,
          status: "pending" as const,
        };
      });

      if (chapterId) {
        localStorage.setItem(`generated_questions_${chapterId}`, JSON.stringify(generated));
      }

      notify.success(`${numQuestions} questions generated for ${chapterTitle}!`);
      navigate(`/courses/${courseId}/modules/${moduleId}/chapters/${chapterId}/questions`);
    } catch (err: any) {
      setGenerationError(err?.message || "Failed to generate questions. Please retry.");
    } finally {
      setIsGenerating(false);
    }
  };

  if (isCourseLoading || isVersionLoading) {
    return <PageLoader label="Loading chapter details..." />;
  }

  const backUrl = `/courses/${courseId}/modules/${moduleId}/chapters`;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* 1. Universal Breadcrumbs & Back Navigation */}
      <CoursePageHeader
        breadcrumbs={[
          { label: "Courses", href: "/courses" },
          { label: course?.title || "Course", href: `/courses/${courseId}` },
          { label: moduleTitle, href: `/courses/${courseId}?tab=modules` },
          { label: chapterTitle, href: backUrl },
          { label: "AI Question Generator", current: true },
        ]}
        title={`AI Question Generator · ${chapterTitle}`}
        description="Extract test questions automatically from the chapter learning materials."
        backHref={backUrl}
      />

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Card: Source Materials */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-4">
          <h3 className="text-sm font-bold text-[#0A1530]">Source materials</h3>

          <div className="space-y-3">
            <div className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
              <span className="w-6 h-6 rounded-full bg-[#00663C] text-white flex items-center justify-center shrink-0">
                <Icon name="check" size={13} />
              </span>
              <div className="min-w-0 flex-1">
                <h4 className="text-xs font-bold text-slate-800">{chapterTitle}</h4>
                <p className="text-[11px] text-slate-500">
                  {(currentChapter?.items?.length ?? 0)} items attached to this chapter
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
              <span className="w-6 h-6 rounded-full bg-[#00663C] text-white flex items-center justify-center shrink-0">
                <Icon name="check" size={13} />
              </span>
              <div className="min-w-0 flex-1">
                <h4 className="text-xs font-bold text-slate-800">Learning objectives</h4>
                <p className="text-[11px] text-slate-500">
                  Concept verification and skill-check questions
                </p>
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-400 font-medium pt-2">
            Questions are generated specifically from this chapter. Students cannot see them until you approve them.
          </p>
        </div>

        {/* Right Card: Settings */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-4">
          <h3 className="text-sm font-bold text-[#0A1530]">Settings</h3>

          {generationError && (
            <div className="rounded-xl bg-rose-50 p-3 text-xs font-semibold text-rose-700 border border-rose-200">
              {generationError}
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Number of questions</label>
            <select
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 focus:border-[#00663C] focus:outline-none"
            >
              <option value={4}>4 questions</option>
              <option value={8}>8 questions</option>
              <option value={12}>12 questions</option>
              <option value={16}>16 questions</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Difficulty</label>
            <div className="flex rounded-xl border border-slate-300 overflow-hidden bg-slate-50 p-0.5">
              {(["Easy", "Mixed", "Hard"] as const).map((lvl) => (
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

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-2">Question types</label>
            <div className="grid grid-cols-2 gap-2">
              {allTypes.map((type) => {
                const isSelected = selectedTypes.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => handleToggleType(type)}
                    className={cn(
                      "flex items-center gap-2 p-2 rounded-xl border text-xs font-semibold transition-all cursor-pointer text-left",
                      isSelected
                        ? "border-[#00663C] bg-emerald-50/50 text-[#00663C]"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                    )}
                  >
                    <span
                      className={cn(
                        "w-4 h-4 rounded flex items-center justify-center shrink-0 border",
                        isSelected
                          ? "bg-[#00663C] border-[#00663C] text-white"
                          : "border-slate-300 bg-white"
                      )}
                    >
                      {isSelected && <Icon name="check" size={11} />}
                    </span>
                    <span className="truncate">{type}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => navigate(backUrl)}
              disabled={isGenerating}
              className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isGenerating}
              onClick={handleGenerate}
              className="px-5 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs inline-flex items-center gap-1.5"
            >
              {isGenerating ? (
                <>
                  <Icon name="refresh" size={14} className="animate-spin" />
                  <span>Generating questions...</span>
                </>
              ) : (
                <>
                  <Icon name="sparkles" size={14} />
                  <span>Generate questions</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
