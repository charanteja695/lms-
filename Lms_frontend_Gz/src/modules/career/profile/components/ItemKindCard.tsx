import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { KIND_LABELS, KIND_SINGULAR } from "@/modules/career/common/labels";
import { SELF_DECLARED_KINDS, type ItemKind, type SelfDeclaredKind } from "@/modules/career/common/types";
import { useDeleteProfileItemMutation, useReorderProfileItemsMutation } from "@/modules/career/profile/api/profileApi";
import { ItemDialog } from "@/modules/career/profile/components/ItemDialog";
import { itemSummary } from "@/modules/career/profile/components/itemSummary";
import type { ProfileItem } from "@/modules/career/profile/types";
import { Badge, Button, Card, ConfirmDialog, Icon } from "@/shared/ui";

/** One kind of profile item. Verified kinds (certificates, courses, scores) come from the platform and are read-only. */
export function ItemKindCard({ kind, items, editable }: { kind: ItemKind; items: ProfileItem[]; editable: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [remove] = useDeleteProfileItemMutation();
  const [reorder] = useReorderProfileItemsMutation();
  const [editing, setEditing] = useState<ProfileItem | "new" | null>(null);
  const selfDeclared = (SELF_DECLARED_KINDS as readonly ItemKind[]).includes(kind);
  const canEdit = editable && selfDeclared;

  const move = async (index: number, delta: number) => {
    const ids = items.map((item) => item.item_id);
    [ids[index], ids[index + delta]] = [ids[index + delta]!, ids[index]!];
    try {
      await reorder({ kind, item_ids: ids }).unwrap();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card
      title={KIND_LABELS[kind]}
      description={selfDeclared ? undefined : "Verified by the platform; added automatically."}
      actions={canEdit && <Button size="sm" variant="secondary" icon="plus" onClick={() => setEditing("new")}>Add {KIND_SINGULAR[kind]}</Button>}
    >
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">{selfDeclared ? "Nothing added yet." : "None yet."}</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((item, index) => {
            const { heading, detail } = itemSummary(item);
            return (
              <li key={item.item_id} className="flex items-start gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                    {heading || "(untitled)"}
                    <Badge tone={item.verified ? "green" : "gray"}>{item.label}</Badge>
                    {!item.active && <Badge tone="red">{item.inactive_reason ?? "Inactive"}</Badge>}
                  </p>
                  {detail && <p className="text-xs text-slate-500">{detail}</p>}
                </div>
                {canEdit && (
                  <div className="flex shrink-0 items-center">
                    <Button variant="ghost" size="icon" aria-label="Move up" disabled={index === 0} onClick={() => void move(index, -1)}><Icon name="arrowUp" size={14} /></Button>
                    <Button variant="ghost" size="icon" aria-label="Move down" disabled={index === items.length - 1} onClick={() => void move(index, 1)}><Icon name="arrowDown" size={14} /></Button>
                    <Button variant="ghost" size="icon" aria-label="Edit" onClick={() => setEditing(item)}><Icon name="edit" size={14} /></Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete"
                      onClick={() =>
                        confirm.ask({ title: `Delete "${heading}"?`, description: "It is removed from your profile and from every resume draft.", confirmLabel: "Delete" }, async () => {
                          try {
                            await remove(item.item_id).unwrap();
                          } catch (error) {
                            notify.apiError(error);
                          }
                        })
                      }
                    >
                      <Icon name="trash" size={14} />
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {editing && (
        <ItemDialog
          kind={kind as SelfDeclaredKind}
          item={editing === "new" ? undefined : editing}
          existingItems={items}
          onClose={() => setEditing(null)}
        />
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}
