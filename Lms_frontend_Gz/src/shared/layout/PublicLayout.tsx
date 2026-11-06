import { Outlet } from "react-router-dom";

import { env } from "@/core/config/env";
import { LogoMark } from "./LogoMark";

/** Pages anyone can open without signing in that need more room than the sign-in layout (a shared resume). */
export function PublicLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center gap-2.5 px-4 py-3 text-lg font-semibold text-navy-900">
          <LogoMark />
          {env.appName}
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
