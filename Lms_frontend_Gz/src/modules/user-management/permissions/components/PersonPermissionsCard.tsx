import { useMemo, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { ROLE_LABELS } from "@/modules/user-management/common/labels";
import type { Role } from "@/modules/user-management/common/types";
import { useGetPermissionCatalogQuery, useGetPersonPermissionsQuery, useSetPersonPermissionsMutation, type PermissionChanges } from "@/modules/user-management/permissions/api/permissionAdminApi";
import { groupPages, plural } from "@/modules/user-management/permissions/components/matrix/matrixModel";
import { MatrixTable } from "@/modules/user-management/permissions/components/matrix/MatrixTable";
import { PersonBox, PersonLegend, stateOf } from "@/modules/user-management/permissions/components/person/PersonBox";
import { PlatformAreas } from "@/modules/user-management/permissions/components/person/PlatformAreas";
import { Button, Card, Field, Spinner, Textarea } from "@/shared/ui";

/** One person's matrix: start from their role, then allow or remove single actions for them alone (super admin only). */
export function PersonPermissionsCard({ userId, role, name }: { userId: string; role: string; name: string }) {
  const notify = useNotify();
  const { data: catalog } = useGetPermissionCatalogQuery();
  const { data: view, isLoading } = useGetPersonPermissionsQuery(userId);
  const [save, { isLoading: saving }] = useSetPersonPermissionsMutation();
  const [pending, setPending] = useState<PermissionChanges>({});
  const [reason, setReason] = useState("");
  const cells = useMemo(() => new Map(view?.permissions.map((c) => [c.key, c]) ?? []), [view]);

  if (isLoading || !catalog) return <Card title="Permissions"><Spinner /></Card>;
  if (!view) return null;
  if (!view.editable) return <Card title="Permissions"><p className="text-sm text-slate-600">A super admin always holds every permission.</p></Card>;

  const roleLabel = ROLE_LABELS[role as Role] ?? role;
  const onMatrix = catalog.matrix_roles.includes(role);
  const groups = onMatrix ? groupPages(catalog.pages, role, "") : [];
  const override = (key: string): boolean | null => (key in pending ? (pending[key] ?? null) : (cells.get(key)?.override ?? null));
  const set = (key: string, value: boolean | null) => setPending((prev) => {
    const next = { ...prev };
    if (value === (cells.get(key)?.override ?? null)) delete next[key];
    else next[key] = value;
    return next;
  });
  // click: go against the role for this person; click again: follow the role
  const flip = (key: string) => set(key, override(key) === null ? !cells.get(key)?.from_role : null);
  const scopeKeys = new Set(catalog.permissions.filter((p) => p.audience === "platform").map((p) => p.key));
  const own = view.permissions.filter((c) => !scopeKeys.has(c.key) && c.override !== null);
  const count = Object.keys(pending).length;
  const resetRow = (keys: string[]) => keys.forEach((k) => set(k, null));

  return (
    <Card
      title="Permissions"
      description={`Start from the ${roleLabel} role, then allow or remove single actions for ${name} alone. Applies within seconds; they stay signed in.`}
      actions={own.length > 0 && <Button size="sm" variant="ghost" onClick={() => resetRow(own.map((c) => c.key))}>Reset to {roleLabel} role</Button>}
      bodyClassName="p-0"
    >
      {role === "admin" && <PlatformAreas catalog={catalog} cells={cells} pending={pending} onChange={set} />}
      {onMatrix && (
        <>
          <PersonLegend name={name} />
          <MatrixTable
            groups={groups}
            actions={catalog.actions}
            rowChanged={(page) => page.actions.some((a) => override(a.key) !== null)}
            renderCell={(page, action) => (
              <PersonBox
                state={stateOf(cells.get(action.key)?.from_role ?? false, override(action.key))}
                unsaved={action.key in pending}
                label={`${page.label} · ${action.action}: ${action.meaning}`}
                onClick={() => flip(action.key)}
              />
            )}
            renderRowEnd={(page) => page.actions.some((a) => override(a.key) !== null) && (
              <Button size="sm" variant="ghost" onClick={() => resetRow(page.actions.map((a) => a.key))}>Reset</Button>
            )}
          />
        </>
      )}
      {count > 0 && (
        <div className="space-y-3 border-t border-slate-100 p-4">
          <Field label="Reason" hint="Kept in the audit log.">{(f) => <Textarea {...f} rows={2} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <p className="mr-auto text-sm text-slate-600">{plural(count, "unsaved change")} for {name}</p>
            <Button variant="ghost" onClick={() => setPending({})}>Discard</Button>
            <Button loading={saving} onClick={() => void save({ userId, changes: pending, reason: reason.trim() || undefined }).unwrap().then(() => { setPending({}); setReason(""); notify.success("Permissions saved"); }, notify.apiError)}>
              Save for {name}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
