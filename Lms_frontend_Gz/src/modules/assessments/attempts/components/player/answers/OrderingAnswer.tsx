import { Button, Icon } from "@/shared/ui";

interface OrderItem {
  id: string;
  text: string;
}

export function OrderingAnswer({ items, response, onChange, disabled }: {
  items: OrderItem[];
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const order = (response?.order as string[]) ?? items.map((item) => item.id);
  const ordered = order.map((id) => items.find((item) => item.id === id)).filter((item): item is OrderItem => Boolean(item));

  const move = (index: number, direction: "up" | "down") => {
    const next = [...order];
    const swapWith = direction === "up" ? index - 1 : index + 1;
    [next[index], next[swapWith]] = [next[swapWith]!, next[index]!];
    onChange({ order: next });
  };

  return (
    <div className="space-y-2">
      {ordered.map((item, index) => (
        <div key={item.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <span className="w-6 text-center text-sm font-medium text-slate-400">{index + 1}</span>
          <span className="flex-1 text-sm text-slate-800">{item.text}</span>
          <Button variant="ghost" size="icon" aria-label="Move up" disabled={disabled || index === 0} onClick={() => move(index, "up")}>
            <Icon name="arrowUp" size={14} />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Move down" disabled={disabled || index === ordered.length - 1} onClick={() => move(index, "down")}>
            <Icon name="arrowDown" size={14} />
          </Button>
        </div>
      ))}
    </div>
  );
}
