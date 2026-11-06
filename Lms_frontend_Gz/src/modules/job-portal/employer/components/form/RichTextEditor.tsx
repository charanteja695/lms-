import { useState, useRef } from "react";
import { Icon } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export interface RichTextEditorProps {
  label?: string;
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
  placeholder?: string;
  required?: boolean;
  minCharacters?: number;
  helperText?: string;
}

export function RichTextEditor({
  label = "About the Job",
  value,
  onChange,
  disabled = false,
  placeholder = "Describe the company mission, what the candidate will be working on, and why this position is exciting...",
  required = false,
  minCharacters = 10,
  helperText = "1 to 3 short paragraphs describing mission, role, and impact (bold, italic, lists, links supported)",
}: RichTextEditorProps) {
  const [mode, setMode] = useState<"write" | "preview">("write");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const applyFormat = (prefix: string, suffix: string = "", placeholderText: string = "text") => {
    const el = textareaRef.current;
    if (!el || disabled) return;

    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = value.substring(start, end);
    const replacement = selected ? `${prefix}${selected}${suffix}` : `${prefix}${placeholderText}${suffix}`;

    const nextValue = value.substring(0, start) + replacement + value.substring(end);
    onChange(nextValue);

    // Re-focus and position cursor
    setTimeout(() => {
      el.focus();
      if (selected) {
        el.setSelectionRange(start, start + replacement.length);
      } else {
        el.setSelectionRange(start + prefix.length, start + prefix.length + placeholderText.length);
      }
    }, 0);
  };

  const handleBold = () => applyFormat("**", "**", "bold text");
  const handleItalic = () => applyFormat("*", "*", "italic text");
  const handleLink = () => applyFormat("[", "](https://example.com)", "link title");

  const handleBulletList = () => {
    const el = textareaRef.current;
    if (!el || disabled) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = value.substring(start, end) || "List item 1\nList item 2";
    const formatted = selected
      .split("\n")
      .map((line) => (line.startsWith("- ") ? line : `- ${line}`))
      .join("\n");

    const nextValue = value.substring(0, start) + formatted + value.substring(end);
    onChange(nextValue);
    setTimeout(() => {
      el.focus();
      el.setSelectionRange(start, start + formatted.length);
    }, 0);
  };

  const isBelowMin = minCharacters > 0 && value.trim().length < minCharacters;

  // Simple safe renderer for preview
  const renderPreview = (text: string) => {
    if (!text.trim()) {
      return <p className="text-slate-400 italic text-xs">Nothing to preview yet. Switch to "Write" to start typing.</p>;
    }

    const lines = text.split("\n");
    return (
      <div className="space-y-2 text-xs text-slate-800 leading-relaxed font-normal">
        {lines.map((line, idx) => {
          if (line.startsWith("- ") || line.startsWith("* ")) {
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="text-brand-600 font-bold select-none">•</span>
                <span>{line.replace(/^[-*]\s*/, "")}</span>
              </div>
            );
          }
          if (/^\d+\.\s/.test(line)) {
            const num = line.match(/^(\d+)\.\s/)?.[1] || "1";
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="text-slate-500 font-semibold select-none">{num}.</span>
                <span>{line.replace(/^\d+\.\s*/, "")}</span>
              </div>
            );
          }
          if (!line.trim()) {
            return <div key={idx} className="h-2" />;
          }
          return <p key={idx}>{line}</p>;
        })}
      </div>
    );
  };

  return (
    <div className="space-y-1.5">
      {/* Header with Label and Character Status */}
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-700 flex items-center gap-1">
          <span>{label}</span>
          {required && <span className="text-rose-500 font-bold">*</span>}
          {minCharacters > 0 && (
            <span
              className={cn(
                "text-[11px] font-medium px-1.5 py-0.5 rounded ml-1.5 transition-colors",
                isBelowMin
                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                  : "bg-emerald-50 text-emerald-700 border border-emerald-200"
              )}
            >
              {value.trim().length}/{minCharacters} min chars
            </span>
          )}
        </label>
        {helperText && <span className="text-[11px] text-slate-400">{helperText}</span>}
      </div>

      {/* Editor Box */}
      <div className="rounded-xl border border-slate-300 bg-white overflow-hidden shadow-2xs focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-500 transition-all">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-50/80 border-b border-slate-200 text-xs">
          {/* Formatting Controls */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={disabled || mode === "preview"}
              onClick={handleBold}
              className="p-1.5 rounded hover:bg-slate-200/70 text-slate-700 disabled:opacity-40 font-bold text-xs transition-colors"
              title="Bold (**text**)"
              aria-label="Bold text"
            >
              <span className="font-extrabold font-serif px-1">B</span>
            </button>

            <button
              type="button"
              disabled={disabled || mode === "preview"}
              onClick={handleItalic}
              className="p-1.5 rounded hover:bg-slate-200/70 text-slate-700 disabled:opacity-40 italic text-xs transition-colors"
              title="Italic (*text*)"
              aria-label="Italic text"
            >
              <span className="italic font-serif px-1">I</span>
            </button>

            <span className="h-4 w-[1px] bg-slate-300 mx-1" />

            <button
              type="button"
              disabled={disabled || mode === "preview"}
              onClick={handleBulletList}
              className="px-2 py-1 rounded hover:bg-slate-200/70 text-slate-700 disabled:opacity-40 text-xs font-medium flex items-center gap-1 transition-colors"
              title="Bullet list (- item)"
              aria-label="Bullet list"
            >
              <Icon name="list" className="h-3.5 w-3.5" />
              <span>List</span>
            </button>

            <button
              type="button"
              disabled={disabled || mode === "preview"}
              onClick={handleLink}
              className="px-2 py-1 rounded hover:bg-slate-200/70 text-slate-700 disabled:opacity-40 text-xs font-medium flex items-center gap-1 transition-colors"
              title="Link ([title](url))"
              aria-label="Insert link"
            >
              <Icon name="link" className="h-3.5 w-3.5" />
              <span>Link</span>
            </button>
          </div>

          {/* Write / Preview Tab Switch */}
          <div className="flex items-center rounded-lg bg-slate-200/60 p-0.5 text-[11px] font-semibold">
            <button
              type="button"
              onClick={() => setMode("write")}
              className={cn(
                "px-2.5 py-0.5 rounded-md transition-colors",
                mode === "write" ? "bg-white text-slate-900 shadow-2xs font-bold" : "text-slate-600 hover:text-slate-900"
              )}
            >
              Write
            </button>
            <button
              type="button"
              onClick={() => setMode("preview")}
              className={cn(
                "px-2.5 py-0.5 rounded-md transition-colors",
                mode === "preview" ? "bg-white text-slate-900 shadow-2xs font-bold" : "text-slate-600 hover:text-slate-900"
              )}
            >
              Preview
            </button>
          </div>
        </div>

        {/* Editor Body */}
        {mode === "write" ? (
          <textarea
            ref={textareaRef}
            rows={5}
            value={value}
            disabled={disabled}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
            className="w-full p-3 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent resize-y leading-relaxed font-sans"
          />
        ) : (
          <div className="p-4 bg-slate-50/40 min-h-[120px] max-h-[300px] overflow-y-auto">
            {renderPreview(value)}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 px-0.5">
        <span>{value.length} characters</span>
        <span>{required ? `Required (min ${minCharacters} characters)` : "Optional"}</span>
      </div>
    </div>
  );
}
