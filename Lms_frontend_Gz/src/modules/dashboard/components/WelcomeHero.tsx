import type { ReactNode } from "react";

function greeting(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

/** The top of Home: who is signed in and where, today's date, and their main actions - on a light surface tinted with the logo's colours. */
export function WelcomeHero({ firstName, subtitle, actions }: { firstName: string; subtitle?: string; actions?: ReactNode }) {
  const now = new Date();
  const today = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  return (
    <section className="relative mb-8 overflow-hidden rounded-3xl border border-slate-200/70 bg-white px-6 py-7 text-navy-950 shadow-card sm:px-8 sm:py-9">
      <div className="absolute inset-0 bg-[radial-gradient(55%_90%_at_0%_0%,color-mix(in_oklab,var(--color-brand-100)_90%,transparent),transparent_70%),radial-gradient(40%_80%_at_100%_100%,color-mix(in_oklab,var(--color-navy-100)_80%,transparent),transparent_70%)]" aria-hidden="true" />
      <div className="absolute inset-0 opacity-[0.35] [background-image:radial-gradient(var(--color-slate-200)_1px,transparent_1px)] [background-size:20px_20px]" aria-hidden="true" />
      <div className="relative flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-brand-700">{today}</p>
          <h1 className="mt-1 text-[28px] font-extrabold tracking-tight sm:text-[34px]">
            {greeting(now.getHours())}, {firstName}
          </h1>
          {subtitle && <p className="mt-1.5 text-[15px] text-slate-600">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </section>
  );
}
