import type { MatrixPage, PageAction } from "@/modules/user-management/permissions/api/permissionAdminApi";
import { Badge, Button, Modal } from "@/shared/ui";

/** Lists what a save will do, cell by cell ("Students · Delete — allowed"), before it is applied. */
export function ReviewChangesDialog({ open, title, description, changes, describe, loading, confirmLabel, onConfirm, onCancel }: {
  open: boolean;
  title: string;
  description: string;
  /** cell key → the result after saving (allowed or not) */
  changes: Record<string, boolean>;
  describe: (key: string) => { page: MatrixPage; action: PageAction } | undefined;
  loading: boolean;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const rows = Object.entries(changes).map(([key, allowed]) => ({ key, allowed, found: describe(key) }));
  return (
    <Modal
      open={open}
      onClose={loading ? () => undefined : onCancel}
      title={title}
      description={description}
      footer={<><Button variant="secondary" onClick={onCancel} disabled={loading}>Back</Button><Button loading={loading} onClick={onConfirm}>{confirmLabel}</Button></>}
    >
      <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
        {rows.map(({ key, allowed, found }) => (
          <li key={key} className="flex items-center justify-between gap-3 py-2 text-sm">
            <span className="min-w-0">
              <span className="font-medium text-slate-800">{found ? `${found.page.label} · ${found.action.action.charAt(0).toUpperCase()}${found.action.action.slice(1)}` : key}</span>
              {found && <span className="block text-xs text-slate-500">{found.action.meaning}</span>}
            </span>
            {allowed ? <Badge tone="green">Allowed</Badge> : <Badge tone="red">Removed</Badge>}
          </li>
        ))}
      </ul>
    </Modal>
  );
}
