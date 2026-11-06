import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import type { Capability, RouteEntry } from "@/modules/ai-settings/common/types";
import { useSetModelRouteMutation } from "@/modules/ai-settings/models/api/modelsApi";
import { Badge, Button, Card, Input } from "@/shared/ui";

const MAX = 5; // ai-gateway accepts up to five providers per capability

/** One capability's fallback order: reorder, add or remove providers, then save. Nothing changes until "Save order". */
export function RouteEditor({ capability, title, description, initial }: { capability: Capability; title: string; description: string; initial: RouteEntry[] }) {
  const notify = useNotify();
  const [save, { isLoading }] = useSetModelRouteMutation();
  const [rows, setRows] = useState<RouteEntry[]>(initial);
  const changed = JSON.stringify(rows) !== JSON.stringify(initial);
  const valid = rows.length > 0 && rows.every((r) => r.provider.trim() && r.model.trim());
  const update = (i: number, patch: Partial<RouteEntry>) => setRows((all) => all.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const move = (i: number, by: number) => setRows((all) => { const next = [...all]; const [row] = next.splice(i, 1); next.splice(i + by, 0, row!); return next; });

  return (
    <Card title={title} description={description} actions={changed && <Badge tone="amber">Unsaved changes</Badge>}>
      <ol className="space-y-3">
        {rows.map((row, i) => (
          <li key={i} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200/80 bg-slate-50/50 p-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-sm font-bold text-navy-900 ring-1 ring-slate-200">{i + 1}</span>
            <Input aria-label={`Provider ${i + 1}`} className="min-w-32 flex-1" value={row.provider} placeholder="anthropic" onChange={(e) => update(i, { provider: e.target.value })} />
            <Input aria-label={`Model ${i + 1}`} className="min-w-44 flex-[2]" value={row.model} placeholder="claude-sonnet-5-5" onChange={(e) => update(i, { model: e.target.value })} />
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" icon="arrowUp" aria-label="Try earlier" disabled={i === 0} onClick={() => move(i, -1)} />
              <Button variant="ghost" size="sm" icon="arrowDown" aria-label="Try later" disabled={i === rows.length - 1} onClick={() => move(i, 1)} />
              <Button variant="ghost" size="sm" icon="trash" aria-label="Remove" disabled={rows.length === 1} onClick={() => setRows((all) => all.filter((_, j) => j !== i))} />
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Button variant="secondary" size="sm" icon="plus" disabled={rows.length >= MAX} onClick={() => setRows((all) => [...all, { provider: "", model: "" }])}>
          Add a fallback
        </Button>
        <div className="flex gap-2">
          {changed && <Button variant="ghost" onClick={() => setRows(initial)}>Undo</Button>}
          <Button disabled={!changed || !valid} loading={isLoading} onClick={() => void save({ capability, providers: rows }).unwrap().then(() => notify.success("Order saved"), notify.apiError)}>
            Save order
          </Button>
        </div>
      </div>
    </Card>
  );
}
