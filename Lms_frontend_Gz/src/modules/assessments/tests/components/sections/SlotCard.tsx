import { PoolCriteriaEditor } from "@/modules/assessments/tests/components/sections/PoolCriteriaEditor";
import type { SlotInput } from "@/modules/assessments/tests/sectionTypes";
import { Button, Icon, Input, Select } from "@/shared/ui";

const SLOT_TYPE_OPTIONS = [
  { value: "fixed", label: "Fixed question" },
  { value: "pool", label: "Pool (random pick)" },
];

export function SlotCard({ slot, onChange, onRemove, onMove, canMoveUp, canMoveDown }: {
  slot: SlotInput;
  onChange: (slot: SlotInput) => void;
  onRemove: () => void;
  onMove: (direction: "up" | "down") => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-2">
        <Select
          aria-label="Slot type"
          className="w-48"
          value={slot.slot_type}
          options={SLOT_TYPE_OPTIONS}
          onChange={(event) => onChange({ ...slot, slot_type: event.target.value as SlotInput["slot_type"] })}
        />
        {slot.slot_type === "fixed" ? (
          <Input value={slot.question_id ?? ""} onChange={(event) => onChange({ ...slot, question_id: event.target.value })} placeholder="Question ID" className="flex-1" />
        ) : (
          <Input
            type="number"
            value={slot.count ?? 1}
            onChange={(event) => onChange({ ...slot, count: Number(event.target.value) })}
            placeholder="How many"
            className="w-28"
          />
        )}
        <Input
          type="number"
          value={slot.marks ?? ""}
          onChange={(event) => onChange({ ...slot, marks: event.target.value ? Number(event.target.value) : null })}
          placeholder="Marks each"
          className="w-28"
        />
        <Button variant="ghost" size="icon" aria-label="Move up" disabled={!canMoveUp} onClick={() => onMove("up")}>
          <Icon name="arrowUp" size={14} />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Move down" disabled={!canMoveDown} onClick={() => onMove("down")}>
          <Icon name="arrowDown" size={14} />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Remove slot" onClick={onRemove}>
          <Icon name="trash" size={14} />
        </Button>
      </div>
      {slot.slot_type === "pool" && <PoolCriteriaEditor criteria={slot.criteria ?? {}} onChange={(criteria) => onChange({ ...slot, criteria })} />}
    </div>
  );
}
