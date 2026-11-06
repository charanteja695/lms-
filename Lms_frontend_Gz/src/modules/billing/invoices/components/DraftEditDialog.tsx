import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { inr, toPaise } from "@/modules/billing/common/format";
import type { InvoiceDetail } from "@/modules/billing/common/types";
import { useEditDraftMutation } from "@/modules/billing/invoices/api/invoicesApi";
import { Button, Field, Input, Modal, Textarea } from "@/shared/ui";

interface Line { description: string; quantity: string; unit_amount: string }

/** Replace a draft's lines, discount and note. Tax is recalculated by the server; an issued invoice can only be credited. */
export function DraftEditDialog({ invoice, onClose }: { invoice: InvoiceDetail; onClose: () => void }) {
  const notify = useNotify();
  const [edit, { isLoading }] = useEditDraftMutation();
  const [lines, setLines] = useState<Line[]>(invoice.lines.map((l) => ({ description: l.description, quantity: String(l.quantity), unit_amount: String(l.unit_amount / 100) })));
  const [discount, setDiscount] = useState(String(invoice.discount / 100));
  const [note, setNote] = useState(invoice.note ?? "");
  const setLine = (i: number, patch: Partial<Line>) => setLines(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const subtotal = lines.reduce((sum, l) => sum + Number(l.quantity) * toPaise(l.unit_amount), 0);
  const valid = lines.length > 0 && lines.every((l) => l.description.trim().length >= 3 && Number(l.quantity) >= 1 && l.unit_amount !== "") && toPaise(discount) <= subtotal;

  const submit = () =>
    void edit({ id: invoice.invoice_id, lines: lines.map((l) => ({ description: l.description.trim(), quantity: Number(l.quantity), unit_amount: toPaise(l.unit_amount) })), discount: toPaise(discount || "0"), note: note.trim() || undefined })
      .unwrap()
      .then(() => { notify.success("Draft updated"); onClose(); }, notify.apiError);

  return (
    <Modal open size="lg" onClose={onClose} title="Edit draft" description={`Subtotal before discount: ${inr(subtotal)}`} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={isLoading} disabled={!valid} onClick={submit}>Save</Button></>}>
      <div className="space-y-3">
        {lines.map((l, i) => (
          <div key={i} className="grid items-end gap-2 sm:grid-cols-[1fr_5rem_8rem_auto]">
            <Field label="Description">{(p) => <Input {...p} maxLength={300} value={l.description} onChange={(e) => setLine(i, { description: e.target.value })} />}</Field>
            <Field label="Qty">{(p) => <Input {...p} type="number" min={1} value={l.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} />}</Field>
            <Field label="Unit (₹)">{(p) => <Input {...p} type="number" min={0} step="0.01" value={l.unit_amount} onChange={(e) => setLine(i, { unit_amount: e.target.value })} />}</Field>
            <Button variant="ghost" icon="trash" aria-label="Remove line" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))} />
          </div>
        ))}
        <Button variant="secondary" size="sm" icon="plus" disabled={lines.length >= 50} onClick={() => setLines([...lines, { description: "", quantity: "1", unit_amount: "0" }])}>Add line</Button>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Discount (₹)">{(p) => <Input {...p} type="number" min={0} step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} />}</Field>
          <Field label="Note">{(p) => <Textarea {...p} rows={1} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
        </div>
      </div>
    </Modal>
  );
}
