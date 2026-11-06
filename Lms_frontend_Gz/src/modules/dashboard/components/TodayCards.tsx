import { Link } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { useListHomeTestsQuery } from "@/modules/dashboard/api/homeApi";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Badge, Card, Icon } from "@/shared/ui";

/** A student's "right now": the courses they are taking and the tests open (or about to open) for them. */
export function TodayCards() {
  const { holds } = useCan();
  const studies = holds("learning.study");
  const takesTests = holds("assessments.take");
  const { data: courses = [] } = useListMyCoursesQuery(undefined, { skip: !studies });
  const { data: tests = [] } = useListHomeTestsQuery(undefined, { skip: !takesTests });
  if (!studies && !takesTests) return null;

  return (
    <div className="mb-8 grid gap-5 lg:grid-cols-2">
      {studies && (
        <Card
          className="hover:border-brand-300 transition-colors shadow-card"
          title={
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100">
                <Icon name="graduation" size={16} />
              </span>
              <span>Continue learning</span>
            </div>
          }
          actions={
            <Link to="/my-learning" className="text-xs font-semibold text-brand-700 hover:underline">
              View all ({courses.length})
            </Link>
          }
        >
          {courses.length === 0 ? (
            <div className="py-6 text-center">
              <Icon name="graduation" size={28} className="mx-auto mb-2 text-slate-300" />
              <p className="text-sm font-semibold text-slate-700">No active course enrollments</p>
              {holds("store.buy") ? (
                <p className="mt-1 text-xs text-slate-500">
                  Buy a course in the <Link to="/store" className="font-semibold text-brand-700 hover:underline">course store</Link> and it appears here.
                </p>
              ) : (
                <p className="mt-1 text-xs text-slate-500">Your institution enrols you into batches. Active courses will appear here.</p>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {courses.slice(0, 5).map((c) => (
                <li key={c.course_id}>
                  <Link
                    to="/my-learning"
                    className="group flex items-center justify-between gap-3 py-3 text-sm hover:text-brand-700 transition-colors"
                  >
                    <span className="flex min-w-0 items-center gap-2.5">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition-colors group-hover:bg-brand-50 group-hover:text-brand-700">
                        <Icon name="play" size={14} />
                      </span>
                      <span className="truncate font-semibold text-navy-950 group-hover:text-brand-700">{c.title}</span>
                    </span>
                    <span className="flex items-center gap-1 text-xs font-semibold text-brand-700">
                      Resume <Icon name="chevronRight" size={14} className="transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {takesTests && (
        <Card
          className="hover:border-navy-300 transition-colors shadow-card"
          title={
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-navy-50 text-navy-800 ring-1 ring-navy-100">
                <Icon name="clipboardCheck" size={16} />
              </span>
              <span>Open & Upcoming Tests</span>
            </div>
          }
          actions={
            <Link to="/my-tests" className="text-xs font-semibold text-brand-700 hover:underline">
              All tests ({tests.length})
            </Link>
          }
        >
          {tests.length === 0 ? (
            <div className="py-6 text-center">
              <Icon name="check" size={28} className="mx-auto mb-2 text-brand-500" />
              <p className="text-sm font-semibold text-slate-700">All caught up!</p>
              <p className="mt-1 text-xs text-slate-500">No tests are open or pending for you right now.</p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {tests.slice(0, 5).map((t) => (
                <li key={t.test_id}>
                  <Link
                    to="/my-tests"
                    className="group flex items-center justify-between gap-3 py-3 text-sm hover:text-brand-700 transition-colors"
                  >
                    <span className="truncate font-semibold text-navy-950 group-hover:text-brand-700">{t.title}</span>
                    <div className="flex shrink-0 items-center gap-2">
                      {t.open_attempt_id ? (
                        <Badge tone="amber">In progress</Badge>
                      ) : t.can_start ? (
                        <Badge tone="green">Open now</Badge>
                      ) : (
                        <Badge tone="blue">Opens {formatDateTime(t.opens_at)}</Badge>
                      )}
                      <Icon name="chevronRight" size={14} className="text-slate-300 group-hover:text-brand-600 transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
