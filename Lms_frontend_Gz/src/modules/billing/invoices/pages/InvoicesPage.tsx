import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { OrgFilter } from "@/modules/billing/common/components/OrgFilter";
import { inr } from "@/modules/billing/common/format";
import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { INVOICE_KIND_LABELS, INVOICE_STATUS_LABELS, INVOICE_STATUS_TONES } from "@/modules/billing/common/labels";
import type { Invoice, InvoiceStatus } from "@/modules/billing/common/types";
import { useListInvoicesQuery } from "@/modules/billing/invoices/api/invoicesApi";
import { OrganizationNameCell } from "@/modules/user-management/common/components/OrganizationNameCell";
import { Badge, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

export function InvoicesPage() {
  const navigate = useNavigate();
  const { isManager } = useBillingRights();
  const [status, setStatus] = useState<InvoiceStatus | undefined>();
  const [org, setOrg] = useState({ id: "", label: "" });
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const { data, isFetching } = useListInvoicesQuery({ status, organization_id: org.id || undefined, page, per_page: perPage });
  // contacts never see drafts (the server leaves them out)
  const statuses = toOptions(INVOICE_STATUS_LABELS, isManager ? undefined : ["issued", "paid", "overdue", "void"]);

  const columns: Column<Invoice>[] = [
    { key: "number", header: "Invoice", render: (i) => <span className="font-medium text-slate-900">{i.number ?? "Draft"}</span> },
    ...(isManager ? [{ key: "org", header: "Organisation", render: (i: Invoice) => <OrganizationNameCell organizationId={i.organization_id} /> }] : []),
    { key: "kind", header: "For", hideOnMobile: true, render: (i) => INVOICE_KIND_LABELS[i.kind] },
    { key: "total", header: "Total", render: (i) => inr(i.total) },
    { key: "due", header: "Balance due", render: (i) => (i.balance_due ? inr(i.balance_due) : "—") },
    { key: "status", header: "Status", render: (i) => <Badge tone={INVOICE_STATUS_TONES[i.status]}>{INVOICE_STATUS_LABELS[i.status]}</Badge> },
    { key: "date", header: "Due date", hideOnMobile: true, render: (i) => formatDate(i.due_date) },
  ];

  return (
    <>
      <PageHeader title="Billing" description={isManager ? "Every institution's invoices. Open one to see its details, record a payment or send a reminder." : "Invoices for your organisation. Open one to see its details and pay."} />
      <BillingTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={status} options={statuses} onChange={(v) => { setStatus(v as InvoiceStatus | undefined); setPage(1); }} />
          {isManager && <OrgFilter value={org.id} label={org.label} onChange={(id, label) => { setOrg({ id, label }); setPage(1); }} />}
        </FilterRow>
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(i) => i.invoice_id} loading={isFetching} onRowClick={(i) => navigate(`/billing/invoices/${i.invoice_id}`)} empty={<EmptyState icon="fileText" title="No invoices" description="Invoices appear here once they're issued." />} />
        <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={(n) => { setPerPage(n); setPage(1); }} />
      </Card>
    </>
  );
}
