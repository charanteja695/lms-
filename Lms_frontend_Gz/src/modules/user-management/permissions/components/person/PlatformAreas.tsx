import type { PermissionCatalog, PermissionChanges, PersonCell } from "@/modules/user-management/permissions/api/permissionAdminApi";
import { Checkbox } from "@/shared/ui";

/** An admin's platform areas (their scopes): theirs alone, so a plain on/off per area. */
export function PlatformAreas({ catalog, cells, pending, onChange }: {
  catalog: PermissionCatalog;
  cells: Map<string, PersonCell>;
  pending: PermissionChanges;
  onChange: (key: string, value: boolean) => void;
}) {
  const areas = catalog.permissions.filter((p) => p.audience === "platform" && cells.has(p.key));
  if (areas.length === 0) return null;
  return (
    <div className="border-b border-slate-100 px-4 py-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Platform areas</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {areas.map((p) => (
          <Checkbox
            key={p.key}
            label={p.label}
            description={p.description}
            checked={p.key in pending ? Boolean(pending[p.key]) : Boolean(cells.get(p.key)?.override)}
            onChange={(e) => onChange(p.key, e.target.checked)}
          />
        ))}
      </div>
    </div>
  );
}
