import type { ReactNode } from "react";

/** The form side of every sign-in and account page: a clear heading, the form, and an optional footnote. */
export function AuthCard({ title, description, children, footer }: { title: string; description?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-[28px] font-extrabold tracking-tight text-navy-950 sm:text-[32px]">{title}</h1>
        {description && <p className="text-[15px] leading-relaxed text-slate-500">{description}</p>}
      </div>
      {children}
      {footer && <div className="border-t border-slate-100 pt-6 text-center text-sm text-slate-500">{footer}</div>}
    </div>
  );
}
