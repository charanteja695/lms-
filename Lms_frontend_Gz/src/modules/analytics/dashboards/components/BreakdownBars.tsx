import { Card } from "@/shared/ui";

const humanise = (key: string) => (key === "none" ? "Not set" : key.replace(/[_.]/g, " ").replace(/^\w/, (c) => c.toUpperCase()));

/** A name -> count map as one-hue horizontal bars, largest first. Labels and values are text, so colour carries nothing alone. */
export function BreakdownBars({ title, counts }: { title: string; counts: Record<string, number> }) {
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map(([, n]) => n));
  const total = rows.reduce((sum, [, n]) => sum + n, 0);

  return (
    <Card title={title} description={rows.length ? `${total.toLocaleString()} in total` : undefined}>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">Nothing in this period.</p>
      ) : (
        <ul className="space-y-2.5">
          {rows.map(([name, n]) => (
            <li key={name} className="group" title={`${humanise(name)}: ${n.toLocaleString()} (${Math.round((n / total) * 100)}%)`}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-slate-700">{humanise(name)}</span>
                <span className="font-medium tabular-nums text-slate-900">{n.toLocaleString()}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-brand-600 transition-colors group-hover:bg-brand-700" style={{ width: `${Math.max(2, (n / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
