export function TrueFalseAnswer({ response, onChange, disabled }: { response: Record<string, unknown> | null; onChange: (response: Record<string, unknown>) => void; disabled: boolean }) {
  const value = response?.value as boolean | undefined;
  return (
    <div className="flex gap-4">
      {[true, false].map((option) => (
        <label key={String(option)} className="flex items-center gap-2 text-sm text-slate-700">
          <input type="radio" checked={value === option} disabled={disabled} onChange={() => onChange({ value: option })} className="h-4 w-4 text-brand-600 focus:ring-brand-500" />
          {option ? "True" : "False"}
        </label>
      ))}
    </div>
  );
}
