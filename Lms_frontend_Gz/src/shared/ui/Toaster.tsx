import { useEffect } from "react";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { cn } from "@/core/lib/cn";
import { type Toast, toastDismissed } from "@/core/toast/toastSlice";
import { Icon } from "./Icon";

function ToastItem({ toast }: { toast: Toast }) {
  const dispatch = useAppDispatch();
  useEffect(() => {
    const timer = setTimeout(() => dispatch(toastDismissed(toast.id)), toast.tone === "error" ? 8000 : 4500);
    return () => clearTimeout(timer);
  }, [dispatch, toast]);

  return (
    <div
      role={toast.tone === "error" ? "alert" : "status"}
      className={cn(
        "pointer-events-auto flex w-full max-w-sm gap-3 rounded-2xl border bg-white p-4 shadow-pop",
        toast.tone === "error" ? "border-red-200" : toast.tone === "success" ? "border-brand-200" : "border-slate-200",
      )}
    >
      <Icon
        name={toast.tone === "success" ? "check" : toast.tone === "error" ? "alert" : "info"}
        className={cn("mt-0.5 shrink-0", toast.tone === "success" ? "text-brand-600" : toast.tone === "error" ? "text-red-600" : "text-navy-700")}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-navy-950">{toast.title}</p>
        {toast.description && <p className="mt-0.5 text-sm text-slate-500">{toast.description}</p>}
      </div>
      <button type="button" className="text-slate-400 hover:text-slate-600" onClick={() => dispatch(toastDismissed(toast.id))} aria-label="Dismiss">
        <Icon name="x" size={16} />
      </button>
    </div>
  );
}

export function Toaster() {
  const toasts = useAppSelector((state) => state.toasts);
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
