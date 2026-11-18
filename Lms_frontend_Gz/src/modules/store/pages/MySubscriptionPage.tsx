import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { toApiError } from "@/core/lib/apiError";
import { inr } from "@/modules/billing/common/format";
import {
  useGetStudentAccountContextQuery,
  useGetStudentSubscriptionOverviewQuery,
} from "@/modules/store/api/studentSubscriptionsApi";
import { PlanTierCard } from "@/modules/store/components/PlanTierCard";
import type { StudentSubscriptionRecord } from "@/modules/store/studentTypes";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import { Alert, Badge, Button, Card, EmptyState, Icon, Modal, PageHeader, PageLoader, Spinner } from "@/shared/ui";

const STATUS_TONE: Record<StudentSubscriptionRecord["status"], "green" | "amber" | "red" | "gray"> = {
  active: "green",
  pending: "amber",
  expired: "red",
  superseded: "gray",
  cancelled: "gray",
  failed: "red",
};

export function MySubscriptionPage() {
  const navigate = useNavigate();
  const { isResolving, isInstitutionStudent } = useStudentType();

  useEffect(() => {
    if (!isResolving && isInstitutionStudent) {
      navigate("/courses/my", { replace: true });
    }
  }, [isResolving, isInstitutionStudent, navigate]);

  const { data: accountCtx } = useGetStudentAccountContextQuery(undefined, { skip: isInstitutionStudent });
  const { data, error, isLoading, isError, refetch } = useGetStudentSubscriptionOverviewQuery(undefined, { skip: isInstitutionStudent });
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const mustRequest = accountCtx?.must_request_payment ?? false;

  if (isResolving || isInstitutionStudent) {
    return <PageLoader />;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[300px] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <Alert tone="error" title="Could not load subscription details">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span>{error ? toApiError(error).message : "Please refresh or try again later."}</span>
          <Button size="sm" variant="secondary" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      </Alert>
    );
  }

  const active = data.active_subscription;
  const upgrades = data.available_upgrades;

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Subscription"
        description="View your active plan, validity, unlocked courses, and upgrade or renew options."
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate("/payment-history")}>
            <Icon name="fileText" size={16} />
            Payment History
          </Button>
        }
      />

      {active ? (
        <div className="grid gap-6 lg:grid-cols-12">
          {/* Active Plan Card (Reference Image 1 Bottom Right) */}
          <Card className="lg:col-span-7" bodyClassName="space-y-5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3.5">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-600">
                  <Icon name="award" size={24} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-navy-950">{active.plan_name}</h2>
                    <Badge tone="green">Active</Badge>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-500">
                    Valid Until: <strong className="text-navy-900">{formatDate(active.ends_at)}</strong>
                  </p>
                </div>
              </div>

              {!mustRequest && (
                <div className="flex flex-wrap gap-2">
                  {upgrades.length > 0 && (
                    <Button variant="primary" onClick={() => setUpgradeOpen(true)}>
                      Upgrade Plan
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    onClick={() => navigate(`/checkout?planId=${encodeURIComponent(active.plan_id)}&action=renew`)}
                  >
                    Renew Plan
                  </Button>
                </div>
              )}
            </div>

            <div className="border-t border-slate-100 pt-4">
              <h3 className="text-sm font-semibold text-navy-950">Subscription Features</h3>
              <ul className="mt-3 grid gap-2.5 sm:grid-cols-2">
                {active.features.map((feat, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm text-slate-700">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
                      <Icon name="check" size={12} />
                    </span>
                    {feat}
                  </li>
                ))}
              </ul>
            </div>

            <div className="grid gap-3 rounded-xl bg-slate-50 p-4 text-xs sm:grid-cols-3">
              <div>
                <div className="text-slate-500">Assessment Access</div>
                <div className="mt-1 font-semibold text-navy-950">
                  {[
                    active.assessment_access.chapter_tests && "Chapter Tests",
                    active.assessment_access.module_tests && "Module Tests",
                    active.assessment_access.final_exam && "Final Exam",
                  ]
                    .filter(Boolean)
                    .join(", ") || "Standard"}
                </div>
              </div>
              <div>
                <div className="text-slate-500">Certificate Tier</div>
                <div className="mt-1 font-semibold capitalize text-navy-950">{active.certificate_level} Certificate</div>
              </div>
              <div>
                <div className="text-slate-500">Course Quota</div>
                <div className="mt-1 font-semibold text-navy-950">
                  {active.courses.length} / {active.max_courses ?? "Unlimited"} used
                </div>
              </div>
            </div>
          </Card>

          {/* Accessible Courses & Latest Payment */}
          <Card className="lg:col-span-5" bodyClassName="space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-navy-950">Unlocked Courses</h3>
              <Button size="sm" variant="ghost" onClick={() => navigate("/browse-courses")}>
                Browse More
              </Button>
            </div>

            {active.courses.length === 0 ? (
              <p className="text-sm text-slate-500">
                No specific courses unlocked yet. Visit Browse Courses to unlock any approved course under your plan.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {active.courses.map((c) => (
                  <li
                    key={c.course_id}
                    className="flex items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50/70 px-3.5 py-2.5"
                  >
                    <span className="truncate text-sm font-medium text-navy-950">{c.course_title}</span>
                    <Button size="sm" variant="secondary" onClick={() => navigate("/courses/my")}>
                      Open
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            {data.latest_payment && (
              <div className="border-t border-slate-100 pt-4 text-xs">
                <div className="font-semibold text-navy-950">Latest Payment</div>
                <div className="mt-1.5 flex justify-between text-slate-600">
                  <span>{data.latest_payment.transaction_ref}</span>
                  <span className="font-semibold text-navy-950">{inr(data.latest_payment.total_amount_paise)}</span>
                </div>
                <div className="mt-0.5 text-slate-400">
                  Method: {data.latest_payment.payment_method.toUpperCase()} &bull; {formatDate(data.latest_payment.created_at)}
                </div>
              </div>
            )}
          </Card>
        </div>
      ) : (
        <EmptyState
          icon="award"
          title="No active subscription yet"
          description="Browse approved courses and select Base, Silver, or Gold Plan to unlock content, tests, and certificates."
          action={
            <Button variant="primary" onClick={() => navigate("/browse-courses")}>
              Browse Courses &amp; Plans
            </Button>
          }
        />
      )}

      {/* Subscription History */}
      {data.history.length > 0 && (
        <Card title="Subscription History" bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-100 bg-slate-50/60 text-xs font-semibold text-slate-500">
                <tr>
                  <th className="px-4 py-3">Plan</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Valid Until</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.history.map((sub) => (
                  <tr key={sub.subscription_id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-medium text-navy-950">{sub.plan_name}</td>
                    <td className="px-4 py-3 text-slate-700">{inr(sub.price_paise)}</td>
                    <td className="px-4 py-3 text-slate-500">{sub.starts_at ? formatDate(sub.starts_at) : "—"}</td>
                    <td className="px-4 py-3 text-slate-500">{sub.ends_at ? formatDate(sub.ends_at) : "—"}</td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[sub.status] ?? "slate"}>{sub.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {sub.status === "expired" && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => navigate(`/checkout?planId=${encodeURIComponent(sub.plan_id)}&action=renew`)}
                        >
                          Renew
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal
        open={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        size="xl"
        title="Upgrade Subscription Plan"
        description="Upgrade to a higher tier. Your upgrade credit is applied automatically at checkout."
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {upgrades.map((plan) => (
            <PlanTierCard
              key={plan.plan_id}
              plan={plan}
              currentPlanCode={active?.plan_code}
              selectLabel={`Upgrade to ${plan.name}`}
              onSelect={(p) => {
                setUpgradeOpen(false);
                navigate(`/checkout?planId=${encodeURIComponent(p.plan_id)}&action=upgrade`);
              }}
            />
          ))}
        </div>
      </Modal>
    </div>
  );
}
