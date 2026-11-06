import { useState } from "react";

import { inr, toPaise } from "@/modules/billing/common/format";
import { Button, Field, Input, Modal, Textarea } from "@/shared/ui";

/** Shared shape of "record a payment" and "issue a credit note": an amount up to a limit, plus a text that explains it. */
export function AmountReasonDialog({ title, description, amountLabel, max, textLabel, textMax, withMethod, busy, onSubmit, onClose }: {
  title: string;
  description: string;
  amountLabel: string;
  max: number;
  textLabel: string;
  textMax: number;
  withMethod?: boolean;
  busy: boolean;
  onSubmit: (paise: number, text: string, method?: string) => void;
  onClose: () => void;
}) {
  const [amount, setAmount] = useState(String(max / 100));
  const [text, setText] = useState("");
  const [method, setMethod] = useState("");
  const paise = toPaise(amount);
  const valid = paise > 0 && paise <= max && text.trim().length >= (withMethod ? 2 : 3);

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={description}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} disabled={!valid} onClick={() => onSubmit(paise, text.trim(), method.trim() || undefined)}>Save</Button></>}
    >
      <div className="space-y-3">
        <Field label={amountLabel} required hint={`Up to ${inr(max)}.`}>{(p) => <Input {...p} type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />}</Field>
        {withMethod && <Field label="Method" hint="Bank transfer, cheque, UPI…">{(p) => <Input {...p} maxLength={30} value={method} onChange={(e) => setMethod(e.target.value)} />}</Field>}
        <Field label={textLabel} required>{(p) => <Textarea {...p} rows={2} maxLength={textMax} value={text} onChange={(e) => setText(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
