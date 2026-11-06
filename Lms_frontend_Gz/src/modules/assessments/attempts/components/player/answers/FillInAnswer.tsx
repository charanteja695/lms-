import { Input } from "@/shared/ui";

export function FillInAnswer({ blanks, response, onChange, disabled }: { blanks: number; response: Record<string, unknown> | null; onChange: (response: Record<string, unknown>) => void; disabled: boolean }) {
  const values: (string | null)[] = (response?.values as (string | null)[]) ?? Array.from({ length: blanks }, () => null);

  const setValue = (index: number, value: string) => {
    const next = [...values];
    next[index] = value || null;
    onChange({ values: next });
  };

  return (
    <div className="space-y-2">
      {Array.from({ length: blanks }, (_, index) => (
        <Input key={index} value={values[index] ?? ""} disabled={disabled} onChange={(event) => setValue(index, event.target.value)} placeholder={`Blank ${index + 1}`} className="max-w-xs" />
      ))}
    </div>
  );
}
