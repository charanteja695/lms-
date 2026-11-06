import { toOptions } from "@/core/lib/options";
import { newOptionId } from "@/modules/assessments/questions/lib/ids";
import type { MatchItem, ScoringMode } from "@/modules/assessments/questions/bodyTypes";
import { Button, Field, Icon, Input, Select } from "@/shared/ui";

const SCORING_LABELS: Record<ScoringMode, string> = { all_or_nothing: "All or nothing", partial: "Per pair" };

function ItemList({ label, items, onChange, hint }: { label: string; items: MatchItem[]; onChange: (items: MatchItem[]) => void; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      {() => (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id} className="flex items-center gap-2">
              <Input value={item.text} onChange={(event) => onChange(items.map((i) => (i.id === item.id ? { ...i, text: event.target.value } : i)))} placeholder="Text" className="flex-1" />
              <Button variant="ghost" size="icon" aria-label="Remove" disabled={items.length <= 2} onClick={() => onChange(items.filter((i) => i.id !== item.id))}>
                <Icon name="trash" size={14} />
              </Button>
            </div>
          ))}
          <Button variant="secondary" size="sm" icon="plus" onClick={() => onChange([...items, { id: newOptionId(), text: "" }])}>
            Add
          </Button>
        </div>
      )}
    </Field>
  );
}

export function MatchEditor({ left, right, pairs, scoring, onLeftChange, onRightChange, onPairsChange, onScoringChange }: {
  left: MatchItem[];
  right: MatchItem[];
  pairs: Record<string, string>;
  scoring: ScoringMode;
  onLeftChange: (items: MatchItem[]) => void;
  onRightChange: (items: MatchItem[]) => void;
  onPairsChange: (pairs: Record<string, string>) => void;
  onScoringChange: (scoring: ScoringMode) => void;
}) {
  const rightOptions = toOptions(Object.fromEntries(right.map((item) => [item.id, item.text || "(untitled)"])));

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <ItemList label="Left column" items={left} onChange={onLeftChange} />
        <ItemList label="Right column" items={right} onChange={onRightChange} hint="Extra items here act as decoys." />
      </div>
      <Field label="Correct pairs">
        {() => (
          <div className="space-y-2">
            {left.map((item) => (
              <div key={item.id} className="flex items-center gap-2">
                <span className="w-1/2 truncate text-sm text-slate-700">{item.text || "(untitled)"}</span>
                <Select
                  aria-label={`Match for ${item.text}`}
                  className="flex-1"
                  value={pairs[item.id] ?? ""}
                  placeholder="Select a match"
                  options={rightOptions}
                  onChange={(event) => onPairsChange({ ...pairs, [item.id]: event.target.value })}
                />
              </div>
            ))}
          </div>
        )}
      </Field>
      <Select aria-label="Scoring" className="w-40" value={scoring} options={toOptions(SCORING_LABELS)} onChange={(event) => onScoringChange(event.target.value as ScoringMode)} />
    </div>
  );
}
