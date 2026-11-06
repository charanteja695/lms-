import { useEffect, useState } from "react";
import { useRouteError, useLocation, useNavigate } from "react-router-dom";

import { Button, Icon, PageLoader } from "@/shared/ui";
import { isStaleBuildError, reloadForNewVersion } from "./staleBuild";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";

/** Shown instead of a broken page: a newer release reloads itself; anything else gets a plain, friendly way out with diagnostics. */
export function RouteError() {
  const error = useRouteError();
  const location = useLocation();
  const navigate = useNavigate();
  const stale = isStaleBuildError(error);

  let authData: { user?: any; role?: string } = {};
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    authData = useAuth();
  } catch {
    // Redux store not mounted or unavailable
  }

  const [showDetails, setShowDetails] = useState(false);
  const [copied, setCopied] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  const errorMessage = (error as any)?.message || (error as any)?.statusText || String(error || "Unknown application error");
  const errorStack = (error as any)?.stack || "No stack trace available";

  useEffect(() => {
    let timer: NodeJS.Timeout | undefined;
    if (stale) {
      const reloaded = reloadForNewVersion();
      // If guarded or failed, time out after 3.5s and show error UI
      timer = setTimeout(() => setTimedOut(true), 3500);
      if (!reloaded) setTimedOut(true);
    } else {
      console.error("[RouteError] Unhandled route crash:", {
        error,
        route: location.pathname + location.search,
        userRole: authData.role,
        userEmail: authData.user?.email,
      });
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [stale, error, location, authData.role, authData.user?.email]);

  const copyDetails = () => {
    const report = [
      `GenZ LMS Route Error Report`,
      `---------------------------------`,
      `Time: ${new Date().toISOString()}`,
      `Route: ${location.pathname}${location.search}`,
      `User Role: ${authData.role || "Unauthenticated"}`,
      `User Email: ${authData.user?.email || "N/A"}`,
      `User Agent: ${navigator.userAgent}`,
      `Error Name: ${(error as any)?.name || "Error"}`,
      `Error Message: ${errorMessage}`,
      ``,
      `Stack Trace:`,
      errorStack,
    ].join("\n");

    navigator.clipboard.writeText(report).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  // Only show spinner momentarily while triggering reload; never get stuck forever
  if (stale && !timedOut) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
        <PageLoader label="Refreshing application..." />
        <button
          type="button"
          onClick={() => setTimedOut(true)}
          className="mt-4 text-xs font-semibold text-slate-400 hover:text-slate-600 underline cursor-pointer"
        >
          Taking too long? Show error details
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-10">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200/80 bg-white p-7 text-center shadow-card">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 ring-1 ring-rose-200">
          <Icon name="alertTriangle" size={24} />
        </div>
        <h1 className="mt-4 text-xl font-bold text-navy-950">Something went wrong</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">
          This page could not be loaded. You can retry, or go back to Courses safely.
        </p>

        <div className="mt-6 flex justify-center gap-3">
          <Button variant="secondary" onClick={() => window.location.reload()} className="rounded-xl border-slate-300">
            Retry
          </Button>
          <button
            type="button"
            onClick={() => navigate("/courses")}
            className="inline-flex h-10 items-center rounded-xl bg-emerald-600 px-4 text-sm font-semibold text-white shadow-brand hover:bg-emerald-700 cursor-pointer"
          >
            Back to courses
          </button>
        </div>

        {/* Technical Diagnostics Accordion */}
        <div className="mt-6 border-t border-slate-200/80 pt-4 text-left">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowDetails(!showDetails)}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1.5 cursor-pointer"
            >
              <Icon name={showDetails ? "chevronUp" : "chevronDown"} size={14} />
              <span>{showDetails ? "Hide technical diagnostic details" : "Show technical diagnostic details"}</span>
            </button>

            {showDetails && (
              <button
                type="button"
                onClick={copyDetails}
                className="text-xs text-slate-500 hover:text-emerald-700 font-medium flex items-center gap-1 cursor-pointer"
              >
                <Icon name={copied ? "check" : "copy"} size={14} />
                <span>{copied ? "Copied" : "Copy details"}</span>
              </button>
            )}
          </div>

          {showDetails && (
            <div className="mt-3 p-3.5 rounded-xl bg-slate-900 text-slate-200 text-xs font-mono max-h-64 overflow-y-auto space-y-2">
              <div>
                <span className="text-slate-400 font-bold">Route: </span>
                <span className="text-emerald-400">{location.pathname}{location.search}</span>
              </div>
              <div>
                <span className="text-slate-400 font-bold">Role: </span>
                <span>{authData.role || "N/A"}</span>
              </div>
              <div>
                <span className="text-slate-400 font-bold">Exception: </span>
                <span className="text-rose-400 font-semibold">{errorMessage}</span>
              </div>
              <div>
                <span className="text-slate-400 font-bold">Stack Trace:</span>
                <pre className="whitespace-pre-wrap text-[11px] text-slate-300 mt-1">{errorStack}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
