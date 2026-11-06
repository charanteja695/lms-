import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { OrgFilter } from "@/modules/billing/common/components/OrgFilter";
import { inr } from "@/modules/billing/common/format";
import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { QUOTE_STATUS_LABELS, QUOTE_STATUS_TONES } from "@/modules/billing/common/labels";
import type { Quote, QuoteStatus } from "@/modules/billing/common/types";
import { useListQuotesQuery } from "@/modules/billing/quotes/api/quotesApi";
import { OrganizationNameCell } from "@/modules/user-management/common/components/OrganizationNameCell";
import { Badge, Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

export function QuotesPage() {
  const navigate = useNavigate();
  const { isManager, isHead } = useBillingRights();
  const [status, setStatus] = useState<QuoteStatus | undefined>();
  const [org, setOrg] = useState({ id: "", label: "" });
  const [page, setPage] = useState(1);
  const { data, isFetching } = useListQuotesQuery({ status, organization_id: org.id || undefined, page, per_page: 20 });

  const columns: Column<Quote>[] = [
    ...(isManager ? [{ key: "org", header: "Organisation", render: (q: Quote) => <OrganizationNameCell organizationId={q.organization_id} /> }] : []),
    { key: "courses", header: "Courses", render: (q) => q.lines.map((l) => `${l.name} × ${l.seats}`).join(", ") },
    { key: "total", header: "Total", render: (q) => inr(q.total) },
    { key: "status", header: "Status", render: (q) => <Badge tone={QUOTE_STATUS_TONES[q.status]}>{QUOTE_STATUS_LABELS[q.status]}</Badge> },
    { key: "valid", header: "Valid until", hideOnMobile: true, render: (q) => formatDate(q.valid_until) },
  ];

  return (
    <>
      <PageHeader
        title="Billing"
        description={isManager ? "Course-seat quotes for every institution. Once accepted, the subscription is invoiced at the quoted price." : "Quotes are prices for course seats. Accepting one fixes the price your subscription will be invoiced at."}
        actions={(isHead || isManager) && <Button icon="plus" onClick={() => navigate("/billing/quotes/new")}>{isManager ? "New quote" : "Ask for a quote"}</Button>}
      />
      <BillingTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={status} options={toOptions(QUOTE_STATUS_LABELS)} onChange={(v) => { setStatus(v as QuoteStatus | undefined); setPage(1); }} />
          {isManager && <OrgFilter value={org.id} label={org.label} onChange={(id, label) => { setOrg({ id, label }); setPage(1); }} />}
        </FilterRow>
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(q) => q.quote_id} loading={isFetching} onRowClick={(q) => navigate(`/billing/quotes/${q.quote_id}`)} empty={<EmptyState icon="edit" title="No quotes" description={isManager ? "Create a quote for an institution's course seats." : "Ask for a quote to get a price for course seats."} />} />
        <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={() => setPage(1)} />
      </Card>
    </>
  );
}
