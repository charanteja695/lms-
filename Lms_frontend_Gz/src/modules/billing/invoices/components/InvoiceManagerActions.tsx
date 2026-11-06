import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import type { InvoiceDetail } from "@/modules/billing/common/types";
import { useIssueCreditNoteMutation, useIssueInvoiceMutation, useRecordPaymentMutation, useVoidInvoiceMutation } from "@/modules/billing/invoices/api/invoicesApi";
import { AmountReasonDialog } from "@/modules/billing/invoices/components/AmountReasonDialog";
import { DraftEditDialog } from "@/modules/billing/invoices/components/DraftEditDialog";
import { Button, ConfirmDialog } from "@/shared/ui";

type Open = "edit" | "payment" | "credit" | null;

/** A billing manager's actions, shown by invoice state; the server refuses anything out of turn. */
export function InvoiceManagerActions({ invoice: inv }: { invoice: InvoiceDetail }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [open, setOpen] = useState<Open>(null);
  const [issue, { isLoading: issuing }] = useIssueInvoiceMutation();
  const [voidIt] = useVoidInvoiceMutation();
  const [pay, { isLoading: paying }] = useRecordPaymentMutation();
  const [credit, { isLoading: crediting }] = useIssueCreditNoteMutation();
  const id = inv.invoice_id;
  const payable = inv.status === "issued" || inv.status === "overdue";
  const creditable = (payable || inv.status === "paid") && inv.credited < inv.total;
  const close = (msg: string) => () => { notify.success(msg); setOpen(null); };

  return (
    <>
      <Button variant="ghost" onClick={() => navigate(`/billing/organizations/${inv.organization_id}/profile`)}>Billing profile</Button>
      {inv.status === "draft" && <Button variant="secondary" icon="edit" onClick={() => setOpen("edit")}>Edit</Button>}
      {(inv.status === "draft" || (payable && inv.amount_paid === 0)) && (
        <Button variant="secondary" onClick={() => confirm.ask({ title: "Void this invoice?", description: "A void invoice can't be paid; a pending plan it was for is cancelled.", confirmLabel: "Void", tone: "danger", withReason: true }, async (reason) => {
          await voidIt({ id, reason: reason ?? "" }).unwrap().then(() => notify.success("Invoice voided"), notify.apiError);
        })}>Void</Button>
      )}
      {creditable && <Button variant="secondary" onClick={() => setOpen("credit")}>Credit note</Button>}
      {payable && inv.balance_due > 0 && <Button variant="secondary" onClick={() => setOpen("payment")}>Record payment</Button>}
      {inv.status === "draft" && <Button loading={issuing} onClick={() => void issue(id).unwrap().then(() => notify.success("Invoice issued"), notify.apiError)}>Issue</Button>}

      {open === "edit" && <DraftEditDialog invoice={inv} onClose={() => setOpen(null)} />}
      {open === "payment" && (
        <AmountReasonDialog title="Record a payment" description="Money received outside the platform. Part payments are fine." amountLabel="Amount (₹)" max={inv.balance_due} textLabel="Reference" textMax={100} withMethod busy={paying}
          onSubmit={(amount, reference, method) => void pay({ id, amount, reference, method }).unwrap().then(close("Payment recorded"), notify.apiError)} onClose={() => setOpen(null)} />
      )}
      {open === "credit" && (
        <AmountReasonDialog title="Issue a credit note" description="The amount before tax; GST on it is credited too." amountLabel="Taxable amount (₹)" max={inv.taxable} textLabel="Reason" textMax={300} busy={crediting}
          onSubmit={(taxable_amount, reason) => void credit({ id, taxable_amount, reason }).unwrap().then(close("Credit note issued"), notify.apiError)} onClose={() => setOpen(null)} />
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
