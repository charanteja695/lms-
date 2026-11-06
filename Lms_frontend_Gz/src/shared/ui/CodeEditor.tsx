import { cn } from "@/core/lib/cn";

/**
 * A plain-text code editor: monospace, Tab inserts a real tab instead of moving focus. No syntax
 * highlighting or language server — this app has no editor dependency, and a plain textarea is
 * enough for running/judging code (the engine sees the same text either way).
 */
export function CodeEditor({ value, onChange, language, rows = 16, disabled, className }: {
  value: string;
  onChange: (value: string) => void;
  /** Shown as a small label above the editor; purely informational. */
  language?: string;
  rows?: number;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("overflow-hidden rounded-lg border border-slate-300 bg-slate-900", className)}>
      {language && <div className="border-b border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400">{language}</div>}
      <textarea
        value={value}
        disabled={disabled}
        spellCheck={false}
        rows={rows}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          event.preventDefault();
          const el = event.currentTarget;
          const { selectionStart, selectionEnd } = el;
          const next = `${value.slice(0, selectionStart)}  ${value.slice(selectionEnd)}`;
          onChange(next);
          requestAnimationFrame(() => el.setSelectionRange(selectionStart + 2, selectionStart + 2));
        }}
        className="w-full resize-y bg-transparent p-3 font-mono text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none disabled:opacity-60"
      />
    </div>
  );
}
