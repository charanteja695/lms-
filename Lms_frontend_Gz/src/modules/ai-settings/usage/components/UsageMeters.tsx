import { cn } from "@/core/lib/cn";
import { formatCount, formatUsd } from "@/modules/ai-settings/common/money";
import type { Usage } from "@/modules/ai-settings/common/types";
import { Icon, type IconName } from "@/shared/ui";

function Meter({ icon, label, used, limit, format }: { icon: IconName; label: string; used: number; limit: number; format: (n: number) => string }) {
  const share = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  // green while comfortable, the logo orange near the limit, red at it
  const tone = share >= 100 ? "bg-red-500" : share >= 80 ? "bg-accent-500" : "bg-brand-500";
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-50 to-brand-100 text-brand-700 ring-1 ring-brand-100">
          <Icon name={icon} size={20} />
        </span>
        <p className="text-sm font-medium text-slate-500">{label}</p>
      </div>
      <p className="mt-4 text-[26px] font-bold leading-none tabular-nums text-navy-950">{format(used)}</p>
      <p className="mt-1 text-sm text-slate-500">of {format(limit)} this month</p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label={`${label}: ${share}% used`} aria-valuenow={share} aria-valuemin={0} aria-valuemax={100}>
        <div className={cn("h-full rounded-full transition-[width] duration-500", tone)} style={{ width: `${share}%` }} />
      </div>
      <p className="mt-2 text-xs font-semibold text-slate-500">{share}% used</p>
    </div>
  );
}

/** This month's requests, tokens and spend against the organisation's limits. */
export function UsageMeters({ usage }: { usage: Usage }) {
  const tokens = usage.prompt_tokens_used + usage.completion_tokens_used;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Meter icon="sparkles" label="Requests" used={usage.requests_used} limit={usage.request_limit} format={formatCount} />
      <Meter icon="fileText" label="Tokens" used={tokens} limit={usage.token_limit} format={formatCount} />
      <Meter icon="chart" label="Spend" used={usage.cost_cents_used} limit={usage.budget_cents} format={formatUsd} />
    </div>
  );
}
