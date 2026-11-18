import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { inr } from "@/modules/billing/common/format";
import type { StudentPaymentTransaction } from "@/modules/store/studentTypes";
import { Button, Icon } from "@/shared/ui";

export function PaymentStateCard({
  transaction,
  onRetry,
  onRefresh,
  busy,
}: {
  transaction: StudentPaymentTransaction;
  onRetry?: () => void;
  onRefresh?: () => void;
  busy?: boolean;
}) {
  const navigate = useNavigate();

  if (transaction.status === "succeeded") {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-7 text-center shadow-card">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500 text-white shadow-md shadow-emerald-500/25">
          <Icon name="check" size={32} />
        </div>
        <h2 className="mt-4 text-2xl font-bold text-navy-950">Payment Successful!</h2>
        <p className="mt-1 text-sm text-slate-600">Your subscription is now active.</p>

        <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-left">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
            <Icon name="checkCircle" size={16} className="text-emerald-600" />
            Course Access Granted
          </div>
          <p className="mt-0.5 text-xs text-emerald-700">
            {transaction.course_title
              ? `You can now access "${transaction.course_title}" and all unlocked plan features.`
              : "You can now access all course content covered under your subscription plan."}
          </p>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-4 text-left text-xs">
          <div>
            <dt className="text-slate-500">Transaction ID</dt>
            <dd className="mt-0.5 font-mono font-semibold text-navy-950">{transaction.transaction_ref}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Amount Paid</dt>
            <dd className="mt-0.5 font-semibold text-navy-950">{inr(transaction.total_amount_paise)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Subscription Plan</dt>
            <dd className="mt-0.5 font-semibold text-navy-950">{transaction.plan_name}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Date</dt>
            <dd className="mt-0.5 font-semibold text-navy-950">{formatDate(transaction.paid_at ?? transaction.created_at)}</dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Button variant="primary" onClick={() => navigate("/courses/my")}>
            Go to My Courses
          </Button>
          <Button variant="secondary" onClick={() => navigate("/my-subscription")}>
            View My Subscription
          </Button>
          <Button variant="ghost" onClick={() => navigate("/payment-history")}>
            Payment History
          </Button>
        </div>
      </div>
    );
  }

  if (transaction.status === "failed") {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-white p-7 text-center shadow-card">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-red-600">
          <Icon name="alertTriangle" size={30} />
        </div>
        <h2 className="mt-4 text-xl font-bold text-navy-950">Payment Failed</h2>
        <p className="mt-1 text-sm text-slate-600">
          {transaction.failure_reason || "Your payment could not be completed. No subscription has been activated."}
        </p>

        <div className="mt-5 rounded-xl bg-slate-50 p-4 text-left text-xs">
          <div className="flex justify-between">
            <span className="text-slate-500">Reference</span>
            <span className="font-mono font-semibold text-navy-950">{transaction.transaction_ref}</span>
          </div>
          <div className="mt-2 flex justify-between">
            <span className="text-slate-500">Plan</span>
            <span className="font-semibold text-navy-950">{transaction.plan_name}</span>
          </div>
          <div className="mt-2 flex justify-between">
            <span className="text-slate-500">Attempted Amount</span>
            <span className="font-semibold text-navy-950">{inr(transaction.total_amount_paise)}</span>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {onRetry && (
            <Button variant="primary" onClick={onRetry}>
              Retry Payment
            </Button>
          )}
          <Button variant="secondary" onClick={() => navigate("/browse-courses")}>
            Back to Browse Courses
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-white p-7 text-center shadow-card">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-600">
        <Icon name="clock" size={30} />
      </div>
      <h2 className="mt-4 text-xl font-bold text-navy-950">Payment Pending Verification</h2>
      <p className="mt-1 text-sm text-slate-600">
        Waiting for confirmation from the payment gateway for <strong className="font-mono">{transaction.transaction_ref}</strong>.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {onRefresh && (
          <Button variant="primary" onClick={onRefresh} loading={busy}>
            <Icon name="refreshCw" size={15} />
            Refresh Status
          </Button>
        )}
        <Button variant="secondary" onClick={() => navigate("/payment-history")}>
          View Payment History
        </Button>
      </div>
    </div>
  );
}
