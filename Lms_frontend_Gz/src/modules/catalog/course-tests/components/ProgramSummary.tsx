import { useGetQuestionQuery } from "@/modules/assessments/questions/api/questionsApi";
import { useGetProblemAuthorQuery, useListTestCasesQuery } from "@/modules/code-execution/problems/api/problemsApi";
import { Alert, Badge, PageLoader } from "@/shared/ui";

/** A program already on the test: published programs don't change; replace one by adding a new one. */
export function ProgramSummary({ questionId }: { questionId: string }) {
  const { data: question } = useGetQuestionQuery(questionId);
  const version = question?.working ?? question?.current;
  const problemId = version ? String(version.body.problem_id ?? "") : "";
  const { data: problem } = useGetProblemAuthorQuery(problemId, { skip: !problemId });
  const { data: cases = [] } = useListTestCasesQuery(problemId, { skip: !problemId });

  if (!question || !problem) return <PageLoader />;
  const samples = cases.filter((c) => c.is_sample).length;
  const allOrNothing = version?.answer_key.scoring === "all_or_nothing";

  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="space-y-3 rounded-2xl bg-white p-6 shadow-card ring-1 ring-slate-200/60">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-extrabold text-navy-950">{problem.title}</h2>
          <Badge tone="gray">{problem.difficulty}</Badge>
        </div>
        <pre className="whitespace-pre-wrap font-sans text-[15px] leading-relaxed text-slate-700">{problem.statement}</pre>
      </section>
      <aside className="space-y-4">
        <section className="space-y-2 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60 text-sm text-slate-700">
          <p><strong className="text-navy-950">{samples}</strong> sample cases · <strong className="text-navy-950">{cases.length - samples}</strong> hidden cases</p>
          <p>{allOrNothing ? "Full marks only when every test case passes." : "Marks for each test case passed."}</p>
          <p>Marks: <strong className="text-navy-950">{version?.default_marks}</strong></p>
        </section>
        <Alert tone="info">A published program doesn&apos;t change. To replace it, add a new program and remove this one from the test.</Alert>
      </aside>
    </div>
  );
}
