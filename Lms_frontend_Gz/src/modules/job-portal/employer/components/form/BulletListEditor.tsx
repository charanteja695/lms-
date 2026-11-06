import React, { useState, useRef, useEffect } from "react";
import { Icon, Button } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export interface BulletListEditorProps {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  required?: boolean;
  minItems?: number;
  placeholder?: string;
  helperText?: string;
  maxItemLength?: number;
}

export function BulletListEditor({
  label,
  items,
  onChange,
  required = false,
  minItems = 0,
  placeholder = "Add a bullet item (press Enter or paste multiple lines)...",
  helperText,
  maxItemLength = 300,
}: BulletListEditorProps) {
  const [newText, setNewText] = useState("");
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [focusIdx, setFocusIdx] = useState<number | null>(null);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (focusIdx !== null && inputRefs.current[focusIdx]) {
      inputRefs.current[focusIdx]?.focus();
      setFocusIdx(null);
    }
  }, [focusIdx, items.length]);

  const addItem = (rawText: string) => {
    const trimmed = rawText.trim();
    if (!trimmed) {
      // If empty and user clicked Add Bullet, add an empty bullet and focus it
      const next = [...items, ""];
      onChange(next);
      setFocusIdx(next.length - 1);
      return;
    }

    // Split on newline if multi-line pasted
    const lines = rawText
      .split(/\r?\n/)
      .map((l) => l.trim().replace(/^[-•*]\s*/, "")) // remove leading bullet chars
      .filter((l) => l.length > 0)
      .map((l) => l.slice(0, maxItemLength));

    if (lines.length === 0) return;

    // Avoid duplicates
    const next = [...items];
    for (const line of lines) {
      if (!next.includes(line)) {
        next.push(line);
      }
    }
    onChange(next);
    setNewText("");
  };

  const updateItem = (index: number, val: string) => {
    const next = [...items];
    next[index] = val.slice(0, maxItemLength);
    onChange(next);
  };

  const removeItem = (index: number) => {
    const next = items.filter((_, i) => i !== index);
    onChange(next);
    if (index > 0) {
      setFocusIdx(index - 1);
    }
  };

  const insertItemAfter = (index: number) => {
    const next = [...items];
    next.splice(index + 1, 0, "");
    onChange(next);
    setFocusIdx(index + 1);
  };

  const moveItem = (from: number, to: number) => {
    if (to < 0 || to >= items.length || from < 0 || from >= items.length) return;
    const next = [...items];
    const moved = next[from];
    if (moved === undefined) return;
    next.splice(from, 1);
    next.splice(to, 0, moved);
    onChange(next);
  };

  const handleNewKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addItem(newText);
    }
  };

  const handleItemKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, idx: number) => {
    if (e.key === "Enter") {
      e.preventDefault();
      insertItemAfter(idx);
    } else if (e.key === "Backspace" && items[idx] === "" && items.length > 0) {
      e.preventDefault();
      removeItem(idx);
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text");
    if (text.includes("\n")) {
      e.preventDefault();
      addItem(text);
    }
  };

  const isBelowMin = minItems > 0 && items.length < minItems;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-700 flex items-center gap-1">
          <span>{label}</span>
          {required && <span className="text-rose-500 font-bold">*</span>}
          {minItems > 0 && (
            <span
              className={cn(
                "text-[11px] font-medium px-1.5 py-0.5 rounded ml-1.5 transition-colors",
                isBelowMin
                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                  : "bg-emerald-50 text-emerald-700 border border-emerald-200"
              )}
            >
              {items.length} of {minItems} min
            </span>
          )}
        </label>
        {items.length > 0 && (
          <span className="text-[11px] text-slate-400">
            {items.length} bullet{items.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {helperText && <p className="text-xs text-slate-500">{helperText}</p>}

      {/* Item List */}
      {items.length > 0 && (
        <ul className="space-y-1.5">
          {items.map((item, idx) => (
            <li
              key={idx}
              draggable
              onDragStart={() => setDraggedIdx(idx)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => {
                if (draggedIdx !== null && draggedIdx !== idx) {
                  moveItem(draggedIdx, idx);
                }
                setDraggedIdx(null);
              }}
              className={cn(
                "group flex items-start gap-2 p-2 rounded-lg border bg-white transition-all text-xs",
                draggedIdx === idx
                  ? "border-brand-500 bg-brand-50/50 opacity-60"
                  : "border-slate-200 hover:border-slate-300"
              )}
            >
              {/* Drag handle & Bullet point marker */}
              <div className="flex items-center gap-1.5 pt-1 text-slate-400">
                <span
                  className="cursor-grab active:cursor-grabbing hover:text-slate-600 inline-flex items-center"
                  title="Drag to reorder"
                >
                  <Icon name="grip-vertical" className="h-3.5 w-3.5 text-slate-400" />
                </span>
                <span className="text-emerald-600 font-extrabold text-base leading-none select-none">•</span>
              </div>

              {/* Item input */}
              <div className="flex-1 min-w-0">
                <input
                  ref={(el) => {
                    inputRefs.current[idx] = el;
                  }}
                  type="text"
                  value={item}
                  maxLength={maxItemLength}
                  onChange={(e) => updateItem(idx, e.target.value)}
                  onKeyDown={(e) => handleItemKeyDown(e, idx)}
                  placeholder="Type a requirement or responsibility..."
                  className="w-full text-xs text-slate-800 bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-500 rounded px-1.5 py-0.5"
                />
              </div>

              {/* Character counter & actions */}
              <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
                {item.length > maxItemLength * 0.8 && (
                  <span className="text-[10px] text-slate-400 mr-1">
                    {item.length}/{maxItemLength}
                  </span>
                )}

                {/* Move Up */}
                <button
                  type="button"
                  disabled={idx === 0}
                  onClick={() => moveItem(idx, idx - 1)}
                  className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-20 disabled:cursor-not-allowed"
                  title="Move up"
                  aria-label="Move bullet up"
                >
                  <Icon name="chevron-up" className="h-3.5 w-3.5" />
                </button>

                {/* Move Down */}
                <button
                  type="button"
                  disabled={idx === items.length - 1}
                  onClick={() => moveItem(idx, idx + 1)}
                  className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-20 disabled:cursor-not-allowed"
                  title="Move down"
                  aria-label="Move bullet down"
                >
                  <Icon name="chevron-down" className="h-3.5 w-3.5" />
                </button>

                {/* Delete */}
                <button
                  type="button"
                  onClick={() => removeItem(idx)}
                  className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                  title="Remove bullet"
                  aria-label="Remove bullet"
                >
                  <Icon name="trash" className="h-3.5 w-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Add New Input with leading bullet point */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 flex items-center">
          <span
            className="absolute left-3 text-emerald-600 font-extrabold text-base leading-none select-none pointer-events-none"
            aria-hidden="true"
          >
            •
          </span>
          <input
            type="text"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            onKeyDown={handleNewKeyDown}
            onPaste={handlePaste}
            placeholder={placeholder}
            maxLength={maxItemLength}
            className="w-full rounded-xl border border-slate-300 pl-7 pr-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 transition-colors"
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => addItem(newText)}
          className="shrink-0 text-xs font-semibold gap-1.5 rounded-xl border-slate-300 hover:border-emerald-600 hover:text-emerald-700 hover:bg-emerald-50/50 shadow-xs"
        >
          <Icon name="plus" className="h-3.5 w-3.5 text-emerald-600" />
          Add Bullet
        </Button>
      </div>
    </div>
  );
}
