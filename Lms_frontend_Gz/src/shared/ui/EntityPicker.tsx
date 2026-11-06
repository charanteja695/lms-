import { useEffect, useId, useRef, useState } from "react";

import { useDebouncedValue } from "@/core/hooks/useDebouncedValue";
import { cn } from "@/core/lib/cn";
import { controlClass } from "./controlStyles";
import { Field } from "./Field";
import { Icon } from "./Icon";
import { Spinner } from "./Spinner";

export interface PickerOption {
  value: string;
  label: string;
  description?: string;
}

/** Hook supplying options for a search term. It should skip the request while `enabled` is false. */
export type OptionsHook = (search: string, enabled: boolean) => { options: PickerOption[]; isFetching: boolean };

/**
 * Searchable single-select for records (institutions, managers, admins). Options are fetched only when
 * the list is opened, and again only after the user pauses typing.
 */
export function EntityPicker({ label, value, selectedLabel, onChange, useOptions, placeholder = "Search…", emptyLabel = "Select…", hint, error, required, disabled, clearable = true }: {
  label: string;
  value: string;
  selectedLabel?: string;
  onChange: (value: string, label: string) => void;
  useOptions: OptionsHook;
  /** Search box placeholder, inside the open list. */
  placeholder?: string;
  /** Shown on the closed control while nothing is chosen. */
  emptyLabel?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  clearable?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const { options, isFetching } = useOptions(debounced.trim().length >= 2 ? debounced.trim() : "", open);
  const containerRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(props) => (
        <div ref={containerRef} className="relative">
          <button
            {...props}
            type="button"
            disabled={disabled}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-controls={listId}
            onClick={() => setOpen((current) => !current)}
            className={controlClass(Boolean(error), "flex h-11 items-center justify-between gap-2 text-left")}
          >
            <span className={cn("truncate", !value && "text-slate-400")}>{value ? selectedLabel || value : emptyLabel}</span>
            <span className="flex items-center gap-1 text-slate-400">
              {clearable && value && !disabled && (
                <span
                  role="button"
                  tabIndex={0}
                  aria-label="Clear"
                  onClick={(event) => {
                    event.stopPropagation();
                    onChange("", "");
                  }}
                  className="rounded p-0.5 hover:bg-slate-100 hover:text-slate-600"
                >
                  <Icon name="x" size={14} />
                </span>
              )}
              <Icon name="chevronDown" size={16} />
            </span>
          </button>
          {open && (
            <div className="absolute z-40 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg">
              <div className="flex items-center gap-2 border-b border-slate-100 px-3">
                <Icon name="search" size={16} className="text-slate-400" />
                <input
                  autoFocus
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={placeholder}
                  className="h-10 w-full border-0 bg-transparent text-sm focus:outline-none"
                />
                {isFetching && <Spinner size={14} className="text-slate-400" />}
              </div>
              <ul id={listId} role="listbox" className="max-h-64 overflow-y-auto py-1">
                {options.length === 0 && !isFetching && <li className="px-3 py-2 text-sm text-slate-500">No matches</li>}
                {options.map((option) => (
                  <li key={option.value}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={option.value === value}
                      onClick={() => {
                        onChange(option.value, option.label);
                        setOpen(false);
                        setSearch("");
                      }}
                      className={cn("flex w-full flex-col px-3 py-2 text-left hover:bg-slate-50", option.value === value && "bg-brand-50")}
                    >
                      <span className="text-sm text-slate-900">{option.label}</span>
                      {option.description && <span className="text-xs text-slate-500">{option.description}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Field>
  );
}
