import { formatDate } from "@/core/lib/format";
import { inr } from "@/modules/billing/common/format";
import { useGetMyPurchasesQuery } from "@/modules/store/api/storeApi";
import type { CoursePurchase } from "@/modules/store/types";
import { Badge, Card, DataTable, EmptyState, type Column } from "@/shared/ui";

const STATUS: Record<CoursePurchase["status"], { label: string; tone: "green" | "amber" | "gray" }> = {
  paid: { label: "Paid", tone: "green" },
  pending: { label: "Waiting for payment", tone: "amber" },
  cancelled: { label: "Cancelled", tone: "gray" },
};

const COLUMNS: Column<CoursePurchase>[] = [
  { key: "course", header: "Course", render: (p) => <span className="font-semibold text-navy-950">{p.course_name}</span> },
  { key: "access", header: "Access", hideOnMobile: true, render: (p) => `${p.valid_days} days` },
  { key: "amount", header: "Amount", render: (p) => inr(p.amount) },
  { key: "invoice", header: "Invoice", hideOnMobile: true, render: (p) => <span className="font-mono text-xs">{p.invoice_number ?? "—"}</span> },
  { key: "status", header: "Status", render: (p) => <Badge tone={STATUS[p.status].tone}>{STATUS[p.status].label}</Badge> },
  { key: "date", header: "Date", hideOnMobile: true, render: (p) => formatDate(p.paid_at ?? p.created_at) },
];

/** Every course they bought, with its GST invoice number. */
export function PurchasesTable() {
  const { data = [], isFetching } = useGetMyPurchasesQuery();
  return (
    <Card bodyClassName="p-0">
      <DataTable
        columns={COLUMNS}
        rows={data}
        rowKey={(p) => p.purchase_id}
        loading={isFetching}
        empty={<EmptyState icon="briefcase" title="No purchases yet" description="Courses you buy appear here with their invoice number." />}
      />
    </Card>
  );
}
