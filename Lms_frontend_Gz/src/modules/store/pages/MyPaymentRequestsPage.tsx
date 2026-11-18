import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useAppDispatch } from "@/app/hooks";
import { formatDate } from "@/core/lib/format";
import { toApiError } from "@/core/lib/apiError";
import { toastAdded } from "@/core/toast/toastSlice";
import { inr } from "@/modules/billing/common/format";
import {
  useCancelStudentPaymentRequestMutation,
  useGetStudentAccountContextQuery,
  useGetStudentPaymentRequestsQuery,
} from "@/modules/store/api/studentSubscriptionsApi";
import type { PaymentRequestStatus, StudentPaymentRequestRecord } from "@/modules/store/studentTypes";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import {
  Alert,
  Badge,
  Button,
  Card,
  DataTable,
  EmptyState,
  FilterRow,
  FilterSelect,
  PageHeader,
  PageLoader,
  Pagination,
  type Column,
} from "@/shared/ui";

const REQ_STATUS_TONE: Record<PaymentRequestStatus, "amber" | "blue" | "red" | "indigo" | "green" | "gray"> = {
  pending: "amber",
  approved: "blue",
  rejected: "red",
  payment_initiated: "indigo",
  paid: "green",
  failed: "red",
  cancelled: "gray",
};

const REQ_STATUS_LABEL: Record<PaymentRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  payment_initiated: "Payment Initiated",
  paid: "Paid",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function MyPaymentRequestsPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { isResolving, isInstitutionStudent } = useStudentType();

  useEffect(() => {
    if (!isResolving && isInstitutionStudent) {
      navigate("/courses/my", { replace: true });
    }
  }, [isResolving, isInstitutionStudent, navigate]);

  const [status, setStatus] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  const { data: ctx } = useGetStudentAccountContextQuery(undefined, { skip: isInstitutionStudent });
  const { data, isFetching } = useGetStudentPaymentRequestsQuery({ status, page, per_page: perPage }, { skip: isInstitutionStudent });
  const [cancelReq, { isLoading: cancelling }] = useCancelStudentPaymentRequestMutation();

  if (isResolving || isInstitutionStudent) {
    return <PageLoader />;
  }

  const handleCancel = async (req: StudentPaymentRequestRecord) => {
    try {
      await cancelReq(req.request_id).unwrap();
      dispatch(toastAdded({ tone: "success", title: "Request cancelled", description: `${req.request_ref} was cancelled.` }));
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Could not cancel request", description: toApiError(err).message }));
    }
  };

  if (ctx && ctx.can_pay_directly) {
    return (
      <div className="space-y-6">
        <PageHeader title="My Payment Requests" description="Payment requests apply to institution-managed student accounts." />
        <Alert tone="info" title="Independent student account">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>You have an independent account and can subscribe directly from Browse Courses.</span>
            <Button size="sm" variant="primary" onClick={() => navigate("/browse-courses")}>
              Browse Courses
            </Button>
          </div>
        </Alert>
      </div>
    );
  }

  const columns: Column<StudentPaymentRequestRecord>[] = [
    {
      key: "ref",
      header: "Request Ref",
      render: (r) => (
        <div>
          <div className="font-semibold text-navy-950">{r.request_ref}</div>
          <div className="text-xs text-slate-500">{formatDate(r.created_at)}</div>
        </div>
      ),
    },
    {
      key: "course",
      header: "Course & Plan",
      render: (r) => (
        <div>
          <div className="font-medium text-navy-950">{r.course_title}</div>
          <div className="text-xs text-slate-500">{r.plan_name}</div>
        </div>
      ),
    },
    {
      key: "amount",
      header: "Amount",
      className: "text-right",
      render: (r) => <span className="font-semibold text-navy-950">{inr(r.amount_paise)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <Badge tone={REQ_STATUS_TONE[r.status]}>{REQ_STATUS_LABEL[r.status]}</Badge>,
    },
    {
      key: "notes",
      header: "Notes",
      render: (r) => (
        <div className="max-w-xs text-xs text-slate-600">
          {r.decision_note ?? r.student_note ?? "—"}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      className: "text-right",
      render: (r) =>
        r.status === "pending" ? (
          <Button size="sm" variant="ghost" loading={cancelling} onClick={() => handleCancel(r)}>
            Cancel
          </Button>
        ) : r.status === "paid" ? (
          <Button size="sm" variant="secondary" onClick={() => navigate("/courses/my")}>
            Open Course
          </Button>
        ) : null,
    },
  ];

  const rows = data?.requests ?? [];
  const pageCtx = data?.page_context;

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Payment Requests"
        description="Track subscription payment requests submitted to your Institution Head."
        actions={
          <Button variant="primary" size="sm" onClick={() => navigate("/browse-courses")}>
            Request Course Access
          </Button>
        }
      />

      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect
            label="Status"
            value={status}
            options={[
              { value: "pending", label: "Pending" },
              { value: "approved", label: "Approved" },
              { value: "payment_initiated", label: "Payment Initiated" },
              { value: "paid", label: "Paid" },
              { value: "rejected", label: "Rejected" },
              { value: "failed", label: "Failed" },
              { value: "cancelled", label: "Cancelled" },
            ]}
            onChange={(val) => {
              setStatus(val);
              setPage(1);
            }}
          />
        </FilterRow>

        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.request_id}
          loading={isFetching}
          empty={
            <EmptyState
              icon="fileText"
              title="No payment requests yet"
              description="Browse approved courses and click Request Payment to ask your Institution Head to pay for your plan."
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
    </div>
  );
}
