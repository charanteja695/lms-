import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import type { Course } from "@/modules/catalog/courses/types";
import { useListSubscriptionsQuery } from "@/modules/subscriptions/subscriptions/api/subscriptionsApi";
import { Badge, Button, EmptyState, PageLoader } from "@/shared/ui";

export function InstitutionApprovedCoursesTab() {
  const navigate = useNavigate();

  // 1. Fetch institution's subscriptions
  const { data: subsData, isLoading: loadingSubs, isError, refetch } = useListSubscriptionsQuery(
    { per_page: 100 },
    { refetchOnMountOrArgChange: true }
  );

  // 2. Fetch courses list
  const { data: coursesData, isLoading: loadingCourses } = useListCoursesQuery({
    per_page: 100,
  });

  const coursesMap = useMemo(() => {
    const map = new Map<string, Course>();
    for (const c of coursesData?.items ?? []) {
      map.set(c.course_id, c);
    }
    return map;
  }, [coursesData]);

  const activeSubscriptions = useMemo(() => {
    return (subsData?.items ?? []).filter((s) => s.status === "active");
  }, [subsData]);

  if (loadingSubs || loadingCourses) return <PageLoader />;

  if (isError) {
    return (
      <EmptyState
        icon="alert"
        title="Could not load approved courses"
        action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}
      />
    );
  }

  if (activeSubscriptions.length === 0) {
    return (
      <EmptyState
        icon="graduation"
        title="No Approved Courses Yet"
        description="Your institution does not have any active approved courses. Request access from the Available Courses tab."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-1">
        <p className="text-xs text-slate-500 font-medium">
          Courses approved and activated for students and staff in your institution.
        </p>
        <span className="text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
          {activeSubscriptions.length} {activeSubscriptions.length === 1 ? "Active Course" : "Active Courses"}
        </span>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {activeSubscriptions.map((sub) => {
          const course = coursesMap.get(sub.course_id);
          const courseTitle = course?.title;

          return (
            <article
              key={sub.subscription_id}
              className="flex flex-col justify-between overflow-hidden rounded-2xl bg-white border border-slate-200 shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5"
            >
              <div>
                {/* Header */}
                <div className="p-4 bg-emerald-50/50 border-b border-emerald-100">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <Badge tone="green">Active Access</Badge>
                    <span className="text-[11px] font-semibold text-slate-500">
                      {sub.seats_total} Seats
                    </span>
                  </div>
                  <h3 className="line-clamp-2 text-base font-bold text-slate-900 leading-snug">
                    {courseTitle ? (
                      courseTitle
                    ) : (
                      <CourseTitleCell courseId={sub.course_id} />
                    )}
                  </h3>
                </div>

                {/* Body */}
                <div className="p-4 space-y-3">
                  <p className="line-clamp-2 text-xs text-slate-500 leading-relaxed min-h-[32px]">
                    {course?.summary || "Full course access is active for enrolled students in your institution."}
                  </p>

                  <div className="grid grid-cols-2 gap-2 border-y border-slate-100 py-2.5 text-center">
                    <div className="flex flex-col items-center">
                      <span className="text-xs font-bold text-slate-800">
                        {formatDate(sub.starts_at.slice(0, 10))}
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">Start Date</span>
                    </div>
                    <div className="flex flex-col items-center border-l border-slate-100">
                      <span className="text-xs font-bold text-slate-800">
                        {formatDate(sub.ends_at.slice(0, 10))}
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">Valid Until</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="p-4 pt-0">
                <Button
                  variant="primary"
                  className="w-full text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
                  onClick={() => navigate(`/courses/${sub.course_id}`)}
                >
                  View Course
                </Button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
