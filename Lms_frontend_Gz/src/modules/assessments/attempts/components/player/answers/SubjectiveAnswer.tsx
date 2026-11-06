import { Textarea } from "@/shared/ui";

export function SubjectiveAnswer({ maxWords, response, onChange, disabled }: {
  maxWords?: number;
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const text = (response?.text as string) ?? "";
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;

  return (
    <div className="space-y-1">
      <Textarea value={text} disabled={disabled} onChange={(event) => onChange({ text: event.target.value })} rows={8} />
      {maxWords && <p className={`text-xs ${words > maxWords ? "text-red-600" : "text-slate-500"}`}>{words} / {maxWords} words</p>}
    </div>
  );
}
