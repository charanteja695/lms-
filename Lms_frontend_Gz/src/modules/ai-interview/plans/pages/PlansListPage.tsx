import { useNavigate } from "react-router-dom";

import { PlanStatusBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { useInterviewRights } from "@/modules/ai-interview/common/hooks/useInterviewRights";
import { DIFFICULTY_LABELS } from "@/modules/ai-interview/common/labels";
import type { Plan } from "@/modules/ai-interview/common/types";
import { useListPlansQuery } from "@/modules/ai-interview/plans/api/plansApi";
import { InterviewTabs } from "@/modules/ai-interview/screening/components/InterviewTabs";
import { Button, Card, DataTable, EmptyState, PageHeader, type Column } from "@/shared/ui";

const COLUMNS: Column<Plan>[] = [
  { key: "title", header: "Plan", render: (p) => <div><p className="font-medium text-slate-900">{p.title}</p><p className="text-xs text-slate-500">{p.role} · v{p.version}</p></div> },
  { key: "kind", header: "Kind", hideOnMobile: true, render: (p) => (p.kind === "mock" ? "Practice" : "Screening") },
  { key: "difficulty", header: "Level", hideOnMobile: true, render: (p) => DIFFICULTY_LABELS[p.difficulty] },
  { key: "length", header: "Length", hideOnMobile: true, render: (p) => `${p.duration_minutes} min · ${p.rounds.length} rounds` },
  { key: "status", header: "Status", render: (p) => <PlanStatusBadge status={p.status} /> },
];

/** Interview plans this person manages: a company's screening plans, or the platform's practice plans (careers managers see all). */
export function PlansListPage() {
  const navigate = useNavigate();
  const { planKind, isCareersManager } = useInterviewRights();
  const { data, isFetching } = useListPlansQuery({ per_page: 100 });

  return (
    <>
      <PageHeader
        title="AI interviews"
        description={isCareersManager ? "Practice plans for students, and every company's screening plans." : "The questions and rounds your screening interviews follow."}
        actions={<Button icon="plus" onClick={() => navigate("/interviews/plans/new")}>New {planKind === "mock" ? "practice" : "screening"} plan</Button>}
      />
      <InterviewTabs />
      <Card bodyClassName="p-0">
        <DataTable columns={COLUMNS} rows={data?.items ?? []} rowKey={(p) => p.plan_id} loading={isFetching} onRowClick={(p) => navigate(`/interviews/plans/${p.plan_id}`)} empty={<EmptyState icon="fileText" title="No plans yet" description="Create a plan to set the questions every candidate is asked." />} />
      </Card>
    </>
  );
}
