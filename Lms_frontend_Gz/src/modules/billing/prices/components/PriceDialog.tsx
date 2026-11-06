import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { toOptions } from "@/core/lib/options";
import { toPaise } from "@/modules/billing/common/format";
import { PRICE_KIND_LABELS } from "@/modules/billing/common/labels";
import type { Price, PriceKind } from "@/modules/billing/common/types";
import { useCreatePriceMutation, useUpdatePriceMutation } from "@/modules/billing/prices/api/pricesApi";
import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import { Button, Checkbox, EntityPicker, Field, Input, Modal, Select } from "@/shared/ui";

/** New price (course seat or employer plan) or an edit of name, amount, learner access days and active. Kind and code never change. */
export function PriceDialog({ price, onClose }: { price?: Price; onClose: () => void }) {
  const notify = useNotify();
  const [create, { isLoading: creating }] = useCreatePriceMutation();
  const [update, { isLoading: updating }] = useUpdatePriceMutation();
  const [kind] = useState<PriceKind>(price?.kind ?? "course_seat");
  const [code, setCode] = useState({ id: price?.code ?? "", label: price?.name ?? "" });
  const [name, setName] = useState(price?.name ?? "");
  const [amount, setAmount] = useState(price ? String(price.unit_amount / 100) : "");
  const [posts, setPosts] = useState(String(price?.meta.job_posts ?? 10));
  const [days, setDays] = useState(String(price?.meta.valid_days ?? 365));
  const [active, setActive] = useState(price?.active ?? true);
  const plan = kind === "employer_plan";
  const valid = name.trim().length >= 2 && Number(amount) >= 0 && amount !== "" && Boolean(code.id.trim());
  const done = () => { notify.success("Price saved"); onClose(); };

  const submit = () =>
    void (price
      ? update({ id: price.price_id, name: name.trim(), unit_amount: toPaise(amount), active, ...(plan ? {} : { valid_days: Number(days) }) })
      : create({ kind, code: code.id.trim(), name: name.trim(), unit_amount: toPaise(amount), ...(plan ? { job_posts: Number(posts) } : {}), valid_days: Number(days) })
    ).unwrap().then(done, notify.apiError);

  return (
    <Modal
      open
      onClose={onClose}
      title={price ? `Edit ${price.name}` : "New price"}
      description="Quotes and invoices already made keep the amount they used."
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={creating || updating} disabled={!valid} onClick={submit}>Save</Button></>}
    >
      <div className="space-y-3">
        {price?.kind === "employer_plan" && <Field label="Kind">{(p) => <Select {...p} value={kind} disabled options={toOptions(PRICE_KIND_LABELS)} onChange={() => undefined} />}</Field>}
        {plan ? (
          <Field label="Tier code" required hint="e.g. starter, growth">{(p) => <Input {...p} maxLength={60} disabled={Boolean(price)} value={code.id} onChange={(e) => setCode({ id: e.target.value.toLowerCase(), label: "" })} />}</Field>
        ) : (
          <EntityPicker label="Course" required disabled={Boolean(price)} value={code.id} selectedLabel={code.label} useOptions={useCourseOptions} onChange={(id, label) => { setCode({ id, label }); if (!name) setName(label); }} />
        )}
        <Field label="Name" required>{(p) => <Input {...p} maxLength={160} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label={plan ? "Plan price (₹)" : "Per seat per year (₹)"} required>{(p) => <Input {...p} type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />}</Field>
        {plan && !price && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Job posts" required>{(p) => <Input {...p} type="number" min={1} value={posts} onChange={(e) => setPosts(e.target.value)} />}</Field>
            <Field label="Valid for (days)" required>{(p) => <Input {...p} type="number" min={1} max={1095} value={days} onChange={(e) => setDays(e.target.value)} />}</Field>
          </div>
        )}
        {!plan && (
          <Field label="Learner access (days)" required hint="How long a self-registered learner's purchase lets them study it. Buying again extends it.">
            {(p) => <Input {...p} type="number" min={1} max={1095} value={days} onChange={(e) => setDays(e.target.value)} />}
          </Field>
        )}
        {price && <Checkbox label="On sale" description="Turned off, it can't be quoted or bought." checked={active} onChange={(e) => setActive(e.target.checked)} />}
      </div>
    </Modal>
  );
}
