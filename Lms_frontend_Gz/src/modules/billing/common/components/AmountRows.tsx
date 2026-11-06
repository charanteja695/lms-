import { cn } from "@/core/lib/cn";
import { inr } from "@/modules/billing/common/format";

/** A right-aligned money summary (subtotal … total); rows with a zero amount and `optional` are left out. */
export function AmountRows({ rows }: { rows: { label: string; amount: number; optional?: boolean; strong?: boolean; negative?: boolean }[] }) {
  return (
    <dl className="ml-auto max-w-sm space-y-1.5 text-sm">
      {rows.filter((r) => !(r.optional && r.amount === 0)).map((r) => (
        <div key={r.label} className={cn("flex justify-between gap-6", r.strong && "border-t border-slate-200 pt-1.5 font-semibold text-slate-900")}>
          <dt className={r.strong ? undefined : "text-slate-600"}>{r.label}</dt>
          <dd className="tabular-nums">{r.negative ? `− ${inr(r.amount)}` : inr(r.amount)}</dd>
        </div>
      ))}
    </dl>
  );
}
