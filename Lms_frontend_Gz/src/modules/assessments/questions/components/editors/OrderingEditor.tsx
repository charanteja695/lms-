import { newOptionId } from "@/modules/assessments/questions/lib/ids";
import type { MatchItem } from "@/modules/assessments/questions/bodyTypes";
import { Button, Field, Icon, Input } from "@/shared/ui";

/** Items are authored in their correct order; the server shuffles them before serving the paper. */
export function OrderingEditor({ items, onChange }: { items: MatchItem[]; onChange: (items: MatchItem[]) => void }) {
  const move = (index: number, direction: "up" | "down") => {
    const next = [...items];
    const swapWith = direction === "up" ? index - 1 : index + 1;
    [next[index], next[swapWith]] = [next[swapWith]!, next[index]!];
    onChange(next);
  };

  return (
    <Field label="Items, in the correct order" hint="Students see them shuffled; this is the order they must reconstruct.">
      {() => (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={item.id} className="flex items-center gap-2">
              <span className="w-6 text-center text-sm font-medium text-slate-400">{index + 1}</span>
              <Input value={item.text} onChange={(event) => onChange(items.map((i, ix) => (ix === index ? { ...i, text: event.target.value } : i)))} placeholder="Item text" className="flex-1" />
              <Button variant="ghost" size="icon" aria-label="Move up" disabled={index === 0} onClick={() => move(index, "up")}>
                <Icon name="arrowUp" size={14} />
              </Button>
              <Button variant="ghost" size="icon" aria-label="Move down" disabled={index === items.length - 1} onClick={() => move(index, "down")}>
                <Icon name="arrowDown" size={14} />
              </Button>
              <Button variant="ghost" size="icon" aria-label="Remove" disabled={items.length <= 2} onClick={() => onChange(items.filter((i) => i.id !== item.id))}>
                <Icon name="trash" size={14} />
              </Button>
            </div>
          ))}
          <Button variant="secondary" size="sm" icon="plus" onClick={() => onChange([...items, { id: newOptionId(), text: "" }])}>
            Add item
          </Button>
        </div>
      )}
    </Field>
  );
}
