import { Field } from "./Field";
import { Input } from "./Input";

export function FilterDate({ label, value, onChange }: { label: string; value: string | undefined; onChange: (value: string | undefined) => void }) {
  return (
    <Field label={label}>
      {(props) => <Input {...props} type="date" value={value ?? ""} onChange={(event) => onChange(event.target.value || undefined)} />}
    </Field>
  );
}
