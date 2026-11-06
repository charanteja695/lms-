import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { Icon, type IconName } from "./Icon";

export interface MenuItem {
  label: string;
  icon?: IconName;
  onSelect: () => void;
  tone?: "default" | "danger";
  hidden?: boolean;
  disabled?: boolean;
}

/** Dropdown of actions (row or page actions). Hidden items are omitted, so permissions stay in one place. */
export function Menu({ trigger, items, align = "right" }: { trigger: ReactNode; items: MenuItem[]; align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const visible = items.filter((item) => !item.hidden);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (visible.length === 0) return null;
  return (
    <div ref={ref} className="relative inline-block text-left">
      <div
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        {trigger}
      </div>
      {open && (
        <div
          role="menu"
          className={cn(
            "absolute z-30 mt-2 min-w-52 overflow-hidden rounded-xl border border-slate-200/80 bg-white p-1.5 shadow-pop",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {visible.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={(event) => {
                event.stopPropagation();
                setOpen(false);
                item.onSelect();
              }}
              className={cn(
                "flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors disabled:opacity-50",
                item.tone === "danger" ? "text-red-600 hover:bg-red-50" : "text-slate-700 hover:bg-slate-100 hover:text-navy-950",
              )}
            >
              {item.icon && <Icon name={item.icon} size={16} />}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
