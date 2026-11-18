import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { toApiError } from "@/core/lib/apiError";
import { cn } from "@/core/lib/cn";
import { toastAdded } from "@/core/toast/toastSlice";
import { inr } from "@/modules/billing/common/format";
import {
  useBrowsePublishedCoursesQuery,
  useCreateStudentCheckoutMutation,
  useGetStudentAccountContextQuery,
  useLazyGetStudentPaymentReceiptQuery,
  usePreviewStudentCheckoutMutation,
  useTriggerTestGatewayCallbackMutation,
  useVerifyStudentPaymentMutation,
} from "@/modules/store/api/studentSubscriptionsApi";
import {
  useGetStoreOffersQuery,
  useBuyCourseMutation,
  useConfirmPurchaseMutation,
} from "@/modules/store/api/storeApi";
import { CourseThumbnail } from "@/modules/store/components/CourseThumbnail";
import { PaymentStateCard } from "@/modules/store/components/PaymentStateCard";
import { UpiQrCard } from "@/modules/store/components/UpiQrCard";
import { useRazorpayCheckout } from "@/modules/store/hooks/useRazorpayCheckout";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import type {
  GatewayCheckoutPayload,
  PaymentActionType,
  PaymentMethodChoice,
  StudentPaymentTransaction,
} from "@/modules/store/studentTypes";
import type { Checkout, CoursePurchase } from "@/modules/store/types";
import { Alert, Badge, Button, Card, EmptyState, Icon, PageLoader, Spinner } from "@/shared/ui";

interface MethodOption {
  id: PaymentMethodChoice;
  settingKey: string;
  title: string;
  subtitle: string;
  badges: string[];
}

const ALL_METHODS: MethodOption[] = [
  {
    id: "upi",
    settingKey: "upi",
    title: "UPI (Google Pay, PhonePe, Paytm)",
    subtitle: "Scan UPI QR or pay instantly with any UPI app",
    badges: ["GPay", "PhonePe", "Paytm"],
  },
  {
    id: "card",
    settingKey: "cards",
    title: "Credit / Debit Card",
    subtitle: "Visa, Mastercard, RuPay encrypted gateway checkout",
    badges: ["VISA", "Mastercard"],
  },
  {
    id: "netbanking",
    settingKey: "netbanking",
    title: "Net Banking",
    subtitle: "All major Indian banks supported",
    badges: ["HDFC", "ICICI", "SBI"],
  },
  {
    id: "wallet",
    settingKey: "wallet",
    title: "Razorpay Wallet",
    subtitle: "One-click wallet & express checkout",
    badges: ["Razorpay"],
  },
];

export function CheckoutPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const openRazorpay = useRazorpayCheckout();
  const { isResolving, isInstitutionStudent } = useStudentType();

  useEffect(() => {
    if (!isResolving && isInstitutionStudent) {
      dispatch(
        toastAdded({
          tone: "info",
          title: "Institutional Account",
          description: "Institution students receive courses through their institution. Individual checkout is disabled.",
        })
      );
      navigate("/courses/my", { replace: true });
    }
  }, [isResolving, isInstitutionStudent, dispatch, navigate]);

  const planId = params.get("planId") ?? "";
  const courseId = params.get("courseId") || params.get("course_id") || null;
  const actionType = (params.get("action") as PaymentActionType) || "new";

  const isIndividualCourseMode = Boolean(courseId && !planId);

  // Queries & Mutations
  const { data: accountCtx } = useGetStudentAccountContextQuery();
  const { data: publishedCoursesData } = useBrowsePublishedCoursesQuery(
    { page: 1, per_page: 100 },
    { skip: !isIndividualCourseMode }
  );
  const { data: storeOffersData } = useGetStoreOffersQuery(undefined, {
    skip: !isIndividualCourseMode,
  });

  // Individual course purchase mutations
  const [buyCourse, { isLoading: buyingCourse }] = useBuyCourseMutation();
  const [confirmPurchase, { isLoading: confirmingPurchase }] = useConfirmPurchaseMutation();

  // Subscription plan purchase mutations
  const [previewCheckout, { data: summary, isLoading: loadingSummary, error: summaryError }] =
    usePreviewStudentCheckoutMutation();
  const [createCheckout, { isLoading: creatingOrder }] = useCreateStudentCheckoutMutation();
  const [verifyPayment, { isLoading: verifying }] = useVerifyStudentPaymentMutation();
  const [triggerTestCb, { isLoading: triggeringTest }] = useTriggerTestGatewayCallbackMutation();
  const [fetchStatus, { isFetching: refreshing }] = useLazyGetStudentPaymentReceiptQuery();

  const [selectedMethod, setSelectedMethod] = useState<PaymentMethodChoice>("upi");

  // Plan order state
  const [activeOrder, setActiveOrder] = useState<{
    transaction: StudentPaymentTransaction;
    checkout: GatewayCheckoutPayload;
  } | null>(null);

  // Individual course order state
  const [individualActiveOrder, setIndividualActiveOrder] = useState<{
    purchase: CoursePurchase;
    checkout: Checkout;
  } | null>(null);
  const [individualPurchasedSuccess, setIndividualPurchasedSuccess] = useState<CoursePurchase | null>(null);

  const [testGatewayModalMethod, setTestGatewayModalMethod] = useState<PaymentMethodChoice | null>(null);

  // Individual Course data
  const matchedCourse = useMemo(() => {
    if (!courseId || !publishedCoursesData) return null;
    return publishedCoursesData.courses.find((c) => String(c.course_id) === String(courseId));
  }, [courseId, publishedCoursesData]);

  const matchedOffer = useMemo(() => {
    if (!courseId || !storeOffersData) return null;
    return storeOffersData.offers.find((o) => String(o.course_id) === String(courseId));
  }, [courseId, storeOffersData]);

  const indivCoursePrice = matchedOffer?.price ?? 49900;
  const indivCourseTax = matchedOffer?.gst ?? Math.round((indivCoursePrice * 18) / 100);
  const indivCourseTotal = matchedOffer?.total ?? (indivCoursePrice + indivCourseTax);
  const indivDurationDays = matchedOffer?.valid_days ?? 180;

  useEffect(() => {
    if (!planId || accountCtx?.must_request_payment) return;
    previewCheckout({ plan_id: planId, course_id: courseId, action_type: actionType });
  }, [planId, courseId, actionType, previewCheckout, accountCtx?.must_request_payment]);

  // Institution student check: No individual payment requests for institution students
  if (accountCtx?.must_request_payment) {
    return (
      <div className="mx-auto max-w-2xl py-8">
        <Alert tone="info" title="Institution-Managed Student Account">
          <div className="space-y-3">
            <p className="text-sm">
              Your account belongs to an educational institution. Courses purchased by your institution are automatically available in your Student Dashboard without individual payments.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="primary" onClick={() => navigate("/courses/my")}>
                Go to My Courses
              </Button>
              <Button size="sm" variant="secondary" onClick={() => navigate("/browse-courses")}>
                Browse Available Courses
              </Button>
            </div>
          </div>
        </Alert>
      </div>
    );
  }

  // Handle individual course payment
  const handleIndividualPayNow = async () => {
    if (!courseId) return;
    try {
      const result = await buyCourse({
        courseId,
        name: user?.full_name ?? "Student",
        email: user?.email ?? null,
      }).unwrap();

      setIndividualActiveOrder(result);

      if (selectedMethod === "upi") {
        return;
      }

      setTestGatewayModalMethod(selectedMethod);
    } catch (err: any) {
      dispatch(
        toastAdded({
          tone: "error",
          title: "Could not initiate payment",
          description: toApiError(err).message,
        })
      );
    }
  };

  const handleIndividualTestCallback = async (outcome: "captured" | "failed") => {
    if (!individualActiveOrder) return;
    try {
      if (outcome === "captured") {
        const confirmed = await confirmPurchase({
          purchaseId: String(individualActiveOrder.purchase.purchase_id),
          razorpay_order_id: individualActiveOrder.checkout.order_id,
          razorpay_payment_id: `pay_test_${Date.now()}`,
          razorpay_signature: "sig_test_verified",
        }).unwrap();

        setIndividualPurchasedSuccess(confirmed);
        setIndividualActiveOrder(null);
        setTestGatewayModalMethod(null);
        dispatch(
          toastAdded({
            tone: "success",
            title: "Course Purchased Successfully!",
            description: `Access has been activated. "${confirmed.course_name}" is now in My Courses.`,
          })
        );
      } else {
        setTestGatewayModalMethod(null);
        dispatch(
          toastAdded({
            tone: "error",
            title: "Payment Declined",
            description: "Test payment authorization was declined.",
          })
        );
      }
    } catch (err: any) {
      dispatch(
        toastAdded({
          tone: "error",
          title: "Payment verification failed",
          description: toApiError(err).message,
        })
      );
    }
  };

  // Handle Plan payment
  const availableMethods = useMemo(() => {
    if (isIndividualCourseMode) return ALL_METHODS;
    if (!summary) return ALL_METHODS;
    return ALL_METHODS.filter((m) => Boolean(summary.accepted_methods[m.settingKey]));
  }, [isIndividualCourseMode, summary]);

  const handlePlanPayNow = async () => {
    if (!summary || availableMethods.length === 0) return;
    try {
      const orderRes = await createCheckout({
        plan_id: summary.plan.plan_id,
        course_id: summary.course_id,
        payment_method: selectedMethod,
        action_type: actionType,
        student_name: user?.full_name ?? "Student",
        student_email: user?.email ?? null,
      }).unwrap();

      setActiveOrder(orderRes);

      if (selectedMethod === "upi") {
        return;
      }

      if (!orderRes.checkout.test_mode && orderRes.checkout.key_id) {
        const outcome = await openRazorpay(
          {
            provider: orderRes.checkout.provider,
            key_id: orderRes.checkout.key_id,
            order_id: orderRes.checkout.order_id,
            amount: orderRes.checkout.amount,
            currency: orderRes.checkout.currency,
            seller_name: orderRes.checkout.seller_name,
          },
          {
            description: `${summary.plan.name}${summary.course_title ? ` — ${summary.course_title}` : ""}`,
            name: user?.full_name ?? "Student",
            email: user?.email ?? null,
          }
        );
        if (outcome.status === "paid") {
          const verified = await verifyPayment({
            txId: orderRes.transaction.tx_id,
            razorpay_order_id: outcome.result.razorpay_order_id,
            razorpay_payment_id: outcome.result.razorpay_payment_id,
            razorpay_signature: outcome.result.razorpay_signature,
            outcome: "succeeded",
          }).unwrap();
          setActiveOrder({ transaction: verified.transaction, checkout: orderRes.checkout });
        } else if (outcome.status === "failed") {
          const verified = await verifyPayment({
            txId: orderRes.transaction.tx_id,
            razorpay_order_id: orderRes.checkout.order_id,
            outcome: "failed",
            failure_reason: outcome.reason,
          }).unwrap();
          setActiveOrder({ transaction: verified.transaction, checkout: orderRes.checkout });
        }
        return;
      }

      setTestGatewayModalMethod(selectedMethod);
    } catch (err) {
      dispatch(
        toastAdded({
          tone: "error",
          title: "Could not initiate payment",
          description: toApiError(err).message,
        })
      );
    }
  };

  const handleTestCallback = async (outcome: "captured" | "failed") => {
    if (!activeOrder) return;
    try {
      const res = await triggerTestCb({
        txId: activeOrder.transaction.tx_id,
        outcome,
        failure_reason: outcome === "failed" ? "Payment authorization declined in test gateway." : undefined,
      }).unwrap();
      setTestGatewayModalMethod(null);
      setActiveOrder({ transaction: res.transaction, checkout: activeOrder.checkout });
    } catch (err) {
      dispatch(
        toastAdded({
          tone: "error",
          title: "Payment update failed",
          description: toApiError(err).message,
        })
      );
    }
  };

  const handleRefreshStatus = async () => {
    if (!activeOrder) return;
    try {
      const receipt = await fetchStatus(activeOrder.transaction.tx_id).unwrap();
      setActiveOrder({
        transaction: { ...activeOrder.transaction, status: receipt.status },
        checkout: activeOrder.checkout,
      });
    } catch {
      navigate(`/payment-status/${activeOrder.transaction.tx_id}`);
    }
  };

  if (isResolving || isInstitutionStudent) {
    return <PageLoader />;
  }

  // View: Success after individual course purchase
  if (individualPurchasedSuccess) {
    return (
      <div className="mx-auto max-w-xl py-8">
        <Card bodyClassName="text-center p-8 space-y-4">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
            <Icon name="check" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Payment Verified &amp; Course Unlocked!</h1>
          <p className="text-sm text-slate-600">
            Congratulations! You have successfully purchased <strong>{individualPurchasedSuccess.course_name}</strong>.
            Access is activated for <strong>{individualPurchasedSuccess.valid_days} days</strong>.
          </p>

          <div className="p-4 bg-slate-50 rounded-xl text-xs space-y-1.5 text-left text-slate-600 border border-slate-200">
            <div className="flex justify-between">
              <span>Purchase ID:</span>
              <span className="font-mono font-medium text-slate-800">#{individualPurchasedSuccess.purchase_id}</span>
            </div>
            <div className="flex justify-between">
              <span>Amount Paid:</span>
              <span className="font-bold text-emerald-700">{inr(individualPurchasedSuccess.amount)}</span>
            </div>
            <div className="flex justify-between">
              <span>Entitlement Status:</span>
              <Badge tone="green">ACTIVE</Badge>
            </div>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
            <Button variant="primary" onClick={() => navigate("/courses/my")}>
              <Icon name="play" size={16} />
              Start Learning Now
            </Button>
            <Button variant="secondary" onClick={() => navigate("/payment-history")}>
              View Payment History
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // View: Plan order results
  if (activeOrder && (activeOrder.transaction.status === "succeeded" || activeOrder.transaction.status === "failed")) {
    return (
      <PaymentStateCard
        transaction={activeOrder.transaction}
        onRetry={() => {
          setActiveOrder(null);
          setTestGatewayModalMethod(null);
        }}
      />
    );
  }

  if (activeOrder && selectedMethod === "upi" && activeOrder.transaction.status === "pending") {
    return (
      <UpiQrCard
        transaction={activeOrder.transaction}
        checkout={activeOrder.checkout}
        busy={triggeringTest || verifying || refreshing}
        onBack={() => setActiveOrder(null)}
        onRefreshStatus={handleRefreshStatus}
        onSimulateSuccess={() => handleTestCallback("captured")}
        onSimulateFailure={() => handleTestCallback("failed")}
      />
    );
  }

  // -------------------------------------------------------------
  // RENDERING: MODEL A - Individual Student Course Checkout
  // -------------------------------------------------------------
  if (isIndividualCourseMode) {
    const courseTitle = matchedCourse?.title ?? matchedOffer?.name ?? `Course #${courseId}`;

    return (
      <div className="mx-auto max-w-4xl space-y-5">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-navy-950"
        >
          <Icon name="arrowLeft" size={16} />
          Back to Courses
        </button>

        <div className="grid gap-6 lg:grid-cols-12">
          <Card className="lg:col-span-7" bodyClassName="space-y-5 p-6">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-navy-950">Buy Course Checkout</h1>
                <Badge tone="blue">Individual Course Purchase</Badge>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Purchase this individual course directly without requiring subscription plans.
              </p>
            </div>

            {/* Course Summary Box */}
            <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-center gap-3">
                <CourseThumbnail title={courseTitle} className="h-14 w-20 shrink-0 rounded-lg" />
                <div>
                  <div className="text-sm font-bold text-navy-950">{courseTitle}</div>
                  <div className="text-xs text-slate-500">
                    Individual Student License &bull; {indivDurationDays} Days Access
                  </div>
                </div>
              </div>
              <div className="text-right text-lg font-extrabold text-navy-950">
                {inr(indivCourseTotal)}
              </div>
            </div>

            {/* Payment Method Selector */}
            <div>
              <h2 className="mb-3 text-sm font-semibold text-navy-950">Select Payment Method</h2>
              <div className="space-y-2.5">
                {ALL_METHODS.map((m) => {
                  const active = selectedMethod === m.id;
                  return (
                    <label
                      key={m.id}
                      className={cn(
                        "flex cursor-pointer items-center justify-between gap-3 rounded-xl border p-3.5 transition",
                        active
                          ? "border-blue-600 bg-blue-50/50 ring-1 ring-blue-600"
                          : "border-slate-200 hover:border-slate-300"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="radio"
                          name="payment_method"
                          checked={active}
                          onChange={() => setSelectedMethod(m.id)}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                        />
                        <div>
                          <div className="text-sm font-semibold text-navy-950">{m.title}</div>
                          <div className="text-xs text-slate-500">{m.subtitle}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {m.badges.map((b) => (
                          <span
                            key={b}
                            className="rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-bold text-slate-700"
                          >
                            {b}
                          </span>
                        ))}
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Modal/Banner for Test Gateway authorization */}
            {testGatewayModalMethod && individualActiveOrder && (
              <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4">
                <p className="text-xs font-bold uppercase tracking-wide text-blue-800">
                  Secure Gateway Authorization ({testGatewayModalMethod.toUpperCase()})
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Payment Order <span className="font-mono font-semibold">{individualActiveOrder.checkout.order_id}</span> generated for{" "}
                  <strong>{inr(indivCourseTotal)}</strong>.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    loading={confirmingPurchase}
                    onClick={() => handleIndividualTestCallback("captured")}
                  >
                    Authorize &amp; Unlock Course
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    loading={confirmingPurchase}
                    onClick={() => handleIndividualTestCallback("failed")}
                  >
                    Simulate Decline
                  </Button>
                </div>
              </div>
            )}

            {/* UPI QR Simulation */}
            {selectedMethod === "upi" && individualActiveOrder && (
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center space-y-3">
                <p className="text-xs font-semibold text-slate-700 uppercase">Scan UPI QR to Pay</p>
                <div className="w-36 h-36 bg-white border border-slate-300 mx-auto rounded-lg flex items-center justify-center p-2 shadow-inner">
                  <Icon name="creditCard" size={64} className="text-slate-800" />
                </div>
                <p className="text-xs text-slate-500">Payable: <strong>{inr(indivCourseTotal)}</strong> via UPI App</p>
                <div className="flex justify-center gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    loading={confirmingPurchase}
                    onClick={() => handleIndividualTestCallback("captured")}
                  >
                    Simulate Payment Captured
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setIndividualActiveOrder(null)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            {!individualActiveOrder && (
              <Button
                className="w-full py-3 text-base"
                variant="primary"
                disabled={buyingCourse || confirmingPurchase}
                loading={buyingCourse || confirmingPurchase}
                onClick={handleIndividualPayNow}
              >
                <Icon name="lock" size={16} />
                Buy Course Now &bull; {inr(indivCourseTotal)}
              </Button>
            )}
          </Card>

          {/* Pricing & Benefits Sidebar */}
          <Card className="lg:col-span-5" bodyClassName="space-y-4 p-6">
            <h2 className="text-base font-bold text-navy-950">Order Summary</h2>
            <dl className="space-y-2.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-600">Course Base Price</dt>
                <dd className="font-medium text-navy-950">{inr(indivCoursePrice)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-600">GST / Tax (18%)</dt>
                <dd className="font-medium text-navy-950">{inr(indivCourseTax)}</dd>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-3 text-base font-extrabold text-navy-950">
                <dt>Total Payable Amount</dt>
                <dd className="text-blue-900">{inr(indivCourseTotal)}</dd>
              </div>
            </dl>

            <div className="rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600 space-y-2">
              <p className="font-semibold text-navy-900">What&apos;s Included:</p>
              <ul className="space-y-1.5">
                <li className="flex items-center gap-1.5">
                  <Icon name="check" size={13} className="text-emerald-600" />
                  Full access to all course modules and video lessons
                </li>
                <li className="flex items-center gap-1.5">
                  <Icon name="check" size={13} className="text-emerald-600" />
                  Access to interactive coding sandbox &amp; quizzes
                </li>
                <li className="flex items-center gap-1.5">
                  <Icon name="check" size={13} className="text-emerald-600" />
                  Verifiable course completion certificate
                </li>
                <li className="flex items-center gap-1.5">
                  <Icon name="check" size={13} className="text-emerald-600" />
                  {indivDurationDays} days of continuous learning access
                </li>
              </ul>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // RENDERING: MODEL B / Subscription Plan Checkout
  // -------------------------------------------------------------
  if (!planId) {
    return (
      <EmptyState
        icon="creditCard"
        title="No course or plan selected"
        description="Choose a course to purchase or select an optional subscription plan."
        action={<Button variant="primary" onClick={() => navigate("/browse-courses")}>Browse Courses</Button>}
      />
    );
  }

  if (loadingSummary) {
    return (
      <div className="flex min-h-[320px] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (summaryError || !summary) {
    return (
      <EmptyState
        icon="alert"
        title="Checkout unavailable"
        description={toApiError(summaryError).message}
        action={<Button variant="secondary" onClick={() => navigate(-1)}>Go Back</Button>}
      />
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-navy-950"
      >
        <Icon name="arrowLeft" size={16} />
        Back to Plans
      </button>

      <div className="grid gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-7" bodyClassName="space-y-5 p-6">
          <div>
            <h1 className="text-xl font-bold text-navy-950">Payment Checkout</h1>
            <p className="mt-1 text-sm text-slate-500">Complete your subscription securely via verified gateway checkout.</p>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-center gap-3">
              <CourseThumbnail title={summary.course_title ?? summary.plan.name} className="h-14 w-20 shrink-0 rounded-lg" />
              <div>
                <div className="text-sm font-bold text-navy-950">
                  {summary.course_title ?? summary.plan.name}
                </div>
                <div className="text-xs text-slate-500">
                  {summary.plan.name} &bull; {summary.plan.billing_duration_days} Days
                  {summary.action_type === "upgrade" && summary.current_plan_name
                    ? ` (Upgrade from ${summary.current_plan_name})`
                    : ""}
                </div>
              </div>
            </div>
            <div className="text-right text-lg font-extrabold text-navy-950">
              {inr(summary.total_amount_paise)}
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-sm font-semibold text-navy-950">Payment Method</h2>
            {availableMethods.length === 0 ? (
              <Alert tone="warning" title="No payment methods enabled">
                Please contact Administrator to enable at least one payment method.
              </Alert>
            ) : (
              <div className="space-y-2.5">
                {availableMethods.map((m) => {
                  const active = selectedMethod === m.id;
                  return (
                    <label
                      key={m.id}
                      className={cn(
                        "flex cursor-pointer items-center justify-between gap-3 rounded-xl border p-3.5 transition",
                        active
                          ? "border-brand-600 bg-brand-50/50 ring-1 ring-brand-600"
                          : "border-slate-200 hover:border-slate-300"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="radio"
                          name="payment_method"
                          checked={active}
                          onChange={() => setSelectedMethod(m.id)}
                          className="h-4 w-4 text-brand-600 focus:ring-brand-500"
                        />
                        <div>
                          <div className="text-sm font-semibold text-navy-950">{m.title}</div>
                          <div className="text-xs text-slate-500">{m.subtitle}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {m.badges.map((b) => (
                          <span
                            key={b}
                            className="rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-bold text-slate-700"
                          >
                            {b}
                          </span>
                        ))}
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {testGatewayModalMethod && activeOrder && (
            <div className="rounded-xl border border-brand-200 bg-brand-50/60 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-brand-800">
                Test Gateway Authorization ({testGatewayModalMethod.toUpperCase()})
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Order <span className="font-mono font-semibold">{activeOrder.checkout.order_id}</span> created for{" "}
                <strong>{inr(activeOrder.transaction.total_amount_paise)}</strong>.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  loading={triggeringTest}
                  onClick={() => handleTestCallback("captured")}
                >
                  Authorize &amp; Complete Payment
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  loading={triggeringTest}
                  onClick={() => handleTestCallback("failed")}
                >
                  Simulate Decline
                </Button>
              </div>
            </div>
          )}

          <Button
            className="w-full py-3 text-base"
            variant="primary"
            disabled={!summary.payments_enabled || availableMethods.length === 0 || creatingOrder || verifying}
            loading={creatingOrder || verifying}
            onClick={handlePlanPayNow}
          >
            <Icon name="lock" size={16} />
            Pay {inr(summary.total_amount_paise)} Securely
          </Button>
        </Card>

        <Card className="lg:col-span-5" bodyClassName="space-y-4 p-6">
          <h2 className="text-base font-bold text-navy-950">Order Summary</h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Plan Price ({summary.plan.name})</dt>
              <dd className="font-medium text-navy-950">{inr(summary.original_amount_paise)}</dd>
            </div>
            {summary.discount_paise > 0 && (
              <div className="flex justify-between text-emerald-700">
                <dt>{summary.discount_note ?? "Upgrade Credit"}</dt>
                <dd className="font-semibold">−{inr(summary.discount_paise)}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-slate-600">Tax / GST ({summary.tax_rate_percent}%)</dt>
              <dd className="font-medium text-navy-950">{inr(summary.tax_paise)}</dd>
            </div>
            <div className="flex justify-between border-t border-slate-200 pt-3 text-base font-extrabold text-navy-950">
              <dt>Final Payable Amount</dt>
              <dd>{inr(summary.total_amount_paise)}</dd>
            </div>
          </dl>

          <div className="rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600">
            <p className="font-semibold text-navy-900">Included Benefits</p>
            <ul className="mt-2 space-y-1.5">
              {summary.plan.features.map((f, i) => (
                <li key={i} className="flex items-center gap-1.5">
                  <Icon name="check" size={13} className="text-brand-600" />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
export default CheckoutPage;
