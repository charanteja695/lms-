import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { InterviewStatusBadge, RecommendationBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { INTERVIEW_STATUS_LABELS } from "@/modules/ai-interview/common/labels";
import { useListScreeningInterviewsQuery, type ScreeningInterview } from "@/modules/ai-interview/screening/api/screeningApi";
import { InterviewTabs } from "@/modules/ai-interview/screening/components/InterviewTabs";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

const COLUMNS: Column<ScreeningInterview>[] = [
  { key: "candidate", header: "Candidate", render: (i) => <UserNameCell userId={i.user_id} /> },
  { key: "role", header: "Role", render: (i) => i.role },
  { key: "status", header: "Status", render: (i) => <InterviewStatusBadge status={i.status} /> },
  { key: "result", header: "Result", render: (i) => <RecommendationBadge value={i.final_recommendation} /> },
  { key: "when", header: "Completed", hideOnMobile: true, render: (i) => formatDateTime(i.completed_at) },
];

export function ScreeningListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<string | undefined>("evaluated");
  const [page, setPage] = useState(1);
  const { data, isFetching } = useListScreeningInterviewsQuery({ status, page, per_page: 20 });

  return (
    <>
      <PageHeader title="AI interviews" description="Review each AI interview. Nothing reaches a candidate until a person has." />
      <InterviewTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={status} options={toOptions(INTERVIEW_STATUS_LABELS)} onChange={(v) => { setStatus(v); setPage(1); }} />
        </FilterRow>
        <DataTable columns={COLUMNS} rows={data?.items ?? []} rowKey={(i) => i.interview_id} loading={isFetching} onRowClick={(i) => navigate(`/interviews/screening/${i.interview_id}`)} empty={<EmptyState icon="users" title="No interviews" description="Interviews appear here once candidates take them." />} />
        <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={() => setPage(1)} />
      </Card>
    </>
  );
}
