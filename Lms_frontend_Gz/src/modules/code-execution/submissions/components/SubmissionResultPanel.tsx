import { VerdictBadge } from "@/modules/code-execution/common/components/VerdictBadge";
import type { Submission } from "@/modules/code-execution/submissions/types";
import { Badge, Card, Spinner } from "@/shared/ui";

export function SubmissionResultPanel({ submission, isSubmitting }: { submission: Submission | null; isSubmitting: boolean }) {
  if (!submission && !isSubmitting) {
    return (
      <Card title="Result">
        <p className="text-sm text-slate-400">Submit your solution to see the verdict here.</p>
      </Card>
    );
  }

  const pending = !submission || submission.status !== "completed";

  return (
    <Card
      title="Result"
      actions={
        pending ? (
          <span className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner size={14} /> Judging…
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <VerdictBadge verdict={submission.verdict} />
            <Badge tone="gray">
              {submission.passed_count}/{submission.total_count} · {submission.score} pts
            </Badge>
          </span>
        )
      }
    >
      {submission && !pending && (
        <div className="space-y-3">
          {submission.compile_output && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Compiler output</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-amber-300">{submission.compile_output}</pre>
            </div>
          )}
          {submission.message && <p className="text-sm text-slate-600">{submission.message}</p>}
          <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {submission.results.map((result) => (
              <div key={result.position} className="px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-800">
                    Case {result.position}
                    {result.is_sample && <Badge tone="blue" className="ml-2">Sample</Badge>}
                  </span>
                  <span className="flex items-center gap-2 text-xs text-slate-500">
                    {result.time_ms != null && `${result.time_ms} ms`}
                    <VerdictBadge verdict={result.verdict} />
                  </span>
                </div>
                {result.is_sample && result.verdict !== "accepted" && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-3">
                    {result.input != null && (
                      <div>
                        <p className="text-xs text-slate-500">Input</p>
                        <pre className="overflow-x-auto rounded bg-slate-900 p-2 font-mono text-xs text-slate-100">{result.input}</pre>
                      </div>
                    )}
                    {result.expected != null && (
                      <div>
                        <p className="text-xs text-slate-500">Expected</p>
                        <pre className="overflow-x-auto rounded bg-slate-900 p-2 font-mono text-xs text-slate-100">{result.expected}</pre>
                      </div>
                    )}
                    {result.actual != null && (
                      <div>
                        <p className="text-xs text-slate-500">Your output</p>
                        <pre className="overflow-x-auto rounded bg-slate-900 p-2 font-mono text-xs text-red-300">{result.actual}</pre>
                      </div>
                    )}
                  </div>
                )}
                {result.message && !result.is_sample && <p className="mt-1 text-xs text-slate-500">{result.message}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
