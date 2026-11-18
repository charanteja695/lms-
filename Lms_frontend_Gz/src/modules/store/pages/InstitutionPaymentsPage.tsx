import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAppDispatch } from "@/app/hooks";
import { useDebouncedValue } from "@/core/hooks/useDebouncedValue";
import { toApiError } from "@/core/lib/apiError";
import { formatDate } from "@/core/lib/format";
import { toastAdded } from "@/core/toast/toastSlice";
import { inr } from "@/modules/billing/common/format";
import {
  useApproveInstitutionRequestMutation,
  useAssignInstitutionStudentCourseMutation,
  useCreateInstitutionCheckoutMutation,
  useGetInstitutionAllocationsQuery,
  useGetInstitutionPaymentRequestsQuery,
  useGetInstitutionStudentsQuery,
  useGetInstitutionTransactionsQuery,
  useGetStudentPlansQuery,
  usePreviewInstitutionCheckoutMutation,
  useRejectInstitutionRequestMutation,
  useTriggerInstitutionTestCallbackMutation,
} from "@/modules/store/api/studentSubscriptionsApi";
import { UpiQrCard } from "@/modules/store/components/UpiQrCard";
import type {
  GatewayCheckoutPayload,
  InstitutionCheckoutSummary,
  InstitutionStudentItem,
  PaymentMethodChoice,
  PaymentRequestStatus,
  StudentPaymentAllocationRecord,
  StudentPaymentRequestRecord,
  StudentPaymentTransaction,
} from "@/modules/store/studentTypes";
import {
  Alert,
  Badge,
  Button,
  Card,
  DataTable,
  EmptyState,
  Field,
  FilterRow,
  FilterSelect,
  FilterText,
  Icon,
  Modal,
  PageHeader,
  Pagination,
  Select,
  type Column,
} from "@/shared/ui";

type TabKey = "students" | "requests" | "transactions" | "allocations";

const STUDENT_PAY_TONE: Record<InstitutionStudentItem["payment_status"], "green" | "amber" | "blue" | "indigo" | "red" | "gray"> = {
  active_subscription: "green",
  pending_request: "amber",
  approved_request: "blue",
  payment_initiated: "indigo",
  failed: "red",
  unpaid: "gray",
};

const STUDENT_PAY_LABEL: Record<InstitutionStudentItem["payment_status"], string> = {
  active_subscription: "Active Plan",
  pending_request: "Pending Request",
  approved_request: "Approved (Ready)",
  payment_initiated: "Payment Initiated",
  failed: "Failed",
  unpaid: "Unpaid",
};

const REQ_TONE: Record<PaymentRequestStatus, "amber" | "blue" | "red" | "indigo" | "green" | "gray"> = {
  pending: "amber",
  approved: "blue",
  rejected: "red",
  payment_initiated: "indigo",
  paid: "green",
  failed: "red",
  cancelled: "gray",
};

export function InstitutionPaymentsPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const [tab, setTab] = useState<TabKey>("students");
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [reqStatus, setReqStatus] = useState<string | undefined>();
  const [txStatus, setTxStatus] = useState<string | undefined>();

  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Assign course modal
  const [assignStudent, setAssignStudent] = useState<InstitutionStudentItem | null>(null);
  const [assignCourseId, setAssignCourseId] = useState("");
  const [assignPlanId, setAssignPlanId] = useState("");

  // Checkout modal
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [checkoutStudentIds, setCheckoutStudentIds] = useState<string[]>([]);
  const [checkoutRequestIds, setCheckoutRequestIds] = useState<string[]>([]);
  const [checkoutPlanId, setCheckoutPlanId] = useState("");
  const [checkoutCourseId, setCheckoutCourseId] = useState("");
  const [checkoutMethod, setCheckoutMethod] = useState<PaymentMethodChoice>("upi");
  const [summary, setSummary] = useState<InstitutionCheckoutSummary | null>(null);
  const [activeOrder, setActiveOrder] = useState<{
    tx: StudentPaymentTransaction;
    gateway: GatewayCheckoutPayload;
    allocations: StudentPaymentAllocationRecord[];
  } | null>(null);

  const { data: plans = [] } = useGetStudentPlansQuery();
  const { data: studentsData, isFetching: loadingStudents } = useGetInstitutionStudentsQuery({
    search: debounced || undefined,
    page,
    per_page: perPage,
  });
  const { data: reqData, isFetching: loadingReqs } = useGetInstitutionPaymentRequestsQuery({
    status: reqStatus,
    search: debounced || undefined,
    page,
    per_page: perPage,
  });
  const { data: txData, isFetching: loadingTxs } = useGetInstitutionTransactionsQuery({
    status: txStatus,
    page,
    per_page: perPage,
  });
  const { data: allocData, isFetching: loadingAllocs } = useGetInstitutionAllocationsQuery({
    page,
    per_page: perPage,
  });

  const [assignCourse, { isLoading: assigning }] = useAssignInstitutionStudentCourseMutation();
  const [approveReq] = useApproveInstitutionRequestMutation();
  const [rejectReq] = useRejectInstitutionRequestMutation();
  const [previewCheckout, { isLoading: previewing }] = usePreviewInstitutionCheckoutMutation();
  const [createCheckout, { isLoading: creatingOrder }] = useCreateInstitutionCheckoutMutation();
  const [triggerTestCb, { isLoading: completing }] = useTriggerInstitutionTestCallbackMutation();

  const students = studentsData?.students ?? [];
  const approvedCourses = studentsData?.approved_courses ?? [];
  const defaultPlanId = plans[0]?.plan_id ?? "";

  const toggleStudent = (sid: string) => {
    setSelectedIds((prev) => (prev.includes(sid) ? prev.filter((x) => x !== sid) : [...prev, sid]));
  };

  const openCheckoutForStudents = async (studentIds: string[], planId?: string, courseId?: string, requestIds: string[] = []) => {
    const pid = planId || defaultPlanId;
    if (!pid) {
      dispatch(toastAdded({ tone: "error", title: "No subscription plans available" }));
      return;
    }
    setCheckoutStudentIds(studentIds);
    setCheckoutRequestIds(requestIds);
    setCheckoutPlanId(pid);
    setCheckoutCourseId(courseId ?? "");
    setActiveOrder(null);
    setSummary(null);
    setCheckoutOpen(true);
    try {
      const res = await previewCheckout({
        student_ids: studentIds,
        plan_id: pid,
        course_id: courseId || undefined,
        request_ids: requestIds,
      }).unwrap();
      setSummary(res);
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Could not calculate payment summary", description: toApiError(err).message }));
    }
  };

  const handlePlanOrCourseChange = async (nextPlanId: string, nextCourseId: string) => {
    setCheckoutPlanId(nextPlanId);
    setCheckoutCourseId(nextCourseId);
    if (!nextPlanId || checkoutStudentIds.length === 0) return;
    try {
      const res = await previewCheckout({
        student_ids: checkoutStudentIds,
        plan_id: nextPlanId,
        course_id: nextCourseId || undefined,
        request_ids: checkoutRequestIds,
      }).unwrap();
      setSummary(res);
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Preview failed", description: toApiError(err).message }));
    }
  };

  const handleCreateOrder = async () => {
    if (!checkoutPlanId || checkoutStudentIds.length === 0) return;
    try {
      const res = await createCheckout({
        student_ids: checkoutStudentIds,
        plan_id: checkoutPlanId,
        payment_method: checkoutMethod,
        course_id: checkoutCourseId || undefined,
        request_ids: checkoutRequestIds,
      }).unwrap();
      setActiveOrder({ tx: res.transaction, gateway: res.gateway, allocations: res.allocations });
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Could not start checkout", description: toApiError(err).message }));
    }
  };

  const handleSimulateGateway = async (outcome: "captured" | "failed") => {
    if (!activeOrder) return;
    try {
      const res = await triggerTestCb({
        txId: activeOrder.tx.tx_id,
        outcome,
        failure_reason: outcome === "failed" ? "Simulated payment failure" : undefined,
      }).unwrap();
      dispatch(
        toastAdded({
          tone: res.transaction.status === "succeeded" ? "success" : "error",
          title: res.transaction.status === "succeeded" ? "Payment verified & access activated" : "Payment failed",
          description:
            res.transaction.status === "succeeded"
              ? `${res.allocations.length} student subscription(s) activated.`
              : res.transaction.failure_reason ?? "Gateway rejected payment.",
        }),
      );
      setCheckoutOpen(false);
      setSelectedIds([]);
      setActiveOrder(null);
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Verification failed", description: toApiError(err).message }));
    }
  };

  const handleAssignSubmit = async () => {
    if (!assignStudent || !assignCourseId) return;
    try {
      await assignCourse({
        student_user_id: assignStudent.student_user_id,
        course_id: assignCourseId,
        plan_id: assignPlanId || undefined,
      }).unwrap();
      dispatch(toastAdded({ tone: "success", title: "Course assigned", description: "Ready for payment." }));
      setAssignStudent(null);
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Assignment failed", description: toApiError(err).message }));
    }
  };

  const handleApprove = async (req: StudentPaymentRequestRecord) => {
    try {
      await approveReq({ requestId: req.request_id }).unwrap();
      dispatch(toastAdded({ tone: "success", title: "Request approved", description: `${req.request_ref} is ready for payment.` }));
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Approve failed", description: toApiError(err).message }));
    }
  };

  const handleReject = async (req: StudentPaymentRequestRecord) => {
    try {
      await rejectReq({ requestId: req.request_id, decision_note: "Rejected by Institution Head" }).unwrap();
      dispatch(toastAdded({ tone: "info", title: "Request rejected", description: req.request_ref }));
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Reject failed", description: toApiError(err).message }));
    }
  };

  const studentColumns: Column<InstitutionStudentItem>[] = [
    {
      key: "select",
      header: "",
      render: (s) => (
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300 text-brand-600"
          checked={selectedIds.includes(s.student_user_id)}
          onChange={() => toggleStudent(s.student_user_id)}
        />
      ),
    },
    {
      key: "student",
      header: "Student",
      render: (s) => (
        <div>
          <div className="font-semibold text-navy-950">{s.student_name}</div>
          <div className="text-xs text-slate-500">
            ID: {s.student_user_id} · {s.student_email}
          </div>
        </div>
      ),
    },
    {
      key: "course",
      header: "Course & Plan",
      render: (s) => (
        <div className="text-xs">
          <div className="font-medium text-navy-900">{s.selected_course_title ?? "Not assigned"}</div>
          <div className="text-slate-500">{s.active_plan_name ?? s.pending_plan_name ?? "No plan"}</div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Payment Status",
      render: (s) => <Badge tone={STUDENT_PAY_TONE[s.payment_status]}>{STUDENT_PAY_LABEL[s.payment_status]}</Badge>,
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (s) => (
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setAssignStudent(s);
              setAssignCourseId(s.selected_course_id ?? String(approvedCourses[0]?.course_id ?? ""));
              setAssignPlanId(s.pending_plan_id ?? defaultPlanId);
            }}
          >
            Assign Course
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={() =>
              openCheckoutForStudents(
                [s.student_user_id],
                s.pending_plan_id ?? defaultPlanId,
                s.selected_course_id ?? undefined,
                s.pending_request_id ? [s.pending_request_id] : [],
              )
            }
          >
            Pay for Student
          </Button>
        </div>
      ),
    },
  ];

  const reqColumns: Column<StudentPaymentRequestRecord>[] = [
    {
      key: "ref",
      header: "Request",
      render: (r) => (
        <div>
          <div className="font-semibold text-navy-950">{r.request_ref}</div>
          <div className="text-xs text-slate-500">{formatDate(r.created_at)}</div>
        </div>
      ),
    },
    {
      key: "student",
      header: "Student",
      render: (r) => (
        <div>
          <div className="font-medium text-navy-950">{r.student_name}</div>
          <div className="text-xs text-slate-500">{r.student_email}</div>
        </div>
      ),
    },
    {
      key: "course",
      header: "Course & Plan",
      render: (r) => (
        <div className="text-xs">
          <div className="font-medium text-navy-900">{r.course_title}</div>
          <div className="text-slate-500">{r.plan_name}</div>
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
      render: (r) => <Badge tone={REQ_TONE[r.status]}>{r.status.replace("_", " ")}</Badge>,
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (r) => (
        <div className="flex justify-end gap-2">
          {r.status === "pending" && (
            <>
              <Button size="sm" variant="secondary" onClick={() => handleApprove(r)}>
                Approve
              </Button>
              <Button size="sm" variant="ghost" onClick={() => handleReject(r)}>
                Reject
              </Button>
            </>
          )}
          {(r.status === "pending" || r.status === "approved") && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => openCheckoutForStudents([r.student_user_id], r.plan_id, r.course_id, [r.request_id])}
            >
              Pay Now
            </Button>
          )}
        </div>
      ),
    },
  ];

  const txColumns: Column<StudentPaymentTransaction>[] = [
    {
      key: "ref",
      header: "Transaction",
      render: (t) => (
        <div>
          <div className="font-semibold text-navy-950">{t.transaction_ref}</div>
          <div className="text-xs text-slate-500">{formatDate(t.created_at)}</div>
        </div>
      ),
    },
    {
      key: "plan",
      header: "Plan & Scope",
      render: (t) => (
        <div className="text-xs">
          <div className="font-medium text-navy-900">{t.plan_name}</div>
          <div className="text-slate-500">{t.course_title ?? "Subscription"}</div>
        </div>
      ),
    },
    {
      key: "amount",
      header: "Amount",
      className: "text-right",
      render: (t) => <span className="font-semibold text-navy-950">{inr(t.total_amount_paise)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (t) => (
        <Badge tone={t.status === "succeeded" ? "green" : t.status === "failed" ? "red" : "amber"}>{t.status}</Badge>
      ),
    },
  ];

  const allocColumns: Column<StudentPaymentAllocationRecord>[] = [
    {
      key: "student",
      header: "Student",
      render: (a) => (
        <div>
          <div className="font-semibold text-navy-950">{a.student_name}</div>
          <div className="text-xs text-slate-500">{a.student_email}</div>
        </div>
      ),
    },
    {
      key: "course",
      header: "Course & Plan",
      render: (a) => (
        <div className="text-xs">
          <div className="font-medium text-navy-900">{a.course_title ?? "All Plan Courses"}</div>
          <div className="text-slate-500">{a.plan_name}</div>
        </div>
      ),
    },
    {
      key: "amount",
      header: "Allocated",
      className: "text-right",
      render: (a) => <span className="font-semibold text-navy-950">{inr(a.allocated_amount_paise)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (a) => (
        <Badge tone={a.status === "succeeded" ? "green" : a.status === "failed" ? "red" : "amber"}>{a.status}</Badge>
      ),
    },
    {
      key: "activated",
      header: "Activated",
      render: (a) => <span className="text-xs text-slate-500">{a.activated_at ? formatDate(a.activated_at) : "—"}</span>,
    },
  ];

  const planOptions = useMemo(() => plans.map((p) => ({ value: p.plan_id, label: `${p.name} (${inr(p.price_paise)})` })), [plans]);
  const courseOptions = useMemo(
    () => approvedCourses.map((c) => ({ value: String(c.course_id), label: c.course_title })),
    [approvedCourses],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Institution Student Payments"
        description="Register students, review student payment requests, and pay individually or in bulk for your institution."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate("/users/import")}>
              <Icon name="upload" size={15} />
              Bulk Import CSV/Excel
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate("/users/new")}>
              <Icon name="plus" size={15} />
              Add Student
            </Button>
            {selectedIds.length > 0 && (
              <Button variant="primary" size="sm" onClick={() => openCheckoutForStudents(selectedIds)}>
                Pay for Selected ({selectedIds.length})
              </Button>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {(
          [
            ["students", "Students & Bulk Pay"],
            ["requests", "Payment Requests"],
            ["transactions", "Payment History"],
            ["allocations", "Student Allocations"],
          ] as [TabKey, string][]
        ).map(([k, label]) => (
          <Button
            key={k}
            size="sm"
            variant={tab === k ? "primary" : "ghost"}
            onClick={() => {
              setTab(k);
              setPage(1);
            }}
          >
            {label}
          </Button>
        ))}
      </div>

      {tab === "students" && (
        <Card bodyClassName="p-0">
          <FilterRow>
            <FilterText
              label="Search students"
              value={search || undefined}
              placeholder="Name, email or student ID"
              onChange={(val) => {
                setSearch(val ?? "");
                setPage(1);
              }}
            />
          </FilterRow>
          <DataTable
            columns={studentColumns}
            rows={students}
            rowKey={(s) => s.student_user_id}
            loading={loadingStudents}
            empty={
              <EmptyState
                icon="users"
                title="No students registered in your institution"
                description="Add a student or import from CSV/Excel to get started."
              />
            }
          />
          {studentsData?.page_context && studentsData.page_context.total_pages > 1 && (
            <div className="border-t border-slate-100 p-4">
              <Pagination
                pageContext={studentsData.page_context}
                disabled={loadingStudents}
                onPageChange={setPage}
                onPerPageChange={(n) => {
                  setPerPage(n);
                  setPage(1);
                }}
              />
            </div>
          )}
        </Card>
      )}

      {tab === "requests" && (
        <Card bodyClassName="p-0">
          <FilterRow>
            <FilterSelect
              label="Status"
              value={reqStatus}
              options={[
                { value: "pending", label: "Pending" },
                { value: "approved", label: "Approved" },
                { value: "payment_initiated", label: "Payment Initiated" },
                { value: "paid", label: "Paid" },
                { value: "rejected", label: "Rejected" },
                { value: "failed", label: "Failed" },
              ]}
              onChange={(val) => {
                setReqStatus(val);
                setPage(1);
              }}
            />
            <FilterText
              label="Search"
              value={search || undefined}
              placeholder="Student, request ref, course"
              onChange={(val) => {
                setSearch(val ?? "");
                setPage(1);
              }}
            />
          </FilterRow>
          <DataTable
            columns={reqColumns}
            rows={reqData?.requests ?? []}
            rowKey={(r) => r.request_id}
            loading={loadingReqs}
            empty={
              <EmptyState
                icon="fileText"
                title="No student payment requests"
                description="Requests submitted by your institution's students will appear here."
              />
            }
          />
          {reqData?.page_context && reqData.page_context.total_pages > 1 && (
            <div className="border-t border-slate-100 p-4">
              <Pagination
                pageContext={reqData.page_context}
                disabled={loadingReqs}
                onPageChange={setPage}
                onPerPageChange={(n) => {
                  setPerPage(n);
                  setPage(1);
                }}
              />
            </div>
          )}
        </Card>
      )}

      {tab === "transactions" && (
        <Card bodyClassName="p-0">
          <FilterRow>
            <FilterSelect
              label="Status"
              value={txStatus}
              options={[
                { value: "succeeded", label: "Succeeded" },
                { value: "pending", label: "Pending" },
                { value: "failed", label: "Failed" },
              ]}
              onChange={(val) => {
                setTxStatus(val);
                setPage(1);
              }}
            />
          </FilterRow>
          <DataTable
            columns={txColumns}
            rows={txData?.transactions ?? []}
            rowKey={(t) => t.tx_id}
            loading={loadingTxs}
            empty={<EmptyState icon="creditCard" title="No institution payment transactions yet" />}
          />
        </Card>
      )}

      {tab === "allocations" && (
        <Card bodyClassName="p-0">
          <DataTable
            columns={allocColumns}
            rows={allocData?.allocations ?? []}
            rowKey={(a) => a.allocation_id}
            loading={loadingAllocs}
            empty={<EmptyState icon="layers" title="No student payment allocations yet" />}
          />
        </Card>
      )}

      {/* Assign Course Modal */}
      <Modal
        open={assignStudent !== null}
        onClose={() => setAssignStudent(null)}
        size="sm"
        title="Assign Course to Student"
        description={assignStudent ? `${assignStudent.student_name} (${assignStudent.student_email})` : undefined}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAssignStudent(null)}>
              Cancel
            </Button>
            <Button variant="primary" loading={assigning} onClick={handleAssignSubmit}>
              Assign (Pending Payment)
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Approved Course">
            {(props) => (
              <Select
                {...props}
                value={assignCourseId}
                options={courseOptions}
                onChange={(e) => setAssignCourseId(e.target.value)}
              />
            )}
          </Field>
          <Field label="Subscription Plan">
            {(props) => (
              <Select
                {...props}
                value={assignPlanId}
                options={planOptions}
                onChange={(e) => setAssignPlanId(e.target.value)}
              />
            )}
          </Field>
        </div>
      </Modal>

      {/* Single / Bulk Institution Checkout Modal */}
      <Modal
        open={checkoutOpen}
        onClose={() => setCheckoutOpen(false)}
        size="lg"
        title={checkoutStudentIds.length > 1 ? `Bulk Checkout (${checkoutStudentIds.length} Students)` : "Institution Student Checkout"}
        description="Server-validated pricing and student-level payment allocations."
      >
        {!activeOrder ? (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Subscription Plan">
                {(props) => (
                  <Select
                    {...props}
                    value={checkoutPlanId}
                    options={planOptions}
                    onChange={(e) => handlePlanOrCourseChange(e.target.value, checkoutCourseId)}
                  />
                )}
              </Field>
              <Field label="Course (optional)">
                {(props) => (
                  <Select
                    {...props}
                    value={checkoutCourseId}
                    options={[{ value: "", label: "All Plan-Eligible Courses" }, ...courseOptions]}
                    onChange={(e) => handlePlanOrCourseChange(checkoutPlanId, e.target.value)}
                  />
                )}
              </Field>
            </div>

            {previewing && <Alert tone="info">Calculating server-side totals...</Alert>}

            {summary && (
              <>
                <div className="max-h-48 overflow-auto rounded-xl border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-3 py-2">Student</th>
                        <th className="px-3 py-2">Course</th>
                        <th className="px-3 py-2 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {summary.allocations.map((a) => (
                        <tr key={a.student_user_id}>
                          <td className="px-3 py-2 font-medium text-navy-950">{a.student_name}</td>
                          <td className="px-3 py-2 text-slate-600">{a.course_title ?? "Plan Access"}</td>
                          <td className="px-3 py-2 text-right font-semibold text-navy-950">{inr(a.total_amount_paise)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-brand-50/70 p-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-600">
                      {summary.student_count} student(s) · Subtotal {inr(summary.original_total_paise)} · Tax{" "}
                      {inr(summary.tax_total_paise)}
                    </div>
                    <div className="text-lg font-bold text-navy-950">Total: {inr(summary.grand_total_paise)}</div>
                  </div>
                  <div className="flex items-end gap-2">
                    <Field label="Method">
                      {(props) => (
                        <Select
                          {...props}
                          value={checkoutMethod}
                          options={[
                            { value: "upi", label: "UPI QR" },
                            { value: "card", label: "Credit / Debit Card" },
                            { value: "razorpay", label: "Razorpay" },
                          ]}
                          onChange={(e) => setCheckoutMethod(e.target.value as PaymentMethodChoice)}
                        />
                      )}
                    </Field>
                    <Button variant="primary" loading={creatingOrder} onClick={handleCreateOrder}>
                      Pay {inr(summary.grand_total_paise)} Securely
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <UpiQrCard
              transaction={activeOrder.tx}
              checkout={activeOrder.gateway}
              busy={completing}
              onBack={() => setActiveOrder(null)}
              onSimulateSuccess={() => handleSimulateGateway("captured")}
              onSimulateFailure={() => handleSimulateGateway("failed")}
              onRefreshStatus={() => {}}
            />
            <Alert tone="info" title={`Order ${activeOrder.gateway.order_id} created`}>
              Test Mode Gateway: authorize or fail this payment to verify HMAC signature and activate{" "}
              {activeOrder.allocations.length} student subscription(s).
            </Alert>
          </div>
        )}
      </Modal>
    </div>
  );
}
