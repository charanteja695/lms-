import { Outlet } from "react-router-dom";

import { env } from "@/core/config/env";
import { Icon, type IconName } from "@/shared/ui";
import { LogoMark } from "./LogoMark";

const PILLARS: Array<{ icon: IconName; title: string; text: string }> = [
  { icon: "graduation", title: "Learn", text: "Courses, batches and progress for every student" },
  { icon: "shield", title: "Certify", text: "Proctored exams and certificates anyone can verify" },
  { icon: "briefcase", title: "Get hired", text: "AI tutor, resumes, mock interviews and jobs" },
];

/** Sign-in and account pages: the brand story on the left (desktop), the form on the right. Colours are the logo's. */
export function AuthLayout() {
  return (
    <div className="flex min-h-screen bg-white">
      <aside className="relative hidden w-[48%] max-w-[720px] overflow-hidden border-r border-slate-200/70 bg-canvas lg:block">
        {/* soft tints of the logo's green (top), navy (middle) and orange (bottom), over a faint dot grid */}
        <div className="absolute inset-0 bg-[radial-gradient(60%_50%_at_10%_0%,color-mix(in_oklab,var(--color-brand-100)_95%,transparent),transparent_70%),radial-gradient(50%_40%_at_100%_100%,color-mix(in_oklab,var(--color-accent-100)_90%,transparent),transparent_70%),radial-gradient(70%_60%_at_80%_30%,color-mix(in_oklab,var(--color-navy-100)_85%,transparent),transparent_70%)]" />
        <div className="absolute inset-0 opacity-[0.5] [background-image:radial-gradient(var(--color-slate-200)_1px,transparent_1px)] [background-size:22px_22px]" aria-hidden="true" />

        <div className="relative flex h-full flex-col justify-between px-12 py-10 text-navy-950 xl:px-16">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-card ring-1 ring-slate-200/70">
              <LogoMark className="h-10 w-10" />
            </span>
            <div className="leading-tight">
              <p className="text-lg font-bold">{env.appName}</p>
              {env.organizationName && <p className="text-xs font-medium text-slate-500">{env.organizationName}</p>}
            </div>
          </div>

          <div className="max-w-lg">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-semibold text-brand-800">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />
              Learn · Certify · Get hired
            </span>
            <h2 className="mt-6 text-4xl font-extrabold leading-[1.1] tracking-tight xl:text-[44px]">
              Where every student{" "}
              <span className="bg-gradient-to-r from-brand-700 via-navy-900 to-accent-600 bg-clip-text text-transparent">grows into a professional</span>
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-slate-600">
              One platform for institutions, teachers and students — from the first lesson to the first job.
            </p>

            <ul className="mt-10 space-y-4">
              {PILLARS.map((pillar) => (
                <li key={pillar.title} className="flex items-start gap-4">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-brand-700 shadow-card">
                    <Icon name={pillar.icon} size={20} />
                  </span>
                  <div>
                    <p className="font-semibold">{pillar.title}</p>
                    <p className="text-sm text-slate-600">{pillar.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-card">
              <Icon name="key" size={18} className="text-accent-600" />
              <p className="text-xs leading-snug text-slate-600">
                Secured with two-factor sign-in
                <br />
                and encrypted storage
              </p>
            </div>
            <p className="text-xs text-slate-500">© {new Date().getFullYear()} {env.organizationName || env.appName}</p>
          </div>
        </div>
      </aside>

      <main className="flex flex-1 items-center justify-center bg-canvas px-5 py-10 sm:px-10 lg:bg-white">
        <div className="w-full max-w-[420px]">
          {/* phones and tablets have no side panel: the logo goes above the form */}
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-card ring-1 ring-slate-200/70">
              <LogoMark className="h-10 w-10" />
            </span>
            <div className="leading-tight">
              <p className="text-lg font-bold text-navy-950">{env.appName}</p>
              {env.organizationName && <p className="text-xs font-medium text-slate-500">{env.organizationName}</p>}
            </div>
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
