import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

import { NAV_GROUPS } from "@/app/navigation";
import { useNavItems } from "@/app/useNavItems";
import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";

const groupLabel = (key: string) => NAV_GROUPS.find((g) => g.key === key)?.label ?? "";

/**
 * Jump to any page this person may open: Ctrl/Cmd+K (or the search box in the header), type a few letters, Enter.
 * It searches only their own menu (the server's permissions), by name, description and section.
 */
export function QuickJump() {
  const navigate = useNavigate();
  const items = useNavItems();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((v) => !v); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => { if (open) { setQuery(""); setActive(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((i) => !q || `${i.label} ${i.hint} ${groupLabel(i.group)}`.toLowerCase().includes(q)).slice(0, 12);
  }, [items, query]);
  const go = (to: string) => { setOpen(false); navigate(to); };

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-label="Jump to a page (Ctrl+K)" className="flex h-10 cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-400 shadow-[0_1px_2px_rgb(16_24_40/0.04)] transition-colors hover:border-slate-300 hover:text-slate-600 sm:w-64">
        <Icon name="search" size={16} />
        <span className="hidden flex-1 text-left sm:inline">Jump to…</span>
        <kbd className="hidden rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-sans text-[11px] font-semibold text-slate-500 sm:inline">Ctrl K</kbd>
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Jump to a page">
          <div className="absolute inset-0 bg-navy-950/30 backdrop-blur-sm" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="relative w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-pop ring-1 ring-slate-200/60">
            <div className="flex items-center gap-3 border-b border-slate-100 px-4">
              <Icon name="search" size={18} className="text-slate-400" />
              <input
                ref={input}
                value={query}
                placeholder="Type a page name, e.g. grading, billing, jobs"
                aria-label="Page name"
                className="h-14 flex-1 bg-transparent text-[15px] text-slate-900 placeholder:text-slate-400 focus:outline-none"
                onChange={(e) => { setQuery(e.target.value); setActive(0); }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setOpen(false);
                  if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
                  if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                  if (e.key === "Enter" && results[active]) go(results[active].to);
                }}
              />
            </div>
            <ul className="max-h-[50vh] overflow-y-auto p-2" role="listbox" aria-label="Pages">
              {results.length === 0 && <li className="px-3 py-8 text-center text-sm text-slate-500">No page matches “{query}”.</li>}
              {results.map((item, index) => (
                <li key={item.to} role="option" aria-selected={index === active}>
                  <button type="button" onMouseEnter={() => setActive(index)} onClick={() => go(item.to)} className={cn("flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors", index === active ? "bg-brand-50" : "hover:bg-slate-50")}>
                    <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", index === active ? "bg-white text-brand-700 ring-1 ring-brand-100" : "bg-slate-100 text-slate-500")}><Icon name={item.icon} size={18} /></span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-navy-950">{item.label}</span>
                      <span className="block truncate text-xs text-slate-500">{item.hint}</span>
                    </span>
                    {groupLabel(item.group) && <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{groupLabel(item.group)}</span>}
                  </button>
                </li>
              ))}
            </ul>
            <p className="border-t border-slate-100 bg-slate-50/60 px-4 py-2 text-[11px] text-slate-500">↑ ↓ to move · Enter to open · Esc to close</p>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
