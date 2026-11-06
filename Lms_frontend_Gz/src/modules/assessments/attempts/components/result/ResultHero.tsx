import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import type { AttemptResultView } from "@/modules/assessments/attempts/resultTypes";

/** The verdict at a glance: the score ring, passed or not yet, and where to go next. */
export function ResultHero({ result }: { result: AttemptResultView }) {
  const passed = result.result === "passed";
  const percent = Math.round(result.percent ?? 0);
  return (
    <section className={cn("flex flex-wrap items-center gap-7 rounded-3xl p-6 shadow-card ring-1 sm:p-8", passed ? "bg-brand-50/70 ring-brand-200" : "bg-white ring-slate-200/60")}>
      <div
        role="img"
        aria-label={`Score ${percent} percent`}
        className="flex h-36 w-36 shrink-0 items-center justify-center rounded-full"
        style={{ background: `conic-gradient(var(${passed ? "--color-brand-600" : "--color-red-600"}) 0 ${percent}%, rgb(226 232 240) ${percent}% 100%)` }}
      >
        <div className="flex h-[116px] w-[116px] flex-col items-center justify-center rounded-full bg-white">
          <span className="text-3xl font-extrabold text-navy-950">{percent}%</span>
          {result.pass_mark_percent != null && <span className="text-xs text-slate-500">pass mark {result.pass_mark_percent}%</span>}
        </div>
      </div>
      <div className="min-w-0 flex-1 basis-72 space-y-2">
        <span className={cn("inline-block rounded-full px-3 py-1 text-xs font-extrabold tracking-[0.08em]", passed ? "bg-brand-600 text-white" : "bg-red-100 text-red-800")}>
          {passed ? "PASSED" : "NOT PASSED YET"}
        </span>
        <h1 className="text-2xl font-extrabold tracking-tight text-navy-950">{result.test_title}</h1>
        <p className="text-[15px] text-slate-700">
          {result.score != null && result.max_score != null && <>You scored <strong>{result.score} of {result.max_score}</strong>. </>}
          {passed ? "Well done. The next part of your course is open." : "Review your answers below, go over the lessons again, then try once more."}
        </p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Link to="/my-learning" className="inline-flex h-11 items-center rounded-xl bg-brand-700 px-5 text-sm font-bold text-white hover:bg-brand-800">
            {passed ? "Continue learning" : "Back to the lessons"}
          </Link>
          <Link to="/my-tests" className="inline-flex h-11 items-center rounded-xl bg-white px-5 text-sm font-bold text-navy-950 ring-1 ring-slate-300 hover:bg-slate-50">
            My tests
          </Link>
        </div>
      </div>
    </section>
  );
}
