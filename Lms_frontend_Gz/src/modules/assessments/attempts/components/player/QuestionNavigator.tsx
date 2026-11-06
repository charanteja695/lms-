import { cn } from "@/core/lib/cn";
import type { PaperQuestion } from "@/modules/assessments/attempts/paperTypes";
import { Card } from "@/shared/ui";

export function QuestionNavigator({ questions, answeredIds }: { questions: PaperQuestion[]; answeredIds: Set<string> }) {
  return (
    <Card title="Questions" description={`${answeredIds.size} of ${questions.length} answered`}>
      <div className="grid grid-cols-4 gap-2">
        {questions.map((question, index) => {
          const isAnswered = answeredIds.has(question.question_id);
          return (
            <a
              key={question.question_id}
              href={`#question-${question.question_id}`}
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-xl text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                isAnswered
                  ? "bg-brand-600 text-white shadow-brand hover:bg-brand-700"
                  : "bg-slate-100 text-slate-600 ring-1 ring-slate-200 hover:bg-slate-200 hover:text-slate-900",
              )}
            >
              {index + 1}
            </a>
          );
        })}
      </div>
    </Card>
  );
}
