import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useGetInstitutionRequestDetailQuery,
  useAcceptQuotationMutation,
  useRequestModificationMutation,
  useRejectQuotationMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import { inr } from "@/modules/billing/common/format";
import { Alert, Badge, Button, Card, Icon, Modal, PageHeader, PageLoader, StatTile, Textarea } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";

export function InstitutionQuotationReviewPage() {
  const { requestId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();

  const { data: request, isLoading, isError, refetch } = useGetInstitutionRequestDetailQuery(requestId, {
    skip: !requestId,
  });

  const [acceptQuotation, { isLoading: isAccepting }] = useAcceptQuotationMutation();
  const [requestModification, { isLoading: isModifying }] = useRequestModificationMutation();
  const [rejectQuotation, { isLoading: isRejecting }] = useRejectQuotationMutation();

  // Modals state
  const [modifyModalOpen, setModifyModalOpen] = useState(false);
  const [modifyNotes, setModifyNotes] = useState("");
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  if (isLoading) return <PageLoader />;
  if (isError || !request) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <Alert tone="error" title="Purchase Request Not Found">
          Unable to find request #{requestId}.
        </Alert>
        <div className="mt-4">
          <Button variant="secondary" onClick={() => navigate("/institution/purchases")}>
            Back to Purchases
          </Button>
        </div>
      </div>
    );
  }

  const quote = request.quotation;
  const payment = request.payment_info;

  const handleAccept = async () => {
    try {
      await acceptQuotation(requestId).unwrap();
      notify.success("Quotation Accepted", "You can now proceed with payment for this package.");
      refetch();
    } catch (err: any) {
      notify.error("Error", err?.data?.detail || "Could not accept quotation.");
    }
  };

  const handleModifySubmit = async () => {
    if (!modifyNotes.trim()) return;
    try {
      await requestModification({ id: requestId, notes: modifyNotes.trim() }).unwrap();
      setModifyModalOpen(false);
      notify.info("Modification Requested", "Admin has been notified with your feedback.");
      refetch();
    } catch (err: any) {
      notify.error("Error", err?.data?.detail || "Could not request modification.");
    }
  };

  const handleRejectSubmit = async () => {
    try {
      await rejectQuotation({ id: requestId, reason: rejectReason.trim() }).unwrap();
      setRejectModalOpen(false);
      notify.info("Quotation Rejected", "You have rejected this quotation.");
      refetch();
    } catch (err: any) {
      notify.error("Error", err?.data?.detail || "Could not reject quotation.");
    }
  };

  const statusBadgeTone = (status: string) => {
    switch (status) {
      case "approved":
        return "green";
      case "paid":
        return "blue";
      case "accepted":
        return "blue";
      case "quoted":
        return "amber";
      case "rejected":
        return "gray";
      case "modification_requested":
        return "amber";
      default:
        return "gray";
    }
  };

  return (
    <div className="mx-auto max-w-5xl py-2 space-y-6">
      <PageHeader
        title={`Institutional Quotation #${quote?.quotation_number || `QUO-${request.public_id}`}`}
        description={`Formal bulk course quotation prepared for ${request.institution_name}`}
        backTo="/institution/purchases"
        backLabel="Back to Purchases"
        actions={
          <div className="flex items-center gap-2">
            {quote?.version && quote.version > 1 && (
              <Badge tone="purple" className="text-xs px-2.5 py-1">
                Version {quote.version}
              </Badge>
            )}
            <Badge tone={statusBadgeTone(request.status) as any} className="text-xs px-3 py-1 uppercase font-bold tracking-wide">
              {request.status.replace("_", " ")}
            </Badge>
          </div>
        }
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatTile icon="book" label="Requested Courses" value={request.requested_courses.length} />
        <StatTile icon="users" label="Approved Seats" value={`${quote?.approved_seats || request.seats_requested} Students`} />
        <StatTile icon="clock" label="Validity Duration" value={`${quote?.approved_duration_days || request.duration_days_requested} Days`} />
        <StatTile
          icon="creditCard"
          label="Grand Total Payable"
          value={quote ? inr(quote.total_paise) : "Awaiting Quote"}
        />
      </div>

      {/* Status Notifications */}
      {request.status === "pending" && (
        <Alert tone="info" title="Awaiting Admin Quotation">
          Your request for {request.requested_courses.length} courses and {request.seats_requested} student seats is under review by the Admin. You will be notified once the quotation is ready.
        </Alert>
      )}

      {request.status === "quoted" && (
        <Alert tone="success" title="Quotation Ready for Review">
          Admin has prepared the following quotation. Please review the course rates, volume discounts, taxes, and validity before accepting.
        </Alert>
      )}

      {request.status === "accepted" && (
        <Alert tone="info" title="Quotation Accepted – Ready for Payment">
          You have approved this quotation. Click &quot;Proceed to Payment&quot; below to complete checkout through the payment gateway.
        </Alert>
      )}

      {request.status === "paid" && (
        <Alert tone="success" title="Payment Verified – Pending Activation">
          Your payment of {quote ? inr(quote.total_paise) : ""} has been verified! Admin will now activate the course package for your students.
        </Alert>
      )}

      {request.status === "approved" && (
        <Alert tone="success" title="Package Active – Courses Available">
          This institutional package is active! Eligible students in {request.institution_name} now have automatic access in their dashboard.
        </Alert>
      )}

      {request.status === "modification_requested" && (
        <Alert tone="warning" title="Modification Requested">
          You have requested changes to this quotation. Admin will review your notes and issue an updated quotation version.
        </Alert>
      )}

      {/* Itemized Quotation Card */}
      {quote ? (
        <Card
          title="Itemized Course Pricing & Entitlement Details"
          description="Complete course-wise institutional rate breakdown, student seat allocations, and tax calculations."
        >
          {quote.package_starts_at && quote.package_ends_at && (
            <div className="mb-4 p-3 bg-blue-50/60 rounded-xl border border-blue-200 flex flex-col sm:flex-row sm:items-center justify-between text-xs text-blue-900 gap-2">
              <div>
                <span className="font-bold">Approved Package Validity:</span>{" "}
                {new Date(quote.package_starts_at).toLocaleDateString()} to{" "}
                {new Date(quote.package_ends_at).toLocaleDateString()} ({quote.approved_duration_days} Days)
              </div>
              <div className="font-semibold text-blue-700">
                Capacity: {quote.approved_seats} Student Seats
              </div>
            </div>
          )}

          <div className="overflow-x-auto border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] uppercase font-semibold text-slate-500 border-b">
                <tr>
                  <th className="px-4 py-3">Course Title</th>
                  <th className="px-4 py-3">Pricing Method</th>
                  <th className="px-4 py-3 text-right">Capacity</th>
                  <th className="px-4 py-3 text-right">Unit Rate</th>
                  <th className="px-4 py-3 text-right">Total Course Price</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {quote.course_prices.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3.5 font-bold text-slate-900">{item.course_title}</td>
                    <td className="px-4 py-3.5">
                      <Badge tone="blue">{(item.pricing_method || "fixed").toUpperCase()}</Badge>
                    </td>
                    <td className="px-4 py-3.5 text-right font-medium text-slate-700">
                      {quote.approved_seats} students
                    </td>
                    <td className="px-4 py-3.5 text-right font-semibold text-slate-900">
                      {inr(item.unit_price_paise)}
                    </td>
                    <td className="px-4 py-3.5 text-right font-bold text-slate-900">
                      {inr(item.subtotal_paise || (item.unit_price_paise * quote.approved_seats))}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-slate-200 bg-slate-50 font-medium text-xs">
                <tr>
                  <td colSpan={4} className="px-4 py-2.5 text-right text-slate-600">Subtotal:</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-slate-900">{inr(quote.subtotal_paise)}</td>
                </tr>
                {quote.discount_paise > 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-2.5 text-right text-emerald-700">
                      Bulk Volume Discount {quote.discount_note ? `(${quote.discount_note})` : ""}:
                    </td>
                    <td className="px-4 py-2.5 text-right text-emerald-700 font-bold">
                      - {inr(quote.discount_paise)}
                    </td>
                  </tr>
                )}
                <tr>
                  <td colSpan={4} className="px-4 py-2.5 text-right text-slate-600">Taxable Amount:</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-slate-900">
                    {inr(quote.taxable_paise !== undefined ? quote.taxable_paise : (quote.subtotal_paise - quote.discount_paise))}
                  </td>
                </tr>
                <tr>
                  <td colSpan={4} className="px-4 py-2.5 text-right text-slate-600">
                    GST ({quote.tax_rate_percent}%):
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold text-slate-900">{inr(quote.tax_paise)}</td>
                </tr>
                <tr className="text-sm font-bold bg-blue-50/70 border-t border-blue-200">
                  <td colSpan={4} className="px-4 py-3 text-right text-blue-900">Final Payable Amount:</td>
                  <td className="px-4 py-3 text-right text-blue-900 text-base">{inr(quote.total_paise)}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          {quote.notes && (
            <div className="mt-4 p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs">
              <p className="font-bold text-slate-600 uppercase tracking-wider mb-1 text-[10px]">Admin Quotation Notes:</p>
              <p className="text-slate-800">{quote.notes}</p>
            </div>
          )}

          {quote.expires_at && (
            <p className="mt-3 text-[11px] text-slate-400 text-right">
              Quotation valid until: {new Date(quote.expires_at).toLocaleDateString()}
            </p>
          )}
        </Card>
      ) : (
        <Card title="Requested Courses">
          <ul className="divide-y divide-slate-100 text-xs">
            {request.requested_courses.map((c, i) => (
              <li key={i} className="py-2.5 flex items-center justify-between">
                <span className="font-bold text-slate-800">{c.course_title}</span>
                <span className="text-slate-400">Course ID: {c.course_id}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Payment Receipt if Paid */}
      {payment && payment.verified && (
        <Card title="Payment Receipt & Transaction Audit">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <p className="text-[10px] text-slate-400 font-semibold uppercase">Transaction ID</p>
              <p className="font-mono text-slate-800 font-bold mt-0.5">{payment.transaction_id || "N/A"}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-semibold uppercase">Amount Paid</p>
              <p className="font-bold text-emerald-700 text-sm mt-0.5">{inr(payment.amount_paid_paise || (quote?.total_paise ?? 0))}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-semibold uppercase">Status</p>
              <div className="mt-0.5">
                <Badge tone="green">VERIFIED VIA GATEWAY</Badge>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-end gap-3 pt-3 border-t border-slate-200">
        {request.status === "quoted" && (
          <>
            <Button
              variant="secondary"
              onClick={() => setRejectModalOpen(true)}
              disabled={isRejecting}
            >
              Reject Quotation
            </Button>
            <Button
              variant="secondary"
              onClick={() => setModifyModalOpen(true)}
              disabled={isModifying}
            >
              Request Modification
            </Button>
            <Button
              variant="primary"
              onClick={handleAccept}
              loading={isAccepting}
            >
              <Icon name="check" size={16} />
              Accept Quotation
            </Button>
          </>
        )}

        {request.status === "accepted" && (
          <Button
            variant="primary"
            onClick={() => navigate(`/institution/course-requests/${requestId}/payment`)}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            <Icon name="creditCard" size={16} />
            Proceed to Payment ({quote ? inr(quote.total_paise) : ""})
          </Button>
        )}

        {request.status === "approved" && (
          <Button
            variant="primary"
            onClick={() => navigate("/institution/purchases")}
          >
            <Icon name="users" size={16} />
            View Active Student Seats & Usage
          </Button>
        )}
      </div>

      {/* Modal: Request Modification */}
      <Modal
        open={modifyModalOpen}
        onClose={() => setModifyModalOpen(false)}
        title="Request Quotation Modification"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600">
            Tell the Admin what adjustments you need (e.g. adjust seat count, pricing, or duration). A revised quotation version will be generated.
          </p>
          <Textarea
            rows={4}
            value={modifyNotes}
            onChange={(e) => setModifyNotes(e.target.value)}
            placeholder="e.g. Can we adjust student seats to 250 with a revised discount tier?"
            required
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModifyModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleModifySubmit}
              loading={isModifying}
              disabled={!modifyNotes.trim()}
            >
              Send Request to Admin
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Reject Quotation */}
      <Modal
        open={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject Quotation"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600">
            Are you sure you want to reject this quotation?
          </p>
          <Textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Reason for rejecting (optional)..."
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setRejectModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleRejectSubmit}
              loading={isRejecting}
            >
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default InstitutionQuotationReviewPage;
