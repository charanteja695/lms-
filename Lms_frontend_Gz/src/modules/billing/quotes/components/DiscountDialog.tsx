import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { inr, toPaise } from "@/modules/billing/common/format";
import type { Quote } from "@/modules/billing/common/types";
import { useDiscountQuoteMutation } from "@/modules/billing/quotes/api/quotesApi";
import { Button, Field, Input, Modal, Textarea } from "@/shared/ui";

/** A billing manager's discount on an open quote, before tax; replaces any earlier discount. */
export function DiscountDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const notify = useNotify();
  const [discount, { isLoading }] = useDiscountQuoteMutation();
  const [amount, setAmount] = useState(quote.discount ? String(quote.discount / 100) : "");
  const [note, setNote] = useState(quote.discount_note ?? "");
  const paise = toPaise(amount);
  const valid = amount !== "" && paise >= 0 && paise <= quote.subtotal && note.trim().length >= 3;

  return (
    <Modal
      open
      onClose={onClose}
      title="Discount"
      description={`Before GST. Subtotal ${inr(quote.subtotal)}.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={isLoading} disabled={!valid} onClick={() => void discount({ id: quote.quote_id, amount: paise, note: note.trim() }).unwrap().then(() => { notify.success("Discount applied"); onClose(); }, notify.apiError)}>
            Apply
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Amount (₹)" required>{(p) => <Input {...p} type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />}</Field>
        <Field label="Note" required hint="The institution sees this.">{(p) => <Textarea {...p} rows={2} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
