import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { cn } from "@/core/lib/cn";
import type { PromptStatus, PromptVersion } from "@/modules/ai-settings/common/types";
import { useChangeVersionStatusMutation } from "@/modules/ai-settings/prompts/api/promptsApi";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { Badge, Button, type BadgeTone } from "@/shared/ui";

const STATUS: Record<PromptStatus, { label: string; tone: BadgeTone }> = {
  active: { label: "In use", tone: "green" },
  draft: { label: "Draft", tone: "amber" },
  retired: { label: "Retired", tone: "gray" },
};

/** One version: its text, the values it expects, and what can be done with it next. */
export function VersionCard({ promptKey, version, onCopy }: { promptKey: string; version: PromptVersion; onCopy: (template: string) => void }) {
  const notify = useNotify();
  const { user } = useAuth();
  const [change, { isLoading }] = useChangeVersionStatusMutation();
  const { isSuperAdmin } = useCan();
  const mine = user?.user_id === version.created_by;
  const needsOther = mine && !isSuperAdmin; // the super admin runs AI alone, so may put their own version in use
  const act = (action: "activate" | "retire") =>
    void change({ key: promptKey, version: version.version, action }).unwrap().then(() => notify.success(action === "activate" ? "Now in use" : "Retired"), notify.apiError);

  return (
    <article className={cn("rounded-2xl border bg-white p-5 shadow-card", version.status === "active" ? "border-brand-200 ring-1 ring-brand-100" : "border-slate-200/80")}>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <h3 className="text-[15px] font-bold text-navy-950">Version {version.version}</h3>
          <Badge tone={STATUS[version.status].tone}>{STATUS[version.status].label}</Badge>
        </div>
        <p className="text-xs text-slate-500">Written {formatDateTime(version.created_at)}{mine ? " by you" : ""}</p>
      </header>
      <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-mono text-[13px] leading-relaxed text-slate-800 ring-1 ring-slate-200/70">{version.template}</pre>
      {version.variables.length > 0 && (
        <p className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">Expects {version.variables.map((v) => <Badge key={v} tone="indigo">{v}</Badge>)}</p>
      )}
      <footer className="mt-4 flex flex-wrap items-center justify-end gap-2">
        {version.status === "draft" && needsOther && <p className="mr-auto text-xs text-slate-500">You wrote this draft, so another AI manager activates it.</p>}
        <Button variant="ghost" size="sm" icon="edit" onClick={() => onCopy(version.template)}>Start a new version from this</Button>
        {version.status !== "retired" && <Button variant="secondary" size="sm" loading={isLoading} onClick={() => act("retire")}>Retire</Button>}
        {version.status === "draft" && <Button size="sm" icon="check" disabled={needsOther} loading={isLoading} onClick={() => act("activate")}>Put in use</Button>}
      </footer>
    </article>
  );
}
