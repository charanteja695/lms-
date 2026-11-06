import { Checkbox } from "@/shared/ui";

interface ChoiceOption {
  id: string;
  text: string;
}

export function McqAnswer({ multi, options, response, onChange, disabled }: {
  multi: boolean;
  options: ChoiceOption[];
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const selected: string[] = multi ? ((response?.selected as string[]) ?? []) : response?.selected ? [response.selected as string] : [];

  const toggle = (id: string) => {
    if (multi) onChange({ selected: selected.includes(id) ? selected.filter((value) => value !== id) : [...selected, id] });
    else onChange({ selected: id });
  };

  return (
    <div className="space-y-2">
      {options.map((option) => (
        <label key={option.id} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50 has-[:checked]:border-brand-400 has-[:checked]:bg-brand-50">
          {multi ? (
            <Checkbox label="" checked={selected.includes(option.id)} disabled={disabled} onChange={() => toggle(option.id)} />
          ) : (
            <input type="radio" checked={selected.includes(option.id)} disabled={disabled} onChange={() => toggle(option.id)} className="h-4 w-4 text-brand-600 focus:ring-brand-500" />
          )}
          <span className="text-sm text-slate-800">{option.text}</span>
        </label>
      ))}
    </div>
  );
}
