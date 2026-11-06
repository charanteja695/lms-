import { ADMIN_SCOPE_LABELS } from "@/modules/user-management/common/labels";
import type { AdminScope } from "@/modules/user-management/common/types";
import { Badge, Card } from "@/shared/ui";

/** What this admin is responsible for across the platform. */
export function ScopesCard({ scopes }: { scopes: AdminScope[] }) {
  return (
    <Card title="Responsibilities">
      <ul className="space-y-2 text-sm">
        {scopes.map((scope) => (
          <li key={scope} className="flex items-center justify-between gap-3">
            <span className="text-slate-700">{ADMIN_SCOPE_LABELS[scope]}</span>
            <Badge>{scope}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}
