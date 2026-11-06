import { Field } from "@/shared/ui";

export function TrueFalseEditor({ correct, onChange }: { correct: boolean; onChange: (correct: boolean) => void }) {
  return (
    <Field label="Correct answer">
      {() => (
        <div className="flex gap-4">
          {[true, false].map((value) => (
            <label key={String(value)} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="radio" checked={correct === value} onChange={() => onChange(value)} className="h-4 w-4 text-brand-600 focus:ring-brand-500" />
              {value ? "True" : "False"}
            </label>
          ))}
        </div>
      )}
    </Field>
  );
}
