import { SlotCard } from "@/modules/assessments/tests/components/sections/SlotCard";
import type { SectionInput } from "@/modules/assessments/tests/sectionTypes";
import { Button, Icon, Input, Textarea } from "@/shared/ui";

export function SectionCard({ section, onChange, onRemove, onMove, canMoveUp, canMoveDown, showTimeLimit }: {
  section: SectionInput;
  onChange: (section: SectionInput) => void;
  onRemove: () => void;
  onMove: (direction: "up" | "down") => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  /** Only meaningful when the test's time_mode is per_section. */
  showTimeLimit: boolean;
}) {
  const setSlot = (index: number, slot: SectionInput["slots"][number]) => onChange({ ...section, slots: section.slots.map((item, i) => (i === index ? slot : item)) });
  const moveSlot = (index: number, direction: "up" | "down") => {
    const next = [...section.slots];
    const swapWith = direction === "up" ? index - 1 : index + 1;
    [next[index], next[swapWith]] = [next[swapWith]!, next[index]!];
    onChange({ ...section, slots: next });
  };

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center gap-2">
        <Input value={section.title} onChange={(event) => onChange({ ...section, title: event.target.value })} placeholder="Section title" className="flex-1 bg-white" />
        {showTimeLimit && (
          <Input
            type="number"
            value={section.time_limit_minutes ?? ""}
            onChange={(event) => onChange({ ...section, time_limit_minutes: event.target.value ? Number(event.target.value) : undefined })}
            placeholder="Minutes"
            className="w-28 bg-white"
          />
        )}
        <Button variant="ghost" size="icon" aria-label="Move section up" disabled={!canMoveUp} onClick={() => onMove("up")}>
          <Icon name="arrowUp" size={14} />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Move section down" disabled={!canMoveDown} onClick={() => onMove("down")}>
          <Icon name="arrowDown" size={14} />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Remove section" onClick={onRemove}>
          <Icon name="trash" size={14} />
        </Button>
      </div>
      <Textarea
        value={section.instructions ?? ""}
        onChange={(event) => onChange({ ...section, instructions: event.target.value })}
        placeholder="Section instructions (optional)"
        rows={2}
        className="bg-white"
      />
      <div className="space-y-2 pl-4">
        {section.slots.map((slot, index) => (
          <SlotCard
            key={index}
            slot={slot}
            onChange={(next) => setSlot(index, next)}
            onRemove={() => onChange({ ...section, slots: section.slots.filter((_, i) => i !== index) })}
            onMove={(direction) => moveSlot(index, direction)}
            canMoveUp={index > 0}
            canMoveDown={index < section.slots.length - 1}
          />
        ))}
        <Button
          variant="secondary"
          size="sm"
          icon="plus"
          onClick={() => onChange({ ...section, slots: [...section.slots, { slot_type: "fixed", question_id: "", marks: 1 }] })}
        >
          Add slot
        </Button>
      </div>
    </div>
  );
}
