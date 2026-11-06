import type { Run } from "@/modules/code-execution/runs/types";
import { Badge, Card, Spinner } from "@/shared/ui";

export function RunOutputPanel({ run, isExecuting }: { run: Run | null; isExecuting: boolean }) {
  if (!run && !isExecuting) {
    return (
      <Card title="Output">
        <p className="text-sm text-slate-400">Run your code to see the output here.</p>
      </Card>
    );
  }

  const pending = !run || run.status !== "completed";

  return (
    <Card
      title="Output"
      actions={
        pending ? (
          <span className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner size={14} /> {run?.status === "running" ? "Running…" : "Queued…"}
          </span>
        ) : (
          <Badge tone={run.outcome === "ok" ? "green" : "red"}>{run.outcome === "ok" ? "Ran successfully" : run.outcome}</Badge>
        )
      }
    >
      {run && !pending && (
        <div className="space-y-3">
          {(run.time_ms != null || run.memory_kb != null) && (
            <p className="text-xs text-slate-500">
              {run.time_ms != null && `${run.time_ms} ms`}
              {run.time_ms != null && run.memory_kb != null && " · "}
              {run.memory_kb != null && `${run.memory_kb} KB`}
              {run.exit_code != null && ` · exit code ${run.exit_code}`}
            </p>
          )}
          {run.compile_output && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Compiler output</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-amber-300">{run.compile_output}</pre>
            </div>
          )}
          {run.stdout && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">stdout</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">{run.stdout}</pre>
            </div>
          )}
          {run.stderr && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">stderr</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-red-300">{run.stderr}</pre>
            </div>
          )}
          {run.message && <p className="text-sm text-slate-600">{run.message}</p>}
          {!run.stdout && !run.stderr && !run.compile_output && !run.message && <p className="text-sm text-slate-400">No output.</p>}
        </div>
      )}
    </Card>
  );
}
