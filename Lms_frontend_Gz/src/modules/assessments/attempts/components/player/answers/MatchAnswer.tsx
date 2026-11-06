import { toOptions } from "@/core/lib/options";
import { Select } from "@/shared/ui";

interface MatchItem {
  id: string;
  text: string;
}

export function MatchAnswer({ left, right, response, onChange, disabled }: {
  left: MatchItem[];
  right: MatchItem[];
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const pairs = (response?.pairs as Record<string, string>) ?? {};
  const rightOptions = toOptions(Object.fromEntries(right.map((item) => [item.id, item.text])));

  return (
    <div className="space-y-2">
      {left.map((item) => (
        <div key={item.id} className="flex items-center gap-3">
          <span className="w-1/2 text-sm text-slate-700">{item.text}</span>
          <Select
            aria-label={`Match for ${item.text}`}
            className="flex-1"
            value={pairs[item.id] ?? ""}
            disabled={disabled}
            placeholder="Select a match"
            options={rightOptions}
            onChange={(event) => onChange({ pairs: { ...pairs, [item.id]: event.target.value } })}
          />
        </div>
      ))}
    </div>
  );
}
