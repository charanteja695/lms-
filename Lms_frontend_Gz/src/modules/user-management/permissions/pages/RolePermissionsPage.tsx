import { useMemo, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { ROLE_LABELS } from "@/modules/user-management/common/labels";
import type { Role } from "@/modules/user-management/common/types";
import { useGetPermissionCatalogQuery, useGetRolePermissionsQuery, useSetRolePermissionsMutation, type PermissionChanges } from "@/modules/user-management/permissions/api/permissionAdminApi";
import { groupPages, plural, viewKey } from "@/modules/user-management/permissions/components/matrix/matrixModel";
import { MatrixTable } from "@/modules/user-management/permissions/components/matrix/MatrixTable";
import { ReviewChangesDialog } from "@/modules/user-management/permissions/components/ReviewChangesDialog";
import { Button, Card, EmptyState, PageHeader, PageLoader, SearchInput, Tabs } from "@/shared/ui";

/** Each role's matrix: tick what everyone in it may do on every page. One person's own changes are on their page. */
export function RolePermissionsPage() {
  const notify = useNotify();
  const { data: catalog, isLoading: loadingCatalog } = useGetPermissionCatalogQuery();
  const { data: roles = [], isLoading } = useGetRolePermissionsQuery();
  const [save, { isLoading: saving }] = useSetRolePermissionsMutation();
  const [role, setRole] = useState("staff");
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState<PermissionChanges>({});
  const [review, setReview] = useState<"save" | "reset" | null>(null);

  const row = roles.find((r) => r.role === role);
  const cells = useMemo(() => new Map(row?.permissions.map((c) => [c.key, c]) ?? []), [row]);
  const actionsByKey = useMemo(() => new Map(catalog?.pages.flatMap((p) => p.actions.map((a) => [a.key, { page: p, action: a }] as const)) ?? []), [catalog]);

  if (isLoading || loadingCatalog) return <PageLoader />;
  if (!catalog || !row) return <EmptyState icon="key" title="No roles to show" />;

  const matrixRoles = roles.filter((r) => catalog.matrix_roles.includes(r.role));
  const groups = groupPages(catalog.pages, role, search);
  const roleLabel = ROLE_LABELS[role as Role] ?? role;
  const count = Object.keys(pending).length;
  const changedKeys = row.permissions.filter((c) => c.changed).map((c) => c.key);

  const catalogDefault = (key: string) => actionsByKey.get(key)?.action.default_roles.includes(role) ?? false;
  const allowed = (key: string) => (key in pending ? (pending[key] ?? catalogDefault(key)) : (cells.get(key)?.allowed ?? false));
  const toggle = (key: string, value: boolean) => setPending((prev) => {
    const next = { ...prev };
    if (value === cells.get(key)?.allowed) delete next[key];
    else next[key] = value;
    return next;
  });
  const switchRole = (next: string) => (count === 0 ? setRole(next) : notify.info(`Save or discard the changes to ${roleLabel} first`));
  const submit = (changes: PermissionChanges, done: string) =>
    void save({ role, changes }).unwrap().then(() => { setPending({}); setReview(null); notify.success(done); }, notify.apiError);
  const resetAll = Object.fromEntries(changedKeys.map((k) => [k, null])) as PermissionChanges;

  return (
    <>
      <PageHeader
        title="Roles & permissions"
        description="Tick what each role may do on every page. Unticking View hides the page from that role's menu. To change one person only, open their page under Users."
      />
      <div className="mb-4 overflow-x-auto">
        <Tabs variant="pills" tabs={matrixRoles.map((r) => ({ value: r.role, label: ROLE_LABELS[r.role as Role] ?? r.role }))} value={role} onChange={switchRole} />
      </div>
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
          <SearchInput value={search} onChange={setSearch} placeholder="Search pages" className="w-full sm:w-72" />
          <p className="text-xs text-slate-500 sm:ml-auto">{changedKeys.length ? `${plural(changedKeys.length, "box")} differ from the default` : "Using the default"}</p>
          {changedKeys.length > 0 && <Button size="sm" variant="ghost" onClick={() => setReview("reset")}>Reset {roleLabel} to default</Button>}
        </div>
        {groups.length === 0 ? (
          <EmptyState icon="search" title="No pages match" description="Try another word." />
        ) : (
          <MatrixTable
            groups={groups}
            actions={catalog.actions}
            rowChanged={(page) => page.actions.some((a) => a.key in pending || cells.get(a.key)?.changed)}
            renderCell={(page, action) => {
              const isView = action.action === "view";
              const blocked = !isView && !allowed(viewKey(page));
              return (
                <span className="relative inline-flex">
                  <input
                    type="checkbox"
                    className="h-[18px] w-[18px] cursor-pointer rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label={`${roleLabel}: ${page.label} · ${action.action}`}
                    title={blocked ? "Needs View" : action.meaning}
                    checked={allowed(action.key)}
                    disabled={blocked}
                    onChange={(e) => toggle(action.key, e.target.checked)}
                  />
                  {action.key in pending && <span className="absolute -right-1.5 -top-1.5 h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />}
                </span>
              );
            }}
          />
        )}
        <p className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">A dot marks a box changed since the last save. “—” means the page has no such action. Every other action needs View.</p>
      </Card>

      {count > 0 && (
        <div className="sticky bottom-4 z-20 mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-brand-200 bg-white/95 px-4 py-3 shadow-card backdrop-blur">
          <p className="text-sm font-medium text-slate-800">{plural(count, "change")} to {roleLabel}</p>
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={() => setPending({})}>Discard</Button>
            <Button onClick={() => setReview("save")}>Review & save</Button>
          </div>
        </div>
      )}

      <ReviewChangesDialog
        open={review !== null}
        title={review === "reset" ? `Reset ${roleLabel} to the default?` : `Save ${plural(count, "change")} for ${roleLabel}?`}
        description={`Everyone with this role gets ${review === "reset" ? "the defaults" : "them"} within seconds, without signing out. People with their own changes keep them.`}
        changes={review === "reset" ? Object.fromEntries(changedKeys.map((k) => [k, catalogDefault(k)])) : Object.fromEntries(Object.keys(pending).map((k) => [k, allowed(k)]))}
        describe={(key) => actionsByKey.get(key)}
        loading={saving}
        confirmLabel={review === "reset" ? "Reset" : "Save"}
        onCancel={() => setReview(null)}
        onConfirm={() => (review === "reset" ? submit(resetAll, `${roleLabel} is back to the default`) : submit(pending, "Role permissions saved"))}
      />
    </>
  );
}
