import { Button, Icon } from "@/shared/ui";

export interface RowActionHandlers {
  onEdit?: () => void;
  onRevoke?: () => void;
  onRestore?: () => void;
  onDelete?: () => void;
}

/**
 * A row's buttons: Edit, Revoke access / Restore access, Delete. A handler is passed only when the server allows
 * that action on this record (`allowed_actions`), so a missing button means "not allowed".
 */
export function RowActions({ name, onEdit, onRevoke, onRestore, onDelete }: RowActionHandlers & { name: string }) {
  return (
    <div className="flex items-center justify-end gap-1">
      {onEdit && (
        <Button variant="ghost" size="icon" onClick={onEdit} aria-label={`Edit ${name}`} title="Edit">
          <Icon name="edit" size={18} />
        </Button>
      )}
      {onRevoke && (
        <Button variant="ghost" size="icon" onClick={onRevoke} aria-label={`Revoke access for ${name}`} title="Revoke access" className="text-amber-700 hover:text-amber-800">
          <Icon name="ban" size={18} />
        </Button>
      )}
      {onRestore && (
        <Button variant="ghost" size="icon" onClick={onRestore} aria-label={`Restore access for ${name}`} title="Restore access" className="text-brand-700 hover:text-brand-800">
          <Icon name="refresh" size={18} />
        </Button>
      )}
      {onDelete && (
        <Button variant="ghost" size="icon" onClick={onDelete} aria-label={`Delete ${name}`} title="Delete" className="text-red-600 hover:text-red-700">
          <Icon name="trash" size={18} />
        </Button>
      )}
    </div>
  );
}
