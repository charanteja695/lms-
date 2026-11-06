import { useTutorRights } from "@/modules/ai-tutor/common/hooks/useTutorRights";
import { useState } from "react";

import { useListParams } from "@/core/hooks/useListParams";
import { formatDate } from "@/core/lib/format";
import { TutorTabs } from "@/modules/ai-tutor/common/components/TutorTabs";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { FAQ_SCOPE_LABELS, FAQ_STATUS_LABELS, FAQ_STATUS_TONES } from "@/modules/ai-tutor/common/labels";
import { useListManageableFaqQuery } from "@/modules/ai-tutor/faq/api/faqApi";
import { FaqCreateDialog } from "@/modules/ai-tutor/faq/components/FaqCreateDialog";
import { FaqEntryDialog } from "@/modules/ai-tutor/faq/components/FaqEntryDialog";
import type { FaqEntry, FaqManageFilters } from "@/modules/ai-tutor/faq/types";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import { Badge, Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(FAQ_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const SCOPE_OPTIONS = Object.entries(FAQ_SCOPE_LABELS).map(([value, label]) => ({ value, label }));

const COLUMNS: Column<FaqEntry>[] = [
  { key: "question", header: "Question", render: (item) => <span className="line-clamp-2">{item.question}</span> },
  {
    key: "scope",
    header: "Visible to",
    hideOnMobile: true,
    render: (item) =>
      item.scope === "course" && item.course_id ? <CourseTitleCell courseId={item.course_id} /> : item.scope === "organization" && item.organization_id ? <InstitutionNameCell organizationId={item.organization_id} /> : FAQ_SCOPE_LABELS[item.scope],
  },
  { key: "status", header: "Status", render: (item) => <Badge tone={FAQ_STATUS_TONES[item.status]}>{FAQ_STATUS_LABELS[item.status]}</Badge> },
  { key: "helpful", header: "Helpful", hideOnMobile: true, render: (item) => item.helpful_count },
  { key: "created", header: "Created", hideOnMobile: true, render: (item) => formatDate(item.created_at) },
];

/** The FAQ entries this person may manage — the server scopes the list (institution, courses, or everything). */
export function FaqManagePage() {
  const { params, update } = useListParams<Record<keyof FaqManageFilters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as FaqManageFilters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListManageableFaqQuery(apiParams);
  const { canCreateFaq } = useTutorRights();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<FaqEntry | null>(null);

  return (
    <>
      <PageHeader
        title="AI tutor"
        description="Answers the tutor gives before writing its own. Promote good tutor answers from a support ticket's transcript."
        actions={canCreateFaq ? <Button icon="plus" onClick={() => setCreating(true)}>New entry</Button> : undefined}
      />
      <TutorTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={apiParams.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
          <FilterSelect label="Scope" value={apiParams.scope} options={SCOPE_OPTIONS} onChange={(value) => update({ scope: value })} />
        </FilterRow>
        {isError ? (
          <EmptyState icon="alert" title="Could not load the FAQ" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable columns={COLUMNS} rows={data?.items ?? []} rowKey={(item) => item.faq_id} loading={isFetching} onRowClick={setEditing} empty={<EmptyState icon="helpCircle" title="No FAQ entries yet" description="Write answers the tutor can give straight away." />} />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
      {creating && <FaqCreateDialog open={creating} onClose={() => setCreating(false)} />}
      {editing && <FaqEntryDialog key={editing.faq_id} entry={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
