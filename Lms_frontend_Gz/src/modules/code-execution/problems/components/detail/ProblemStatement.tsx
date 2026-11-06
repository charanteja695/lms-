import type { Problem } from "@/modules/code-execution/problems/types";
import { Card } from "@/shared/ui";

export function ProblemStatement({ problem }: { problem: Problem }) {
  return (
    <div className="space-y-4">
      <Card>
        <p className="whitespace-pre-wrap text-sm text-slate-700">{problem.statement}</p>
      </Card>
      {problem.samples.map((sample) => (
        <Card key={sample.position} title={`Sample ${sample.position}`}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Input</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">{sample.input}</pre>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Expected output</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">{sample.expected}</pre>
            </div>
          </div>
          {sample.explanation && <p className="mt-3 text-sm text-slate-600">{sample.explanation}</p>}
        </Card>
      ))}
    </div>
  );
}
