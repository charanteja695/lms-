import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { useCreateEvalSetMutation, useListEvalSetsQuery } from "@/modules/ai-tutor/insights/api/insightsApi";
import type { EvalSet } from "@/modules/ai-tutor/insights/types";
import { Button, Card, DataTable, EmptyState, Input, type Column } from "@/shared/ui";

const COLUMNS: Column<EvalSet>[] = [
  { key: "name", header: "Name", render: (item) => item.name },
  { key: "created", header: "Created", render: (item) => formatDateTime(item.created_at) },
];

/** Offline evaluation: question sets that measure whether the retriever finds the right lesson. */
export function EvalSetsPanel({ courseId }: { courseId: string }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: sets = [], isFetching } = useListEvalSetsQuery(courseId);
  const [create, { isLoading }] = useCreateEvalSetMutation();
  const [name, setName] = useState("");

  return (
    <Card title="Evaluation sets" bodyClassName="p-0">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-4">
        <Input aria-label="New set name" className="max-w-xs" placeholder="e.g. Week 1 questions" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
        <Button
          icon="plus"
          loading={isLoading}
          disabled={!name.trim()}
          onClick={async () => {
            try {
              const created = await create({ course_id: courseId, name: name.trim() }).unwrap();
              setName("");
              navigate(`/tutor/eval-sets/${created.eval_set_id}`);
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          New set
        </Button>
      </div>
      <DataTable
        columns={COLUMNS}
        rows={sets}
        rowKey={(item) => item.eval_set_id}
        loading={isFetching}
        onRowClick={(item) => navigate(`/tutor/eval-sets/${item.eval_set_id}`)}
        empty={<EmptyState icon="layers" title="No evaluation sets yet" description="Write the questions students ask and name the lesson that answers each." />}
      />
    </Card>
  );
}
