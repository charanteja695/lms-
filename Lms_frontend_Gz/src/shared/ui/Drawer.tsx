import { createContext, useContext, useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/core/lib/cn";

export type DrawerSize = "md" | "lg" | "xl";

type DrawerContextValue = { titleId: string; close: () => void };
const DrawerContext = createContext<DrawerContextValue | null>(null);

/** Inside a drawer, page pieces (header, cards, sections, form actions) take their compact drawer shape. */
export function useInDrawer() {
  return useContext(DrawerContext);
}

const WIDTH: Record<DrawerSize, string> = { md: "sm:max-w-xl", lg: "sm:max-w-3xl", xl: "sm:max-w-5xl" };
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * A panel that slides over the page from the right (full screen on a phone), so a form opens on top of the list it
 * belongs to. Esc or the close button closes it; clicking the dimmed page does not, so a half-filled form is never
 * lost by a stray click. Focus stays inside while it is open and returns to where it was afterwards.
 */
export function Drawer({ onClose, size = "lg", children }: { onClose: () => void; size?: DrawerSize; children: ReactNode }) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const panel = panelRef.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const isTopmost = () => {
      const dialogs = document.querySelectorAll('[aria-modal="true"]');
      return dialogs[dialogs.length - 1] === panel;
    };
    const onKey = (event: KeyboardEvent) => {
      if (!panel || !isTopmost()) return; // a confirm dialog opened from the form handles its own keys
      if (event.key === "Escape") closeRef.current();
      if (event.key !== "Tab") return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null);
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    // first field, else the panel itself
    const firstField = panel?.querySelector<HTMLElement>("input:not([type=hidden]):not([disabled]), select, textarea");
    (firstField ?? panel)?.focus({ preventScroll: true });
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previouslyFocused?.focus?.({ preventScroll: true });
    };
  }, []);

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="drawer-backdrop absolute inset-0 bg-navy-950/35 backdrop-blur-[2px]" aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          "drawer-panel relative flex h-full w-full flex-col overflow-y-auto overscroll-contain bg-canvas shadow-pop focus:outline-none sm:border-l sm:border-slate-200/80",
          WIDTH[size],
        )}
      >
        <DrawerContext.Provider value={{ titleId, close: onClose }}>{children}</DrawerContext.Provider>
      </div>
    </div>,
    document.body,
  );
}
