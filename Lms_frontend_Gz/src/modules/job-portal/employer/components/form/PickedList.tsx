import type { ReactNode } from "react";

import type { Picked } from "@/modules/job-portal/employer/form/jobForm";
import { Badge, Button, EntityPicker, Icon, type OptionsHook } from "@/shared/ui";

/** A multi-pick built from the single-select EntityPicker: chosen entries as removable chips. */
export function PickedList({ label, hint, picked, useOptions, onChange, renderLabel }: {
  label: string;
  hint?: string;
  picked: Picked[];
  useOptions: OptionsHook;
  onChange: (next: Picked[]) => void;
  /** For an entry loaded from a saved job (id only, empty label). */
  renderLabel?: (picked: Picked) => ReactNode;
}) {
  return (
    <div className="space-y-2">
      <EntityPicker
        label={label}
        hint={hint}
        value=""
        useOptions={useOptions}
        onChange={(id, text) => id && !picked.some((p) => p.id === id) && onChange([...picked, { id, label: text }])}
      />
      {picked.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {picked.map((p) => (
            <Badge key={p.id} tone="blue">
              {p.label || renderLabel?.(p) || `#${p.id}`}
              <Button variant="ghost" size="icon" className="ml-1 h-4 w-4" aria-label="Remove" onClick={() => onChange(picked.filter((x) => x.id !== p.id))}>
                <Icon name="x" size={12} />
              </Button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
