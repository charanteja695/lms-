import { useState, useMemo } from "react";
import {
  useGetAdminInstitutionalRequestsQuery,
  useCreateAdminQuotationMutation,
  useApproveAndActivatePackageMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import type { InstitutionalPurchaseRequest } from "@/modules/billing/institutional/types";
import { inr } from "@/modules/billing/common/format";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Modal,
  PageHeader,
  PageLoader,
  StatTile,
  Textarea,
} from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";

export function AdminInstitutionalRequestsPage() {
  const notify = useNotify();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const { data: requests, isLoading, isError, refetch } = useGetAdminInstitutionalRequestsQuery(
    statusFilter === "all" ? undefined : { status: statusFilter }
  );

  const [createQuotation, { isLoading: isQuoting }] = useCreateAdminQuotationMutation();
  const [approveAndActivate, { isLoading: isApproving }] = useApproveAndActivatePackageMutation();

  // Quotation Modal state
  const [activeQuoteRequest, setActiveQuoteRequest] = useState<InstitutionalPurchaseRequest | null>(null);
  const [coursePrices, setCoursePrices] = useState<Record<string, number>>({});
  const [discountPaise, setDiscountPaise] = useState<number>(0);
  const [discountNote, setDiscountNote] = useState<string>("Bulk volume discount");
  const [taxRatePercent, setTaxRatePercent] = useState<number>(18);
  const [approvedSeats, setApprovedSeats] = useState<number>(100);
  const [approvedDurationDays, setApprovedDurationDays] = useState<number>(180);
  const [packageStartsAtStr, setPackageStartsAtStr] = useState<string>("");
  const [packageEndsAtStr, setPackageEndsAtStr] = useState<string>("");
  const [quoteNotes, setQuoteNotes] = useState<string>("Official quotation based on institutional licensing rules.");
  const [validDays, setValidDays] = useState<number>(14);

  // Detail Modal state
  const [viewDetailRequest, setViewDetailRequest] = useState<InstitutionalPurchaseRequest | null>(null);

  const requestList = requests ?? [];

  const handleOpenQuotation = (req: InstitutionalPurchaseRequest) => {
    setActiveQuoteRequest(req);
    const existingQ = req.quotation;

    const initPrices: Record<string, number> = {};
    if (existingQ && existingQ.course_prices) {
      existingQ.course_prices.forEach((cp) => {
        initPrices[String(cp.course_id)] = cp.unit_price_paise;
      });
    } else {
      req.requested_courses.forEach((c) => {
        initPrices[String(c.course_id)] = 30000; // default ₹300 per seat
      });
    }
    setCoursePrices(initPrices);

    setApprovedSeats(existingQ?.approved_seats || req.seats_requested || 100);
    setApprovedDurationDays(existingQ?.approved_duration_days || req.duration_days_requested || 180);
    setDiscountPaise(existingQ?.discount_paise || 0);
    setDiscountNote(existingQ?.discount_note || "Institutional bulk discount");
    setTaxRatePercent(existingQ?.tax_rate_percent !== undefined ? existingQ.tax_rate_percent : 18);
    setQuoteNotes(existingQ?.notes || `Approved quotation for ${req.institution_name}.`);

    const sStr = req.starts_at_requested
      ? req.starts_at_requested.split("T")[0]
      : new Date().toISOString().split("T")[0];
    const eStr = req.ends_at_requested
      ? req.ends_at_requested.split("T")[0]
      : new Date(Date.now() + 180 * 24 * 3600 * 1000).toISOString().split("T")[0];

    setPackageStartsAtStr(sStr || "");
    setPackageEndsAtStr(eStr || "");
  };

  const quotationTotals = useMemo(() => {
    let subtotal = 0;
    if (activeQuoteRequest) {
      activeQuoteRequest.requested_courses.forEach((c) => {
        const unit = Number(coursePrices[String(c.course_id)] || 0);
        subtotal += unit * Number(approvedSeats || 1);
      });
    }
    const discount = Number(discountPaise || 0);
    const taxable = Math.max(0, subtotal - discount);
    const tax = Math.round((taxable * Number(taxRatePercent || 0)) / 100);
    const total = taxable + tax;
    return { subtotal, discount, taxable, tax, total };
  }, [activeQuoteRequest, coursePrices, approvedSeats, discountPaise, taxRatePercent]);

  const handleSendQuotation = async () => {
    if (!activeQuoteRequest) return;
    try {
      const pricesArray = activeQuoteRequest.requested_courses.map((c) => ({
        course_id: String(c.course_id),
        course_title: c.course_title,
        unit_price_paise: Number(coursePrices[String(c.course_id)] || 0),
      }));

      await createQuotation({
        id: activeQuoteRequest.public_id,
        course_prices: pricesArray,
        subtotal_paise: quotationTotals.subtotal,
        discount_paise: quotationTotals.discount,
        discount_note: discountNote.trim() || undefined,
        tax_rate_percent: Number(taxRatePercent || 18),
        tax_paise: quotationTotals.tax,
        total_paise: quotationTotals.total,
        approved_seats: Number(approvedSeats),
        approved_duration_days: Number(approvedDurationDays),
        package_starts_at: packageStartsAtStr ? new Date(packageStartsAtStr).toISOString() : undefined,
        package_ends_at: packageEndsAtStr ? new Date(packageEndsAtStr).toISOString() : undefined,
        notes: quoteNotes.trim() || undefined,
        valid_days: Number(validDays || 14),
      }).unwrap();

      notify.success("Quotation Sent", `Formal quotation sent to ${activeQuoteRequest.institution_name}.`);
      setActiveQuoteRequest(null);
      refetch();
    } catch (err: any) {
      notify.error("Failed to Send Quotation", err?.data?.detail || err?.data?.message || "Could not save quotation.");
    }
  };

  const handleApproveAndActivate = async (req: InstitutionalPurchaseRequest) => {
    try {
      await approveAndActivate(req.public_id).unwrap();
      notify.success(
        "Package Approved & Activated!",
        `Courses are now automatically active for all students of ${req.institution_name}.`
      );
      if (viewDetailRequest) setViewDetailRequest(null);
      refetch();
    } catch (err: any) {
      notify.error("Approval Failed", err?.data?.detail || err?.data?.message || "Could not activate package.");
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "approved":
        return <Badge tone="green">APPROVED & ACTIVE</Badge>;
      case "paid":
        return <Badge tone="blue">PAID (READY TO ACTIVATE)</Badge>;
      case "accepted":
        return <Badge tone="blue">ACCEPTED (AWAITING PAYMENT)</Badge>;
      case "quoted":
        return <Badge tone="amber">QUOTED</Badge>;
      case "pending":
        return <Badge tone="gray">PENDING QUOTE</Badge>;
      case "modification_requested":
        return <Badge tone="amber">MODIFICATION REQUESTED</Badge>;
      case "rejected":
        return <Badge tone="gray">REJECTED</Badge>;
      default:
        return <Badge tone="gray">{status.toUpperCase()}</Badge>;
    }
  };

  return (
    <div className="mx-auto max-w-7xl py-2 space-y-6">
      <PageHeader
        title="Admin – Institutional Requests, Custom Quotations & Approvals"
        description="Review incoming bulk course requests from colleges, prepare and adjust customized quotations, verify gateway payments, and activate automatic student course enrollments."
      />

      {/* Aggregate Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatTile icon="fileText" label="Total Requests" value={requestList.length} />
        <StatTile
          icon="clock"
          label="Pending Quotations"
          value={requestList.filter((r) => r.status === "pending" || r.status === "modification_requested").length}
        />
        <StatTile
          icon="creditCard"
          label="Awaiting Activation (Paid)"
          value={requestList.filter((r) => r.status === "paid").length}
        />
        <StatTile
          icon="check"
          label="Active Packages"
          value={requestList.filter((r) => r.status === "approved").length}
        />
      </div>

      {/* Status Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        {["all", "pending", "quoted", "accepted", "paid", "approved", "modification_requested", "rejected"].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition ${
              statusFilter === st
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {st.replace("_", " ")}
          </button>
        ))}
      </div>

      {isLoading ? (
        <PageLoader />
      ) : isError ? (
        <Alert tone="error" title="Failed to load requests">
          Could not retrieve institutional requests.
        </Alert>
      ) : requestList.length === 0 ? (
        <EmptyState
          icon="fileText"
          title="No institutional requests found"
          description={statusFilter === "all" ? "No colleges have submitted purchase requests yet." : `No requests with status '${statusFilter}'.`}
        />
      ) : (
        <Card bodyClassName="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 uppercase text-[11px] text-slate-500 font-semibold border-b">
                <tr>
                  <th className="px-4 py-3.5">Req #</th>
                  <th className="px-4 py-3.5">Institution</th>
                  <th className="px-4 py-3.5">Courses & Seats</th>
                  <th className="px-4 py-3.5">Requested Dates & Duration</th>
                  <th className="px-4 py-3.5">Quotation Amount</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {requestList.map((req) => {
                  const q = req.quotation;
                  const totalPaise = q?.total_paise || (req.calculation_breakdown?.grand_total_paise) || 0;
                  const coursesCount = req.requested_courses?.length || 0;

                  return (
                    <tr key={req.public_id} className="hover:bg-slate-50/70 transition">
                      <td className="px-4 py-3.5 font-bold text-slate-900">
                        #{req.public_id}
                      </td>
                      <td className="px-4 py-3.5">
                        <p className="font-bold text-slate-900">{req.institution_name}</p>
                        <p className="text-[11px] text-slate-400">
                          {req.contact_person} · {req.contact_email}
                        </p>
                      </td>
                      <td className="px-4 py-3.5">
                        <p className="font-semibold text-slate-800">
                          {coursesCount} course{coursesCount > 1 ? "s" : ""} · {req.seats_requested} seats
                        </p>
                        <p className="text-[11px] text-slate-500 truncate max-w-xs">
                          {req.requested_courses.map((c) => c.course_title).join(", ")}
                        </p>
                      </td>
                      <td className="px-4 py-3.5">
                        {req.starts_at_requested && req.ends_at_requested ? (
                          <>
                            <p className="font-medium text-slate-800">
                              {new Date(req.starts_at_requested).toLocaleDateString()} – {new Date(req.ends_at_requested).toLocaleDateString()}
                            </p>
                            <p className="text-[11px] text-slate-500">{req.duration_days_requested} days</p>
                          </>
                        ) : (
                          <p className="text-slate-600">{req.duration_days_requested} days validity</p>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        {totalPaise > 0 ? (
                          <>
                            <p className="font-bold text-slate-900 text-sm">{inr(totalPaise)}</p>
                            {q?.discount_paise ? (
                              <p className="text-[10px] text-emerald-600">Discount: {inr(q.discount_paise)}</p>
                            ) : null}
                          </>
                        ) : (
                          <span className="text-slate-400 font-medium">Pending Quote</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        {getStatusBadge(req.status)}
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-1.5 whitespace-nowrap">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => setViewDetailRequest(req)}
                        >
                          <Icon name="eye" size={13} />
                          Details
                        </Button>

                        {(req.status === "pending" || req.status === "quoted" || req.status === "modification_requested") && (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => handleOpenQuotation(req)}
                          >
                            <Icon name="fileText" size={13} />
                            {req.status === "quoted" ? "Adjust Quote" : "Prepare Quote"}
                          </Button>
                        )}

                        {req.status === "paid" && (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => handleApproveAndActivate(req)}
                            loading={isApproving}
                          >
                            <Icon name="checkCircle" size={13} />
                            Activate Package
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Prepare / Adjust Quotation Modal */}
      <Modal
        open={Boolean(activeQuoteRequest)}
        onClose={() => setActiveQuoteRequest(null)}
        title={`Custom Quotation – ${activeQuoteRequest?.institution_name} (Req #${activeQuoteRequest?.public_id})`}
      >
        {activeQuoteRequest && (
          <div className="space-y-4 text-xs max-h-[82vh] overflow-y-auto pr-1">
            <p className="text-slate-500">
              Review requested courses and set custom pricing. The final payable amount is recalculated on the backend.
            </p>

            {/* Capacity & Dates */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Approved Seats</label>
                <Input
                  type="number"
                  min={1}
                  value={approvedSeats}
                  onChange={(e) => setApprovedSeats(Number(e.target.value))}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Approved Start Date</label>
                <Input
                  type="date"
                  value={packageStartsAtStr}
                  onChange={(e) => setPackageStartsAtStr(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Approved End Date</label>
                <Input
                  type="date"
                  value={packageEndsAtStr}
                  onChange={(e) => setPackageEndsAtStr(e.target.value)}
                />
              </div>
            </div>

            {/* Course-Wise Rates */}
            <div className="space-y-2">
              <p className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
                Course-Wise Institutional Rates (Per Student)
              </p>
              <div className="space-y-2">
                {activeQuoteRequest.requested_courses.map((course) => {
                  const cid = String(course.course_id);
                  const pricePaise = coursePrices[cid] || 0;

                  return (
                    <div
                      key={cid}
                      className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-xl"
                    >
                      <div className="flex-1 min-w-0 pr-3">
                        <p className="font-bold text-slate-900 truncate">{course.course_title}</p>
                        <p className="text-[11px] text-slate-400">ID: {cid}</p>
                      </div>

                      <div className="w-48">
                        <label className="block text-[10px] text-slate-400 font-medium">Rate / Student (₹)</label>
                        <div className="relative">
                          <input
                            type="number"
                            min={0}
                            value={Math.round(pricePaise / 100)}
                            onChange={(e) =>
                              setCoursePrices((prev) => ({
                                ...prev,
                                [cid]: Math.round(Number(e.target.value) * 100),
                              }))
                            }
                            className="w-full text-xs p-1.5 border border-slate-300 rounded font-bold text-slate-900"
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Discount, Tax & Validity */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Bulk Discount (₹)</label>
                <Input
                  type="number"
                  min={0}
                  value={Math.round(discountPaise / 100)}
                  onChange={(e) => setDiscountPaise(Math.round(Number(e.target.value) * 100))}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Discount Note</label>
                <Input
                  value={discountNote}
                  onChange={(e) => setDiscountNote(e.target.value)}
                  placeholder="e.g. Volume discount"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">GST Tax Rate (%)</label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={taxRatePercent}
                  onChange={(e) => setTaxRatePercent(Number(e.target.value))}
                />
              </div>
            </div>

            {/* Totals Summary */}
            <div className="p-4 bg-blue-900 text-white rounded-xl space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span>Subtotal ({approvedSeats} seats):</span>
                <span className="font-bold">{inr(quotationTotals.subtotal)}</span>
              </div>
              <div className="flex justify-between text-emerald-300">
                <span>Discount ({discountNote || "Special"}):</span>
                <span>- {inr(quotationTotals.discount)}</span>
              </div>
              <div className="flex justify-between text-blue-200">
                <span>Taxable Amount:</span>
                <span>{inr(quotationTotals.taxable)}</span>
              </div>
              <div className="flex justify-between text-blue-200">
                <span>GST ({taxRatePercent}%):</span>
                <span>{inr(quotationTotals.tax)}</span>
              </div>
              <div className="flex justify-between text-sm font-bold pt-2 border-t border-white/20">
                <span>Final Payable Amount:</span>
                <span className="text-emerald-400 text-lg">{inr(quotationTotals.total)}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Quotation Notes / Terms</label>
              <Textarea
                rows={2}
                value={quoteNotes}
                onChange={(e) => setQuoteNotes(e.target.value)}
              />
            </div>

            <div className="w-48">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Quotation Validity (Days)</label>
              <Input
                type="number"
                min={1}
                max={365}
                value={validDays}
                onChange={(e) => setValidDays(Number(e.target.value))}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
              <Button variant="secondary" onClick={() => setActiveQuoteRequest(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSendQuotation} loading={isQuoting}>
                <Icon name="check" size={14} />
                Send Formal Quotation
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* View Request Details Modal */}
      <Modal
        open={Boolean(viewDetailRequest)}
        onClose={() => setViewDetailRequest(null)}
        title={`Request #${viewDetailRequest?.public_id} Details`}
      >
        {viewDetailRequest && (
          <div className="space-y-4 text-xs">
            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div>
                <p className="font-bold text-slate-900 text-sm">{viewDetailRequest.institution_name}</p>
                <p className="text-slate-500">Contact: {viewDetailRequest.contact_person} ({viewDetailRequest.contact_email})</p>
              </div>
              {getStatusBadge(viewDetailRequest.status)}
            </div>

            {viewDetailRequest.quotation && (
              <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-200 space-y-1.5">
                <p className="font-bold text-blue-900 uppercase tracking-wider text-[11px]">
                  Current Quotation ({viewDetailRequest.quotation.quotation_number || `#QUO-${viewDetailRequest.public_id}`})
                </p>
                <div className="flex justify-between">
                  <span>Subtotal:</span>
                  <span className="font-semibold">{inr(viewDetailRequest.quotation.subtotal_paise)}</span>
                </div>
                {viewDetailRequest.quotation.discount_paise ? (
                  <div className="flex justify-between text-emerald-700">
                    <span>Discount:</span>
                    <span>- {inr(viewDetailRequest.quotation.discount_paise)}</span>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <span>GST ({viewDetailRequest.quotation.tax_rate_percent}%):</span>
                  <span>{inr(viewDetailRequest.quotation.tax_paise)}</span>
                </div>
                <div className="flex justify-between font-bold text-sm text-slate-900 pt-1 border-t">
                  <span>Grand Total:</span>
                  <span className="text-blue-900">{inr(viewDetailRequest.quotation.total_paise)}</span>
                </div>
              </div>
            )}

            {viewDetailRequest.payment_info && (
              <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 space-y-1">
                <p className="font-bold text-emerald-900 text-xs">Payment Verified via Gateway</p>
                <p className="text-slate-700">Transaction ID: <span className="font-mono">{viewDetailRequest.payment_info.transaction_id}</span></p>
                <p className="text-slate-700">Amount Paid: <span className="font-bold">{inr(viewDetailRequest.payment_info.amount_paid_paise || 0)}</span></p>
                <p className="text-slate-500 text-[11px]">Method: {viewDetailRequest.payment_info.method} · Paid At: {viewDetailRequest.payment_info.paid_at}</p>
              </div>
            )}

            {viewDetailRequest.modification_notes && (
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                <p className="font-bold text-amber-900">Institution Modification Request Notes:</p>
                <p className="text-slate-800 mt-1">{viewDetailRequest.modification_notes}</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="secondary" onClick={() => setViewDetailRequest(null)}>
                Close
              </Button>
              {viewDetailRequest.status === "paid" && (
                <Button
                  variant="primary"
                  onClick={() => handleApproveAndActivate(viewDetailRequest)}
                  loading={isApproving}
                >
                  <Icon name="checkCircle" size={14} />
                  Approve & Activate Package
                </Button>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default AdminInstitutionalRequestsPage;
