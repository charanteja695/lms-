import { Link } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { cn } from "@/core/lib/cn";
import type { Interview } from "@/modules/ai-interview/common/types";
import { useListMockPlansQuery, useListMyInterviewsQuery } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { PracticeSetup } from "@/modules/ai-interview/student/components/PracticeSetup";
import { Icon, PageHeader, Spinner } from "@/shared/ui";

const DONE = ["completed", "evaluated", "reviewed"];
const linkTo = (i: Interview) => (DONE.includes(i.status) ? `/interviews/mine/${i.interview_id}/report` : `/interviews/mine/${i.interview_id}`);

/** Company interviews waiting for me on top, practice set-up, and my past interviews with their scores. */
export function PracticePage() {
  const { data: plans = [], isLoading } = useListMockPlansQuery();
  const { data: mine } = useListMyInterviewsQuery({ per_page: 50 });
  const interviews = mine?.items ?? [];
  const waiting = interviews.filter((i) => i.kind === "screening" && (i.status === "invited" || i.status === "in_progress"));
  const past = interviews.filter((i) => DONE.includes(i.status));
  const scored = past.filter((i) => i.overall_score != null);

  return (
    <>
      <PageHeader title="AI interview" description="Practise as often as you like. The AI asks follow-up questions and gives you a report." />
      <div className="space-y-5">
        {waiting.map((i) => (
          <Link key={i.interview_id} to={linkTo(i)} className="flex flex-wrap items-center gap-4 rounded-2xl bg-accent-50 p-4 ring-2 ring-accent-400 hover:bg-accent-100/60">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-accent-700 ring-1 ring-accent-200"><Icon name="briefcase" size={20} /></span>
            <span className="min-w-[220px] flex-1">
              <span className="block text-[15px] font-bold text-navy-950">A company interview is waiting: {i.role}</span>
              <span className="block text-[13px] text-slate-600">{i.duration_minutes} min · counts for your application{i.invite_expires_at ? ` · open until ${formatDate(i.invite_expires_at)}` : ""}</span>
            </span>
            <span className="inline-flex h-10 items-center rounded-xl bg-brand-700 px-4 text-sm font-bold text-white">{i.status === "in_progress" ? "Continue" : "Start"}</span>
          </Link>
        ))}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
          {isLoading ? <Spinner /> : <PracticeSetup plans={plans} />}
          <section aria-labelledby="progress" className="space-y-3 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60 sm:p-6">
            <h2 id="progress" className="text-lg font-extrabold text-navy-950">Your interviews</h2>
            {scored.length >= 2 && (
              <p className="text-[13px] text-slate-600">
                Latest score <strong className="text-navy-950">{scored[0]!.overall_score}</strong> of {scored[0]!.score_max}, from {scored[scored.length - 1]!.overall_score} in your first scored interview.
              </p>
            )}
            {past.length === 0 ? (
              <p className="text-sm text-slate-500">No interviews yet. Your reports will collect here.</p>
            ) : (
              <ul className="space-y-2">
                {past.map((i) => (
                  <li key={i.interview_id}>
                    <Link to={linkTo(i)} className="flex items-center gap-3 rounded-xl p-2.5 ring-1 ring-slate-200 hover:bg-slate-50">
                      <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-sm font-extrabold", i.overall_score != null ? "bg-brand-50 text-brand-800" : "bg-slate-100 text-slate-500")}>
                        {i.overall_score ?? "—"}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-bold text-navy-950">{i.role}</span>
                        <span className="block text-xs text-slate-500">{i.kind === "screening" ? "Company interview" : "Practice"} · {formatDate(i.completed_at ?? i.created_at)}</span>
                      </span>
                      <span className="text-[13px] font-bold text-brand-700">Report</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
