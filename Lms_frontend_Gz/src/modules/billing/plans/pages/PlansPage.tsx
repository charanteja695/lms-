import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate } from "@/core/lib/format";
import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { inr } from "@/modules/billing/common/format";
import { PLAN_STATUS_LABELS, PLAN_STATUS_TONES } from "@/modules/billing/common/labels";
import type { OrgPlan, PlanTier } from "@/modules/billing/common/types";
import { useListMyPlansQuery, useListPlanTiersQuery, usePurchasePlanMutation } from "@/modules/billing/plans/api/plansApi";
import { Badge, Button, Card, ConfirmDialog, DataTable, EmptyState, PageHeader, type Column } from "@/shared/ui";

const PLAN_COLUMNS: Column<OrgPlan>[] = [
  { key: "tier", header: "Plan", render: (p) => <span className="font-medium capitalize">{p.tier}</span> },
  { key: "posts", header: "Job posts", render: (p) => p.job_posts },
  { key: "status", header: "Status", render: (p) => <Badge tone={PLAN_STATUS_TONES[p.status]}>{PLAN_STATUS_LABELS[p.status]}</Badge> },
  { key: "ends", header: "Runs", render: (p) => (p.starts_at ? `${formatDate(p.starts_at)} – ${formatDate(p.ends_at)}` : `${p.valid_days} days from payment`) },
];

/** An employer admin buys a plan: its invoice is issued at once, and paying it activates the plan. */
export function PlansPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: tiers = [], isLoading } = useListPlanTiersQuery();
  const { data: plans = [], isFetching } = useListMyPlansQuery();
  const [purchase] = usePurchasePlanMutation();

  const buy = (t: PlanTier) =>
    confirm.ask({ title: `Buy ${t.name}?`, description: `An invoice for ${inr(t.price)} plus GST is issued now; the plan starts when it is paid.`, confirmLabel: "Buy", tone: "primary" }, async () => {
      await purchase(t.tier).unwrap().then((r) => { notify.success("Invoice issued"); navigate(`/billing/invoices/${r.invoice.invoice_id}`); }, notify.apiError);
    });

  return (
    <>
      <PageHeader title="Billing" description="Hiring plans give your company job posts for a period. Buy one below." />
      <BillingTabs />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {!isLoading && tiers.length === 0 && <EmptyState icon="briefcase" title="No plans on sale" description="Plans appear here once the platform team prices them." />}
        {tiers.map((t) => (
          <Card key={t.tier} title={t.name} description={`${t.job_posts} job posts · ${t.valid_days} days`}>
            <p className="text-2xl font-semibold text-slate-900">{inr(t.price)}<span className="ml-1 text-sm font-normal text-slate-500">+ GST</span></p>
            <Button className="mt-4 w-full" onClick={() => buy(t)}>Buy</Button>
          </Card>
        ))}
      </div>
      <Card title="Your plans" bodyClassName="p-0">
        <DataTable columns={PLAN_COLUMNS} rows={plans} rowKey={(p) => p.plan_id} loading={isFetching} empty={<EmptyState icon="briefcase" title="No plans yet" description="Buy a plan above to start posting jobs." />} />
      </Card>
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
