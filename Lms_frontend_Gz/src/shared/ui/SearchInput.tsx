import { useEffect, useState } from "react";

import { useDebouncedValue } from "@/core/hooks/useDebouncedValue";
import { cn } from "@/core/lib/cn";
import { Icon } from "./Icon";

/** Search box that reports its value only after the user stops typing (and ignores 1-character terms). */
export function SearchInput({ value, onChange, placeholder = "Search…", className }: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);
  const debounced = useDebouncedValue(draft, 400);

  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    const next = debounced.trim();
    if (next.length === 1 || next === value) return;
    onChange(next);
  }, [debounced]);

  return (
    <div className={cn("relative", className)}>
      <Icon name="search" size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3.5 text-sm shadow-[0_1px_2px_rgb(16_24_40/0.04)] transition-[border-color,box-shadow] duration-150 placeholder:text-slate-400 hover:border-slate-300 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15"
      />
    </div>
  );
}
