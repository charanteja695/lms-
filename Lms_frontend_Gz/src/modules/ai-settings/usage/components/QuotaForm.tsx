import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import type { Quota } from "@/modules/ai-settings/common/types";
import { useSetAiQuotaMutation } from "@/modules/ai-settings/usage/api/usageApi";
import { Badge, Button, Card, Checkbox, Field, Input } from "@/shared/ui";

type Draft = { tokens: string; requests: string; budget: string; enabled: boolean };

const toDraft = (q: Quota): Draft => ({
  tokens: q.is_default ? "" : String(q.monthly_token_limit),
  requests: q.is_default ? "" : String(q.monthly_request_limit),
  budget: q.is_default ? "" : String(q.monthly_budget_cents / 100),
  enabled: q.enabled,
});
const orNull = (v: string, scale = 1) => (v.trim() === "" ? null : Math.round(Number(v) * scale));

/** An AI manager sets an organisation's monthly limits; an empty field falls back to the platform default. */
export function QuotaForm({ quota }: { quota: Quota }) {
  const notify = useNotify();
  const [save, { isLoading }] = useSetAiQuotaMutation();
  const [draft, setDraft] = useState<Draft>(() => toDraft(quota));
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  return (
    <Card
      title="Monthly limits"
      description="Leave a field empty to use the platform default. Turning AI off stops every AI feature for this organisation at once."
      actions={quota.is_default ? <Badge>Platform defaults</Badge> : <Badge tone="indigo">Custom limits</Badge>}
    >
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Requests per month">{(p) => <Input {...p} type="number" min={0} value={draft.requests} placeholder={String(quota.monthly_request_limit)} onChange={(e) => set({ requests: e.target.value })} />}</Field>
        <Field label="Tokens per month">{(p) => <Input {...p} type="number" min={0} value={draft.tokens} placeholder={String(quota.monthly_token_limit)} onChange={(e) => set({ tokens: e.target.value })} />}</Field>
        <Field label="Budget per month (US$)">{(p) => <Input {...p} type="number" min={0} step="0.01" value={draft.budget} placeholder={String(quota.monthly_budget_cents / 100)} onChange={(e) => set({ budget: e.target.value })} />}</Field>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <Checkbox label="AI is on for this organisation" checked={draft.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
        <Button
          loading={isLoading}
          onClick={() =>
            void save({
              organizationId: quota.organization_id,
              body: { monthly_request_limit: orNull(draft.requests), monthly_token_limit: orNull(draft.tokens), monthly_budget_cents: orNull(draft.budget, 100), enabled: draft.enabled },
            })
              .unwrap()
              .then((q) => { setDraft(toDraft(q)); notify.success("Limits saved"); }, notify.apiError)
          }
        >
          Save limits
        </Button>
      </div>
    </Card>
  );
}
