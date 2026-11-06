import { formatDateTime } from "@/core/lib/format";
import { formatCount, formatUsd } from "@/modules/ai-settings/common/money";
import type { CallLog } from "@/modules/ai-settings/common/types";
import { OrganizationNameCell } from "@/modules/user-management/common/components/OrganizationNameCell";
import { Badge, DescriptionList, Modal } from "@/shared/ui";

/** One AI call: who asked, what was sent and received (personal data already removed), and what it cost. */
export function LogDetailDialog({ log, onClose }: { log: CallLog; onClose: () => void }) {
  return (
    <Modal open onClose={onClose} size="lg" title={log.prompt_key ?? log.capability} description={formatDateTime(log.created_at)}>
      <div className="space-y-5">
        <DescriptionList
          items={[
            { label: "Organisation", value: <OrganizationNameCell organizationId={log.organization_id} /> },
            { label: "Service", value: log.service },
            { label: "Outcome", value: <Badge tone={log.status === "ok" ? "green" : log.status === "blocked" ? "amber" : "red"}>{log.status}{log.error_code ? ` · ${log.error_code}` : ""}</Badge> },
            { label: "Model", value: log.model ? `${log.provider} · ${log.model}` : "—" },
            { label: "Tokens", value: `${formatCount(log.prompt_tokens)} in · ${formatCount(log.completion_tokens)} out` },
            { label: "Cost · time", value: `${formatUsd(log.cost_cents)} · ${log.latency_ms.toLocaleString()} ms` },
            ...(log.guardrail_flags.length ? [{ label: "Safety flags", value: log.guardrail_flags.join(", ") }] : []),
          ]}
        />
        <section>
          <h3 className="mb-2 text-sm font-bold text-navy-950">Sent (personal data removed)</h3>
          <pre className="max-h-56 overflow-auto rounded-xl bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-800 ring-1 ring-slate-200/70">{JSON.stringify(log.request_redacted, null, 2)}</pre>
        </section>
        <section>
          <h3 className="mb-2 text-sm font-bold text-navy-950">Reply (start)</h3>
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm text-slate-800 ring-1 ring-slate-200/70">{log.response_preview || "—"}</pre>
        </section>
      </div>
    </Modal>
  );
}
