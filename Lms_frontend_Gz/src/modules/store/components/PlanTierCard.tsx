import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { inr } from "@/modules/billing/common/format";
import type { SubscriptionPlan } from "@/modules/store/studentTypes";
import { Button, Icon } from "@/shared/ui";

function tierVisual(plan: SubscriptionPlan) {
  const code = plan.code.toLowerCase();
  if (code.includes("gold") || plan.tier_rank >= 3) {
    return {
      cardBg: "bg-gradient-to-b from-amber-50/90 via-white to-white",
      border: plan.is_recommended ? "border-brand-600 ring-2 ring-brand-600/20" : "border-amber-200",
      iconWrap: "bg-amber-100 text-amber-600",
      iconName: "award" as const,
      subtitle: plan.description || "Unlimited access & proctored exams",
    };
  }
  if (code.includes("silver") || plan.is_recommended || plan.tier_rank === 2) {
    return {
      cardBg: "bg-gradient-to-b from-brand-50/70 via-white to-white",
      border: plan.is_recommended ? "border-brand-600 ring-2 ring-brand-500/20 shadow-md" : "border-brand-200",
      iconWrap: "bg-brand-100 text-brand-600",
      iconName: "sparkles" as const,
      subtitle: plan.description || "Unlock more learning & tests",
    };
  }
  return {
    cardBg: "bg-gradient-to-b from-slate-50/90 via-white to-white",
    border: plan.is_recommended ? "border-brand-600 ring-2 ring-brand-500/20" : "border-slate-200",
    iconWrap: "bg-sky-100 text-sky-600",
    iconName: "layers" as const,
    subtitle: plan.description || "Essential learning access",
  };
}

export function PlanTierCard({
  plan,
  currentPlanCode,
  onSelect,
  selectLabel = "Select Plan",
  loading,
  disabled,
  footerActions,
}: {
  plan: SubscriptionPlan;
  currentPlanCode?: string | null;
  onSelect?: (plan: SubscriptionPlan) => void;
  selectLabel?: string;
  loading?: boolean;
  disabled?: boolean;
  footerActions?: ReactNode;
}) {
  const vis = tierVisual(plan);
  const isCurrent = Boolean(currentPlanCode && currentPlanCode.toLowerCase() === plan.code.toLowerCase());

  return (
    <div
      className={cn(
        "relative flex flex-col justify-between rounded-2xl border p-5 transition hover:shadow-card",
        vis.cardBg,
        vis.border,
        !plan.is_active && "opacity-60",
      )}
    >
      {plan.is_recommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center rounded-full bg-brand-600 px-3 py-0.5 text-xs font-semibold text-white shadow-sm">
            Most Popular
          </span>
        </div>
      )}

      <div>
        <div className="flex items-start gap-3 pt-1">
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", vis.iconWrap)}>
            <Icon name={vis.iconName} size={20} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-navy-950">{plan.name}</h3>
              {!plan.is_active && (
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">Inactive</span>
              )}
              {isCurrent && (
                <span className="rounded bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">Active</span>
              )}
            </div>
            <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{vis.subtitle}</p>
          </div>
        </div>

        <div className="mt-4 flex items-baseline gap-1 border-b border-slate-100 pb-4">
          <span className="text-2xl font-extrabold tracking-tight text-navy-950">{inr(plan.price_paise)}</span>
          <span className="text-xs font-medium text-slate-500">/ {plan.billing_label || `${plan.billing_duration_days}d`}</span>
        </div>

        <ul className="mt-4 space-y-2.5">
          {plan.features.map((feat, idx) => (
            <li key={`${plan.plan_id}-f-${idx}`} className="flex items-start gap-2 text-xs text-slate-700">
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
                <Icon name="check" size={11} />
              </span>
              <span>{feat}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-5 pt-2">
        {footerActions ? (
          footerActions
        ) : (
          <Button
            className="w-full"
            variant={plan.is_recommended ? "primary" : "secondary"}
            loading={loading}
            disabled={disabled || isCurrent || !plan.is_active}
            onClick={() => onSelect?.(plan)}
          >
            {isCurrent ? "Current Plan" : selectLabel}
          </Button>
        )}
      </div>
    </div>
  );
}
