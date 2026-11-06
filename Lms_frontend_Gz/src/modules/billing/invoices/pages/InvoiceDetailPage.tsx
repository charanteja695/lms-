import { useParams } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { AmountRows } from "@/modules/billing/common/components/AmountRows";
import { inr } from "@/modules/billing/common/format";
import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { INVOICE_KIND_LABELS, INVOICE_STATUS_LABELS, INVOICE_STATUS_TONES } from "@/modules/billing/common/labels";
import type { InvoiceLine } from "@/modules/billing/common/types";
import { useGetInvoiceQuery } from "@/modules/billing/invoices/api/invoicesApi";
import { InvoiceManagerActions } from "@/modules/billing/invoices/components/InvoiceManagerActions";
import { CreditNotesCard, PartyBlock, PaymentsCard } from "@/modules/billing/invoices/components/InvoiceRecords";
import { PayOnlineButton } from "@/modules/billing/invoices/components/PayOnlineButton";
import { Alert, Badge, Card, DataTable, EmptyState, PageHeader, PageLoader, type Column } from "@/shared/ui";

const LINE_COLUMNS: Column<InvoiceLine>[] = [
  { key: "desc", header: "Description", render: (l) => l.description },
  { key: "sac", header: "SAC", hideOnMobile: true, render: (l) => l.sac_code },
  { key: "qty", header: "Qty", render: (l) => l.quantity.toLocaleString() },
  { key: "unit", header: "Unit", hideOnMobile: true, render: (l) => inr(l.unit_amount) },
  { key: "amount", header: "Amount", render: (l) => inr(l.amount) },
];

export function InvoiceDetailPage() {
  const { invoiceId = "" } = useParams();
  const { isManager, canUpdate } = useBillingRights();
  const { data: inv, isLoading, isError } = useGetInvoiceQuery(invoiceId);

  if (isLoading) return <PageLoader />;
  if (isError || !inv) return <EmptyState icon="alert" title="Invoice not found" />;

  return (
    <>
      <PageHeader
        title={inv.number ?? "Draft invoice"}
        description={<span className="flex items-center gap-2"><Badge tone={INVOICE_STATUS_TONES[inv.status]}>{INVOICE_STATUS_LABELS[inv.status]}</Badge>{INVOICE_KIND_LABELS[inv.kind]}{inv.due_date && ` · due ${formatDate(inv.due_date)}`}</span>}
        backTo="/billing/invoices"
        backLabel="Invoices"
        actions={<>{isManager && <InvoiceManagerActions invoice={inv} />}{canUpdate && <PayOnlineButton invoice={inv} />}</>}
      />
      {inv.status === "void" && <Alert tone="info" className="mb-4" title="Void">{inv.void_reason}</Alert>}
      {inv.refund_due > 0 && <Alert tone="warning" className="mb-4" title={`Refund due: ${inr(inv.refund_due)}`}>A credit note was issued against money already paid.</Alert>}
      <Card className="mb-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <PartyBlock title="From" party={inv.seller} />
          <PartyBlock title="Bill to" party={inv.customer} />
          <div className="text-sm text-slate-600">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Details</p>
            {inv.issue_date && <p>Issued {formatDate(inv.issue_date)}</p>}
            {inv.place_of_supply && <p>Place of supply: {inv.place_of_supply}</p>}
            {inv.note && <p className="mt-1 whitespace-pre-wrap">{inv.note}</p>}
          </div>
        </div>
      </Card>
      <Card className="mb-4" bodyClassName="p-0">
        <DataTable columns={LINE_COLUMNS} rows={inv.lines} rowKey={(l) => String(l.position)} />
        <div className="border-t border-slate-100 p-4">
          <AmountRows rows={[
            { label: "Subtotal", amount: inv.subtotal },
            { label: "Discount", amount: inv.discount, optional: true, negative: true },
            { label: "Taxable", amount: inv.taxable },
            { label: "CGST", amount: inv.cgst, optional: true },
            { label: "SGST", amount: inv.sgst, optional: true },
            { label: "IGST", amount: inv.igst, optional: true },
            { label: "Total", amount: inv.total, strong: true },
            { label: "Credited", amount: inv.credited, optional: true, negative: true },
            { label: "Paid", amount: inv.amount_paid, optional: true, negative: true },
            { label: "Balance due", amount: inv.balance_due, strong: true },
          ]} />
        </div>
      </Card>
      <div className="space-y-4">
        <PaymentsCard payments={inv.payments} />
        <CreditNotesCard notes={inv.credit_notes} />
      </div>
    </>
  );
}
