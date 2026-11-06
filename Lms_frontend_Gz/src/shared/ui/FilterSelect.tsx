import { type Option, Select } from "./Select";

export function FilterSelect({ label, value, options, onChange, placeholder = "All" }: {
  label: string;
  value: string | undefined;
  options: readonly Option[];
  onChange: (value: string | undefined) => void;
  placeholder?: string;
}) {
  return (
    <Select
      aria-label={label}
      className="w-full sm:w-auto sm:min-w-44 sm:max-w-64"
      options={options}
      placeholder={`${label}: ${placeholder}`}
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value || undefined)}
    />
  );
}
