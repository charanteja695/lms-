import { useGetProblemQuery } from "@/modules/code-execution/problems/api/problemsApi";

/** A real component (not an inline render callback) so the lookup can call a hook safely per row. */
export function ProblemTitleCell({ problemId }: { problemId: string }) {
  const { data: problem, isFetching } = useGetProblemQuery(problemId);
  if (isFetching && !problem) return <span className="text-slate-400">Loading…</span>;
  return <span className="text-slate-900">{problem?.title ?? problemId}</span>;
}
