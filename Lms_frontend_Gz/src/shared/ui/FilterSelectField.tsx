import { FilterSelect } from "./FilterSelect";

export function FilterSelectField({ label, value, options, onChange }: { label: string; value: string | undefined; options: Array<{ value: string; label: string }>; onChange: (value: string | undefined) => void }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <FilterSelect label={label} value={value} options={options} onChange={onChange} />
    </div>
  );
}
