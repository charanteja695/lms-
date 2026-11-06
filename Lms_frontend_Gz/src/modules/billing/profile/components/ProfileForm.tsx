import { useState } from "react";

import type { BillingProfile, BillingProfileInput } from "@/modules/billing/common/types";
import { Button, Card, Field, Input, Textarea } from "@/shared/ui";

const empty: BillingProfileInput = { legal_name: "", gstin: "", state: "", address: "", email: "" };

/** Legal name, GSTIN, state and address: frozen onto each invoice when it is issued. The state decides CGST+SGST or IGST. */
export function ProfileForm({ profile, saving, onSave, readOnly = false }: { profile?: BillingProfile; saving: boolean; onSave: (input: BillingProfileInput) => void; readOnly?: boolean }) {
  const [v, setV] = useState<BillingProfileInput>(profile ? { ...profile, gstin: profile.gstin ?? "", email: profile.email ?? "" } : empty);
  const set = (key: keyof BillingProfileInput, value: string) => setV({ ...v, [key]: value });
  const valid = v.legal_name.trim().length >= 2 && v.state.trim().length >= 2 && v.address.trim().length >= 5;

  return (
    <Card>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Legal name" required>{(p) => <Input {...p} maxLength={200} value={v.legal_name} onChange={(e) => set("legal_name", e.target.value)} />}</Field>
        <Field label="GSTIN" hint="15 characters; leave empty if unregistered.">{(p) => <Input {...p} maxLength={15} value={v.gstin ?? ""} onChange={(e) => set("gstin", e.target.value.toUpperCase())} />}</Field>
        <Field label="State" required hint="Place of supply for GST.">{(p) => <Input {...p} maxLength={60} value={v.state} onChange={(e) => set("state", e.target.value)} />}</Field>
        <Field label="Billing email">{(p) => <Input {...p} type="email" maxLength={200} value={v.email ?? ""} onChange={(e) => set("email", e.target.value)} />}</Field>
        <Field label="Address" required className="sm:col-span-2">{(p) => <Textarea {...p} rows={3} maxLength={500} value={v.address} onChange={(e) => set("address", e.target.value)} />}</Field>
      </div>
      <div className="mt-4 flex justify-end">
        {!readOnly && <Button loading={saving} disabled={!valid} onClick={() => onSave({ ...v, gstin: v.gstin?.trim() || null, email: v.email?.trim() || null })}>Save</Button>}
      </div>
    </Card>
  );
}
