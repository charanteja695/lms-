import { useState } from "react";
import { useParams } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate, formatDateTime } from "@/core/lib/format";
import { AmountRows } from "@/modules/billing/common/components/AmountRows";
import { inr } from "@/modules/billing/common/format";
import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { QUOTE_STATUS_LABELS, QUOTE_STATUS_TONES } from "@/modules/billing/common/labels";
import type { QuoteLine } from "@/modules/billing/common/types";
import { useAcceptQuoteMutation, useCancelQuoteMutation, useGetQuoteQuery } from "@/modules/billing/quotes/api/quotesApi";
import { DiscountDialog } from "@/modules/billing/quotes/components/DiscountDialog";
import { Alert, Badge, Button, Card, ConfirmDialog, DataTable, EmptyState, PageHeader, PageLoader, type Column } from "@/shared/ui";

const COLUMNS: Column<QuoteLine>[] = [
  { key: "course", header: "Course", render: (l) => l.name },
  { key: "seats", header: "Seats", render: (l) => l.seats.toLocaleString() },
  { key: "term", header: "Term", render: (l) => `${l.term_days} days` },
  { key: "rate", header: "Per seat / year", hideOnMobile: true, render: (l) => inr(l.unit_amount) },
  { key: "amount", header: "Amount", render: (l) => inr(l.amount) },
];

export function QuoteDetailPage() {
  const { quoteId = "" } = useParams();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { isManager, isHead } = useBillingRights();
  const { data: quote, isLoading, isError } = useGetQuoteQuery(quoteId);
  const [accept, { isLoading: accepting }] = useAcceptQuoteMutation();
  const [cancel] = useCancelQuoteMutation();
  const [discounting, setDiscounting] = useState(false);

  if (isLoading) return <PageLoader />;
  if (isError || !quote) return <EmptyState icon="alert" title="Quote not found" />;
  const open = quote.status === "open";

  return (
    <>
      <PageHeader
        title={`Quote · ${inr(quote.total)}`}
        description={<span className="flex items-center gap-2"><Badge tone={QUOTE_STATUS_TONES[quote.status]}>{QUOTE_STATUS_LABELS[quote.status]}</Badge>{open ? `valid until ${formatDate(quote.valid_until)}` : quote.accepted_at && `accepted ${formatDateTime(quote.accepted_at)}`}</span>}
        backTo="/billing/quotes"
        backLabel="Quotes"
        actions={open && (
          <>
            {isManager && <Button variant="secondary" onClick={() => setDiscounting(true)}>Discount</Button>}
            <Button variant="secondary" onClick={() => confirm.ask({ title: "Cancel this quote?", description: "It can no longer be accepted; ask for a new one any time.", confirmLabel: "Cancel quote", tone: "danger" }, async () => {
              await cancel(quoteId).unwrap().then(() => notify.success("Quote cancelled"), notify.apiError);
            })}>Cancel quote</Button>
            {isHead && <Button loading={accepting} onClick={() => void accept(quoteId).unwrap().then(() => notify.success("Quote accepted"), notify.apiError)}>Accept</Button>}
          </>
        )}
      />
      {quote.status === "accepted" && <Alert tone="success" className="mb-4" title="Price fixed">When your subscription is activated for these courses and seats, its invoice uses this price.</Alert>}
      <Card bodyClassName="p-0">
        <DataTable columns={COLUMNS} rows={quote.lines} rowKey={(l) => l.course_id} />
        <div className="border-t border-slate-100 p-4">
          <AmountRows rows={[
            { label: "Subtotal", amount: quote.subtotal },
            { label: `Discount${quote.discount_note ? ` (${quote.discount_note})` : ""}`, amount: quote.discount, optional: true, negative: true },
            { label: "GST", amount: quote.gst },
            { label: "Total", amount: quote.total, strong: true },
          ]} />
        </div>
      </Card>
      {discounting && <DiscountDialog quote={quote} onClose={() => setDiscounting(false)} />}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
