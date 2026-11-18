import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useGetInstitutionRequestDetailQuery,
  useCheckoutInstitutionalRequestMutation,
  useTestCompletePaymentMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import { inr } from "@/modules/billing/common/format";
import {
  Alert,
  Badge,
  Button,
  Card,
  Icon,
  PageHeader,
  PageLoader,
} from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";

export function InstitutionalPaymentPage() {
  const { requestId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();

  const { data: request, isLoading, isError, refetch } = useGetInstitutionRequestDetailQuery(requestId, {
    skip: !requestId,
  });

  const [checkoutRequest, { isLoading: isCheckingOut }] = useCheckoutInstitutionalRequestMutation();
  const [testCompletePayment, { isLoading: isTestingPay }] = useTestCompletePaymentMutation();

  const [paymentMethod, setPaymentMethod] = useState<"upi" | "card" | "netbanking">("upi");
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <PageLoader />;
  if (isError || !request) {
    return (
      <div className="mx-auto max-w-4xl py-6">
        <Alert tone="error" title="Request Not Found">
          Unable to find institutional request #{requestId}.
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
  const isPaid = request.status === "paid" || request.status === "approved";

  const handlePayNow = async () => {
    setError(null);
    try {
      // 1. Get or create gateway checkout session
      const checkoutSession = await checkoutRequest(requestId).unwrap();

      // 2. Complete payment verification (simulates gateway callback in test/prod environment)
      await testCompletePayment({
        id: requestId,
        payment_method: paymentMethod === "upi" ? "upi_gateway" : "cards_gateway",
      }).unwrap();

      notify.success(
        "Payment Succeeded & Verified!",
        `Order ${checkoutSession.order_id} verified. Invoice marked paid; package pending final Admin activation.`
      );
      refetch();
    } catch (err: any) {
      setError(err?.data?.detail || err?.data?.message || "Payment verification failed. Please try again.");
    }
  };

  return (
    <div className="mx-auto max-w-4xl py-2 space-y-6">
      <PageHeader
        title="Institutional Bulk Course Payment Checkout"
        description="Verify invoice line items, tax breakdown, and complete secure payment for institutional student licenses."
        backTo={`/institution/course-requests/${requestId}`}
        backLabel="Back to Quotation Review"
      />

      {error && (
        <Alert tone="error" title="Payment Error">
          {error}
        </Alert>
      )}

      {isPaid ? (
        <div className="p-6 bg-emerald-50 rounded-2xl border border-emerald-200 text-emerald-950 space-y-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold">
              <Icon name="check" size={20} />
            </div>
            <div>
              <h3 className="font-bold text-lg text-emerald-950">Payment Completed & Verified!</h3>
              <p className="text-xs text-emerald-700">
                Transaction ID: <span className="font-mono font-bold">{request.payment_info?.transaction_id || `TX-${request.public_id}`}</span>
              </p>
            </div>
          </div>

          <div className="p-4 bg-white rounded-xl border border-emerald-100 text-xs space-y-2 text-slate-700">
            <div className="flex justify-between">
              <span>Paid Amount:</span>
              <span className="font-bold text-slate-900">{inr(request.payment_info?.amount_paid_paise || quote?.total_paise || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span>Paid At:</span>
              <span>{request.payment_info?.paid_at || new Date().toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Payment Status:</span>
              <Badge tone="green">VERIFIED</Badge>
            </div>
            <div className="flex justify-between">
              <span>Package Status:</span>
              <span className="font-semibold text-blue-900">
                {request.status === "approved" ? "Active for Students" : "Pending Admin Activation"}
              </span>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => navigate(`/institution/course-requests/${requestId}`)}>
              View Quotation
            </Button>
            <Button variant="primary" onClick={() => navigate("/institution/purchases")}>
              View Purchases & Seat Allocation
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Order & Quotation Summary Card */}
          <Card title="Quotation & Invoice Information">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs pb-4 border-b border-slate-100">
              <div>
                <p className="text-slate-400">Quotation No</p>
                <p className="font-bold text-slate-900">{quote?.quotation_number || `QUO-${request.public_id}`}</p>
              </div>
              <div>
                <p className="text-slate-400">Institution</p>
                <p className="font-bold text-slate-900">{request.institution_name}</p>
              </div>
              <div>
                <p className="text-slate-400">Approved Seats</p>
                <p className="font-bold text-slate-900">{quote?.approved_seats || request.seats_requested} Students</p>
              </div>
              <div>
                <p className="text-slate-400">Access Validity</p>
                <p className="font-bold text-slate-900">{quote?.approved_duration_days || request.duration_days_requested} Days</p>
              </div>
            </div>

            {/* Courses list */}
            <div className="pt-4 space-y-2">
              <p className="font-bold text-xs uppercase tracking-wider text-slate-700">Purchased Courses</p>
              <div className="space-y-2">
                {request.requested_courses.map((c, i) => (
                  <div key={i} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg text-xs">
                    <span className="font-semibold text-slate-800">{c.course_title}</span>
                    <span className="text-slate-400">Course ID: {c.course_id}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Tax & Total Calculation */}
            {quote && (
              <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-2">
                <div className="flex justify-between text-slate-600">
                  <span>Course Subtotal:</span>
                  <span className="font-semibold text-slate-800">{inr(quote.subtotal_paise)}</span>
                </div>
                {quote.discount_paise > 0 && (
                  <div className="flex justify-between text-emerald-700">
                    <span>Bulk Discount {quote.discount_note ? `(${quote.discount_note})` : ""}:</span>
                    <span className="font-bold">- {inr(quote.discount_paise)}</span>
                  </div>
                )}
                <div className="flex justify-between text-slate-600 pt-1 border-t border-slate-200">
                  <span>Taxable Amount:</span>
                  <span className="font-semibold text-slate-800">
                    {inr(quote.taxable_paise !== undefined ? quote.taxable_paise : (quote.subtotal_paise - quote.discount_paise))}
                  </span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>GST ({quote.tax_rate_percent}%):</span>
                  <span className="font-semibold text-slate-800">{inr(quote.tax_paise)}</span>
                </div>
                <div className="flex justify-between text-base font-bold text-slate-900 pt-2 border-t border-slate-200">
                  <span>Total Payable:</span>
                  <span className="text-blue-900 text-lg">{inr(quote.total_paise)}</span>
                </div>
              </div>
            )}
          </Card>

          {/* Payment Methods */}
          <Card title="Select Payment Gateway Method">
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { id: "upi", label: "UPI Instant Payment", desc: "GPay, PhonePe, Paytm, BHIM" },
                  { id: "card", label: "Credit / Debit Card", desc: "Visa, Mastercard, RuPay" },
                  { id: "netbanking", label: "Net Banking", desc: "SBI, HDFC, ICICI, Axis & more" },
                ].map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setPaymentMethod(m.id as any)}
                    className={`p-3.5 rounded-xl border text-left transition ${
                      paymentMethod === m.id
                        ? "border-blue-600 bg-blue-50/70 shadow-sm ring-2 ring-blue-500/20"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <p className="font-bold text-slate-900 text-xs">{m.label}</p>
                    <p className="text-[11px] text-slate-500 mt-1">{m.desc}</p>
                  </button>
                ))}
              </div>

              <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 flex items-start gap-2">
                <Icon name="shield" size={16} className="text-amber-600 shrink-0 mt-0.5" />
                <p>
                  Institutional payment orders are secured via HMAC webhook signatures. Once verified, the platform issues an official GST invoice and notifies Admin for package activation.
                </p>
              </div>
            </div>
          </Card>

          {/* Checkout CTA */}
          <div className="flex items-center justify-between pt-2">
            <Button variant="secondary" onClick={() => navigate(`/institution/course-requests/${requestId}`)}>
              Back to Quotation
            </Button>
            <Button
              variant="primary"
              size="lg"
              onClick={handlePayNow}
              loading={isCheckingOut || isTestingPay}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
            >
              <Icon name="creditCard" size={18} />
              Pay {quote ? inr(quote.total_paise) : ""} & Confirm Order
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default InstitutionalPaymentPage;
