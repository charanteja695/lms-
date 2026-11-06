import { useState } from "react";

import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { inr } from "@/modules/billing/common/format";
import type { Price } from "@/modules/billing/common/types";
import { useListAllPricesQuery } from "@/modules/billing/prices/api/pricesApi";
import { PriceDialog } from "@/modules/billing/prices/components/PriceDialog";
import { Badge, Button, Card, DataTable, EmptyState, PageHeader, type Column } from "@/shared/ui";

const COLUMNS: Column<Price>[] = [
  { key: "name", header: "Name", render: (p) => <span className="font-medium text-slate-900">{p.name}</span> },
  { key: "code", header: "Code", hideOnMobile: true, render: (p) => <span className="font-mono text-xs">{p.code}</span> },
  { key: "amount", header: "Per seat per year", render: (p) => inr(p.unit_amount) },
  { key: "access", header: "Learner access", hideOnMobile: true, render: (p) => (p.meta.valid_days ? `${p.meta.valid_days} days` : "Standard") },
  { key: "active", header: "", render: (p) => (p.active ? <Badge tone="green">On sale</Badge> : <Badge>Off</Badge>) },
];

export function PricesPage() {
  // companies don't sign in (the super admin posts their jobs), so only course-seat prices are sold
  const { data = [], isFetching } = useListAllPricesQuery("course_seat");
  const [editing, setEditing] = useState<Price | "new" | null>(null);

  return (
    <>
      <PageHeader title="Billing" description="Each course's price: per seat per year for institutions' quotes and invoices, and what a self-registered learner pays (plus GST) in the course store." actions={<Button icon="plus" onClick={() => setEditing("new")}>New price</Button>} />
      <BillingTabs />
      <Card bodyClassName="p-0">
        <DataTable columns={COLUMNS} rows={data} rowKey={(p) => p.price_id} loading={isFetching} onRowClick={setEditing} empty={<EmptyState icon="layers" title="No course prices yet" description="Add a price per course seat so courses can be quoted and invoiced." />} />
      </Card>
      {editing && <PriceDialog key={editing === "new" ? "new" : editing.price_id} price={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />}
    </>
  );
}
