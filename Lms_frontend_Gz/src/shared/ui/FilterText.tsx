import { useEffect, useState } from "react";

import { Field } from "./Field";
import { Input } from "./Input";

export function FilterText({ label, value, onChange, placeholder }: { label: string; value: string | undefined; onChange: (value: string | undefined) => void; placeholder?: string }) {
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => setDraft(value ?? ""), [value]);  // "Clear filters" empties the box too
  return (
    <Field label={label}>
      {(props) => (
        <Input
          {...props}
          value={draft}
          placeholder={placeholder ?? `Any ${label.toLowerCase()}`}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => onChange(draft.trim() || undefined)}
          onKeyDown={(event) => {
            if (event.key === "Enter") onChange(draft.trim() || undefined);
          }}
        />
      )}
    </Field>
  );
}
