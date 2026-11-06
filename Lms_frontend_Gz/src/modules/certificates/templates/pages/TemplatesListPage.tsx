import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { formatDateTime } from "@/core/lib/format";
import { CertificateTabs } from "@/modules/certificates/common/components/CertificateTabs";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { TEMPLATE_STATUS_LABELS } from "@/modules/certificates/common/labels";
import { TemplateStatusBadge } from "@/modules/certificates/common/components/StatusBadges";
import { useListTemplatesQuery } from "@/modules/certificates/templates/api/templatesApi";
import { useTemplateRights } from "@/modules/certificates/templates/hooks/useTemplateRights";
import type { CertificateTemplate, TemplateFilters } from "@/modules/certificates/templates/types";
import { Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(TEMPLATE_STATUS_LABELS).map(([value, label]) => ({ value, label }));

const COLUMNS: Column<CertificateTemplate>[] = [
  { key: "name", header: "Name", render: (item) => item.name },
  { key: "course", header: "Course", render: (item) => (item.course_id ? <CourseTitleCell courseId={item.course_id} /> : <span className="text-slate-500">Platform default</span>) },
  { key: "status", header: "Status", render: (item) => <TemplateStatusBadge status={item.status} /> },
  { key: "updated", header: "Updated", hideOnMobile: true, render: (item) => formatDateTime(item.updated_at) },
];

export function TemplatesListPage() {
  const navigate = useNavigate();
  const { canAuthor } = useTemplateRights();
  const { params, update } = useListParams<Record<keyof TemplateFilters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as TemplateFilters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListTemplatesQuery(apiParams);

  return (
    <>
      <PageHeader
        title="Certificates"
        description="Templates: the wording, signatories and grade bands a course's certificates are issued with."
        actions={
          canAuthor && (
            <Button icon="plus" onClick={() => navigate("/certificates/templates/new")}>
              New template
            </Button>
          )
        }
      />
      <CertificateTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={apiParams.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
        </FilterRow>
        {isError ? (
          <EmptyState icon="alert" title="Could not load templates" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={COLUMNS}
              rows={data?.items ?? []}
              rowKey={(item) => item.template_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/certificates/templates/${item.template_id}`)}
              empty={<EmptyState icon="fileText" title="No templates yet" description="Certificates use the built-in design until one is activated." />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
