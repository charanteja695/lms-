import type { BuildIssue } from "@/modules/catalog/builder/hooks/useBuildIssues";
import type { CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";
import { Icon } from "@/shared/ui";

/** "Before you publish": what is left, each one a link to where it gets fixed. */
export function PublishPanel({ issues, loading, onGo }: { issues: BuildIssue[]; loading: boolean; onGo: (issue: BuildIssue) => void }) {
  const shown = issues.slice(0, 8);
  return (
    <section className="rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
      <div className="flex items-center gap-3">
        <span className={issues.length ? "flex h-11 w-11 items-center justify-center rounded-full bg-amber-100 text-amber-800" : "flex h-11 w-11 items-center justify-center rounded-full bg-brand-600 text-white"}>
          {issues.length ? <span className="text-base font-extrabold">{issues.length}</span> : <Icon name="check" size={20} />}
        </span>
        <div>
          <h2 className="text-[15px] font-bold text-navy-950">Before you publish</h2>
          <p className="text-[13px] text-slate-500">{loading ? "Checking…" : issues.length ? `${issues.length} ${issues.length === 1 ? "thing" : "things"} left. Click one to go there.` : "Everything is ready."}</p>
        </div>
      </div>
      {shown.length > 0 && (
        <ul className="mt-3 space-y-1">
          {shown.map((issue) => (
            <li key={issue.key}>
              <button type="button" onClick={() => onGo(issue)} className="flex w-full gap-2.5 rounded-xl p-2.5 text-left transition-colors hover:bg-amber-50">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-extrabold text-amber-800">!</span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-slate-900">{issue.title}</span>
                  <span className="block text-[13px] text-slate-600">{issue.text}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {issues.length > shown.length && <p className="mt-2 px-2.5 text-[13px] text-slate-500">…and {issues.length - shown.length} more.</p>}
    </section>
  );
}

const durationLabel = (seconds: number) => {
  const hours = Math.floor(seconds / 3600);
  const mins = Math.round((seconds % 3600) / 60);
  return hours ? `${hours}h ${mins}m` : `${mins}m`;
};

/** The course in numbers, straight from the version. */
export function BuildStats({ version }: { version: CourseVersionDetail }) {
  const items = version.modules.flatMap((module) => module.topics.flatMap((topic) => topic.items));
  const seconds = items.reduce((total, item) => total + (item.item_type === "video" ? item.duration_seconds ?? 0 : 0), 0);
  const stats = [
    { value: String(items.length), label: items.length === 1 ? "lesson" : "lessons" },
    { value: seconds >= 60 ? durationLabel(seconds) : `${seconds}s`, label: "of video" },
    { value: String(items.filter((item) => item.item_type === "pdf").length), label: "PDFs" },
    { value: String(version.modules.reduce((total, module) => total + module.topics.length, 0)), label: "topics" },
  ];
  return (
    <section className="grid grid-cols-2 gap-4 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
      {stats.map((stat) => (
        <div key={stat.label}>
          <p className="text-xl font-extrabold text-navy-950">{stat.value}</p>
          <p className="text-[13px] text-slate-500">{stat.label}</p>
        </div>
      ))}
    </section>
  );
}
