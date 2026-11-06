import { formatDate, formatDateTime } from "@/core/lib/format";
import { inr } from "@/modules/billing/common/format";
import type { CreditNote, Party, Payment } from "@/modules/billing/common/types";
import { Badge, Card, DataTable, type Column } from "@/shared/ui";

const PAYMENT_TONES = { pending: "amber", succeeded: "green", failed: "red" } as const;

const PAYMENT_COLUMNS: Column<Payment>[] = [
  { key: "amount", header: "Amount", render: (p) => inr(p.amount) },
  { key: "method", header: "Method", render: (p) => p.method.replace(/_/g, " ") },
  { key: "ref", header: "Reference", hideOnMobile: true, render: (p) => p.reference ?? p.gateway_order_id ?? "—" },
  { key: "status", header: "Status", render: (p) => <Badge tone={PAYMENT_TONES[p.status]}>{p.status}</Badge> },
  { key: "when", header: "Paid", hideOnMobile: true, render: (p) => (p.paid_at ? formatDateTime(p.paid_at) : "—") },
];

const CREDIT_COLUMNS: Column<CreditNote>[] = [
  { key: "number", header: "Credit note", render: (c) => <span className="font-medium">{c.number}</span> },
  { key: "reason", header: "Reason", render: (c) => c.reason },
  { key: "total", header: "Total (with GST)", render: (c) => inr(c.total) },
  { key: "when", header: "Date", hideOnMobile: true, render: (c) => formatDate(c.created_at) },
];

export function PaymentsCard({ payments }: { payments: Payment[] }) {
  if (payments.length === 0) return null;
  return <Card title="Payments" bodyClassName="p-0"><DataTable columns={PAYMENT_COLUMNS} rows={payments} rowKey={(p) => p.payment_id} /></Card>;
}

export function CreditNotesCard({ notes }: { notes: CreditNote[] }) {
  if (notes.length === 0) return null;
  return <Card title="Credit notes" bodyClassName="p-0"><DataTable columns={CREDIT_COLUMNS} rows={notes} rowKey={(c) => c.credit_note_id} /></Card>;
}

/** Seller and the customer as frozen on the invoice when it was issued (a draft has none yet). */
export function PartyBlock({ title, party }: { title: string; party: Party | null }) {
  return (
    <div className="text-sm">
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
      {party ? (
        <>
          <p className="font-medium text-slate-900">{party.legal_name}</p>
          {party.address && <p className="whitespace-pre-wrap text-slate-600">{party.address}</p>}
          <p className="text-slate-600">{[party.state, party.gstin && `GSTIN ${party.gstin}`].filter(Boolean).join(" · ")}</p>
        </>
      ) : (
        <p className="text-slate-500">Taken from the billing profile when issued.</p>
      )}
    </div>
  );
}
