import { useState } from "react";

import { formatDate } from "@/core/lib/format";
import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { inr } from "@/modules/billing/common/format";
import { useAdminListTransactionsQuery } from "@/modules/billing/subscription-plans/api/studentPlansAdminApi";
import type { StudentPaymentTransaction, TxStatus } from "@/modules/store/studentTypes";
import {
  Badge,
  Card,
  DataTable,
  EmptyState,
  FilterDate,
  FilterRow,
  FilterSelect,
  FilterText,
  PageHeader,
  Pagination,
  type Column,
} from "@/shared/ui";

const TONE: Record<TxStatus, "green" | "amber" | "red" | "gray"> = {
  succeeded: "green",
  pending: "amber",
  processing: "amber",
  failed: "red",
  refunded: "gray",
};

export function TransactionsAdminPage() {
  const [status, setStatus] = useState<TxStatus | undefined>();
  const [fromDate, setFromDate] = useState<string | undefined>();
  const [toDate, setToDate] = useState<string | undefined>();
  const [search, setSearch] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  const { data, isFetching } = useAdminListTransactionsQuery({
    status,
    from_date: fromDate,
    to_date: toDate,
    search,
    page,
    per_page: perPage,
  });

  const columns: Column<StudentPaymentTransaction>[] = [
    { key: "ref", header: "Transaction Ref", render: (tx) => <span className="font-mono text-xs font-semibold">{tx.transaction_ref}</span> },
    { key: "user", header: "Student ID", render: (tx) => <span className="font-mono text-xs">{tx.user_id}</span> },
    {
      key: "plan",
      header: "Plan / Course",
      render: (tx) => (
        <div>
          <div className="font-medium text-navy-950">{tx.plan_name}</div>
          {tx.course_title && <div className="text-xs text-slate-500">{tx.course_title}</div>}
        </div>
      ),
    },
    { key: "method", header: "Method", hideOnMobile: true, render: (tx) => <span className="text-xs uppercase">{tx.payment_method}</span> },
    { key: "amount", header: "Amount", render: (tx) => <span className="font-semibold">{inr(tx.total_amount_paise)}</span> },
    { key: "status", header: "Status", render: (tx) => <Badge tone={TONE[tx.status] ?? "gray"}>{tx.status}</Badge> },
    { key: "date", header: "Date", hideOnMobile: true, render: (tx) => formatDate(tx.paid_at ?? tx.created_at) },
  ];

  const rows = data?.transactions ?? [];

  return (
    <>
      <PageHeader title="Student Transactions" description="All student subscription orders, verified payments, and failures." />
      <BillingTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect
            label="Status"
            value={status}
            options={[
              { value: "succeeded", label: "Succeeded" },
              { value: "pending", label: "Pending" },
              { value: "failed", label: "Failed" },
            ]}
            onChange={(v) => {
              setStatus(v as TxStatus | undefined);
              setPage(1);
            }}
          />
          <FilterDate label="From" value={fromDate} onChange={(v) => { setFromDate(v); setPage(1); }} />
          <FilterDate label="To" value={toDate} onChange={(v) => { setToDate(v); setPage(1); }} />
          <FilterText label="Search" value={search} placeholder="TXN ref or plan" onChange={(v) => { setSearch(v); setPage(1); }} />
        </FilterRow>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.tx_id}
          loading={isFetching}
          empty={<EmptyState icon="creditCard" title="No student transactions yet" description="Student checkouts and payments will appear here." />}
        />
        <Pagination
          pageContext={data?.page_context}
          disabled={isFetching}
          onPageChange={setPage}
          onPerPageChange={(n) => {
            setPerPage(n);
            setPage(1);
          }}
        />
      </Card>
    </>
  );
}
