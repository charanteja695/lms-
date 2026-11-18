import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { inr } from "@/modules/billing/common/format";
import {
  useGetStudentPaymentHistoryQuery,
  useLazyGetStudentPaymentReceiptQuery,
} from "@/modules/store/api/studentSubscriptionsApi";
import type { PaymentReceipt, StudentPaymentTransaction, TxStatus } from "@/modules/store/studentTypes";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import {
  Badge,
  Button,
  Card,
  DataTable,
  EmptyState,
  FilterDate,
  FilterRow,
  FilterSelect,
  FilterText,
  Icon,
  Modal,
  PageHeader,
  PageLoader,
  Pagination,
  type Column,
} from "@/shared/ui";

const TX_STATUS_TONE: Record<TxStatus, "green" | "amber" | "red" | "gray"> = {
  succeeded: "green",
  pending: "amber",
  processing: "amber",
  failed: "red",
  refunded: "gray",
};

const TX_STATUS_LABELS: Record<TxStatus, string> = {
  succeeded: "Successful",
  pending: "Pending",
  processing: "Processing",
  failed: "Failed",
  refunded: "Refunded",
};

export function PaymentHistoryPage() {
  const navigate = useNavigate();
  const { isResolving, isInstitutionStudent } = useStudentType();

  useEffect(() => {
    if (!isResolving && isInstitutionStudent) {
      navigate("/courses/my", { replace: true });
    }
  }, [isResolving, isInstitutionStudent, navigate]);

  const [status, setStatus] = useState<TxStatus | undefined>();
  const [fromDate, setFromDate] = useState<string | undefined>();
  const [toDate, setToDate] = useState<string | undefined>();
  const [search, setSearch] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  const { data, isFetching } = useGetStudentPaymentHistoryQuery({
    status,
    from_date: fromDate,
    to_date: toDate,
    search,
    page,
    per_page: perPage,
  }, { skip: isInstitutionStudent });

  if (isResolving || isInstitutionStudent) {
    return <PageLoader />;
  }

  const [loadReceipt, { isFetching: loadingReceipt }] = useLazyGetStudentPaymentReceiptQuery();
  const [receipt, setReceipt] = useState<PaymentReceipt | null>(null);

  const openReceipt = async (txId: string) => {
    const res = await loadReceipt(txId).unwrap();
    setReceipt(res);
  };

  const columns: Column<StudentPaymentTransaction>[] = [
    {
      key: "ref",
      header: "Transaction ID",
      render: (tx) => <span className="font-mono text-xs font-semibold text-navy-950">{tx.transaction_ref}</span>,
    },
    {
      key: "item",
      header: "Course & Plan",
      render: (tx) => (
        <div>
          <div className="font-medium text-navy-950">{tx.course_title ?? tx.plan_name}</div>
          <div className="text-xs text-slate-500">
            {tx.plan_name} ({tx.action_type})
          </div>
        </div>
      ),
    },
    {
      key: "method",
      header: "Method",
      hideOnMobile: true,
      render: (tx) => <span className="uppercase text-xs font-medium text-slate-600">{tx.payment_method}</span>,
    },
    {
      key: "amount",
      header: "Amount",
      render: (tx) => <span className="font-semibold text-navy-950">{inr(tx.total_amount_paise)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (tx) => <Badge tone={TX_STATUS_TONE[tx.status] ?? "slate"}>{TX_STATUS_LABELS[tx.status] ?? tx.status}</Badge>,
    },
    {
      key: "date",
      header: "Date",
      hideOnMobile: true,
      render: (tx) => formatDate(tx.paid_at ?? tx.created_at),
    },
    {
      key: "actions",
      header: "Action",
      render: (tx) => (
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" loading={loadingReceipt} onClick={() => openReceipt(tx.tx_id)}>
            Receipt
          </Button>
          {tx.status === "failed" && (
            <Button
              size="sm"
              variant="primary"
              onClick={() =>
                navigate(
                  `/checkout?planId=${encodeURIComponent(tx.plan_id)}&courseId=${encodeURIComponent(
                    tx.course_id ?? "",
                  )}&action=${tx.action_type}`,
                )
              }
            >
              Retry
            </Button>
          )}
          {tx.status === "pending" && (
            <Button size="sm" variant="ghost" onClick={() => navigate(`/payment-status/${tx.tx_id}`)}>
              Status
            </Button>
          )}
        </div>
      ),
    },
  ];

  const rows = data?.transactions ?? [];
  const pageCtx = data?.page_context;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Payment History"
        description="Track every subscription payment, download receipts, or retry failed transactions."
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate("/my-subscription")}>
            <Icon name="award" size={16} />
            My Subscription
          </Button>
        }
      />

      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect
            label="Status"
            value={status}
            options={[
              { value: "succeeded", label: "Successful" },
              { value: "pending", label: "Pending" },
              { value: "failed", label: "Failed" },
            ]}
            onChange={(val) => {
              setStatus(val as TxStatus | undefined);
              setPage(1);
            }}
          />
          <FilterDate
            label="From"
            value={fromDate}
            onChange={(val) => {
              setFromDate(val);
              setPage(1);
            }}
          />
          <FilterDate
            label="To"
            value={toDate}
            onChange={(val) => {
              setToDate(val);
              setPage(1);
            }}
          />
          <FilterText
            label="Search"
            value={search}
            placeholder="TXN ref, plan, course"
            onChange={(val) => {
              setSearch(val);
              setPage(1);
            }}
          />
        </FilterRow>

        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.tx_id}
          loading={isFetching}
          empty={
            <EmptyState
              icon="creditCard"
              title="No transactions found"
              description="Payments made for subscription plans will appear here."
              action={
                <Button variant="primary" onClick={() => navigate("/browse-courses")}>
                  Browse Courses
                </Button>
              }
            />
          }
        />

        {pageCtx && pageCtx.total_pages > 1 && (
          <div className="border-t border-slate-100 p-4">
            <Pagination
              pageContext={pageCtx}
              disabled={isFetching}
              onPageChange={setPage}
              onPerPageChange={(n) => {
                setPerPage(n);
                setPage(1);
              }}
            />
          </div>
        )}
      </Card>

      <Modal
        open={receipt !== null}
        onClose={() => setReceipt(null)}
        size="md"
        title="Payment Receipt"
        description={receipt ? `Invoice ${receipt.invoice_number ?? receipt.transaction_ref}` : undefined}
        footer={
          <>
            <Button variant="secondary" onClick={() => window.print()}>
              Print Receipt
            </Button>
            <Button variant="primary" onClick={() => setReceipt(null)}>
              Close
            </Button>
          </>
        }
      >
        {receipt && (
          <div className="space-y-4 text-sm">
            <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3.5">
              <div>
                <div className="font-bold text-navy-950">{receipt.seller_name}</div>
                <div className="text-xs text-slate-500">
                  {receipt.seller_gstin ? `GSTIN: ${receipt.seller_gstin}` : `State: ${receipt.seller_state}`}
                </div>
              </div>
              <Badge tone={TX_STATUS_TONE[receipt.status] ?? "slate"}>
                {TX_STATUS_LABELS[receipt.status] ?? receipt.status}
              </Badge>
            </div>

            <dl className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <dt className="text-slate-500">Transaction Ref</dt>
                <dd className="mt-0.5 font-mono font-semibold text-navy-950">{receipt.transaction_ref}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Invoice Number</dt>
                <dd className="mt-0.5 font-semibold text-navy-950">{receipt.invoice_number ?? "Pending"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Plan</dt>
                <dd className="mt-0.5 font-semibold text-navy-950">{receipt.plan_name}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Payment Method</dt>
                <dd className="mt-0.5 uppercase font-semibold text-navy-950">{receipt.payment_method}</dd>
              </div>
              {receipt.course_title && (
                <div className="col-span-2">
                  <dt className="text-slate-500">Course</dt>
                  <dd className="mt-0.5 font-semibold text-navy-950">{receipt.course_title}</dd>
                </div>
              )}
              <div>
                <dt className="text-slate-500">Gateway Order ID</dt>
                <dd className="mt-0.5 font-mono text-slate-700">{receipt.gateway_order_id}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Date</dt>
                <dd className="mt-0.5 text-slate-700">{formatDate(receipt.paid_at ?? receipt.created_at)}</dd>
              </div>
            </dl>

            <div className="space-y-1.5 border-t border-slate-200 pt-3 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Original Amount</span>
                <span>{inr(receipt.original_amount_paise)}</span>
              </div>
              {receipt.discount_paise > 0 && (
                <div className="flex justify-between text-emerald-700">
                  <span>Discount / Upgrade Credit</span>
                  <span>−{inr(receipt.discount_paise)}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Tax / GST</span>
                <span>{inr(receipt.tax_paise)}</span>
              </div>
              <div className="flex justify-between border-t border-slate-100 pt-2 text-sm font-bold text-navy-950">
                <span>Total Amount</span>
                <span>{inr(receipt.total_amount_paise)}</span>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
