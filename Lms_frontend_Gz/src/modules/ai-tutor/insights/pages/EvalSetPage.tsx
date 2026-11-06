import { useState } from "react";
import { useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetEvalSetQuery, useRunEvalSetMutation } from "@/modules/ai-tutor/insights/api/insightsApi";
import { AddCaseForm } from "@/modules/ai-tutor/insights/components/eval/AddCaseForm";
import { EvalRunCard } from "@/modules/ai-tutor/insights/components/eval/EvalRunCard";
import { Button, Card, EmptyState, PageHeader, PageLoader, Select } from "@/shared/ui";

const TOP_K_OPTIONS = [1, 3, 5, 10].map((value) => ({ value: String(value), label: `Top ${value}` }));

export function EvalSetPage() {
  const { evalSetId = "" } = useParams();
  const notify = useNotify();
  const { data, isLoading, isError } = useGetEvalSetQuery(evalSetId, { skip: !evalSetId });
  const [run, { isLoading: running }] = useRunEvalSetMutation();
  const [topK, setTopK] = useState("3");

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <EmptyState icon="alert" title="Evaluation set not found" />;

  const { eval_set: evalSet, cases, runs } = data;

  return (
    <>
      <PageHeader
        title={evalSet.name}
        description="Measures whether the tutor's retriever finds the lesson that answers each question."
        backTo={`/tutor/insights?course=${evalSet.course_id}&tab=evaluation`}
        backLabel="Course insights"
        actions={
          <div className="flex items-center gap-2">
            <Select aria-label="How many results count" className="w-28" options={TOP_K_OPTIONS} value={topK} onChange={(event) => setTopK(event.target.value)} />
            <Button
              icon="play"
              loading={running}
              disabled={cases.length === 0}
              onClick={async () => {
                try {
                  await run({ evalSetId, top_k: Number(topK) }).unwrap();
                  notify.success("Run complete");
                } catch (error) {
                  notify.apiError(error);
                }
              }}
            >
              Run
            </Button>
          </div>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <AddCaseForm evalSetId={evalSetId} courseId={evalSet.course_id} />
          <Card title={`Questions (${cases.length})`}>
            {cases.length === 0 ? (
              <p className="text-sm text-slate-500">Add the first question above.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {cases.map((item) => (
                  <li key={item.case_id} className="border-b border-slate-100 pb-2 last:border-0">
                    <p className="text-slate-800">{item.question}</p>
                    <p className="text-xs text-slate-500">Expects {item.expected_item_ids.length} lesson{item.expected_item_ids.length === 1 ? "" : "s"}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        <div className="space-y-4">
          {runs.length === 0 ? <EmptyState icon="play" title="No runs yet" description="Run it to get the first results." /> : runs.map((item) => <EvalRunCard key={item.run_id} run={item} />)}
        </div>
      </div>
    </>
  );
}
