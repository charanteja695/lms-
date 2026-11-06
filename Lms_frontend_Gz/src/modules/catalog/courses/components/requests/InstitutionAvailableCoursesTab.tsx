import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { RequestCourseAccessModal } from "@/modules/catalog/courses/components/requests/RequestCourseAccessModal";
import type { Course } from "@/modules/catalog/courses/types";
import { useListCourseRequestsQuery } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { useListSubscriptionsQuery } from "@/modules/subscriptions/subscriptions/api/subscriptionsApi";
import { Badge, Button, EmptyState, Icon, PageLoader } from "@/shared/ui";

export function InstitutionAvailableCoursesTab() {
  const navigate = useNavigate();
  const [selectedCourseForRequest, setSelectedCourseForRequest] = useState<Course | null>(null);

  // 1. Fetch published courses
  const { data: coursesData, isLoading: loadingCourses, refetch: refetchCourses } = useListCoursesQuery({
    published_only: true,
    per_page: 50,
  });

  // 2. Fetch institution's subscriptions to filter out already-accessible courses
  const { data: subsData, isLoading: loadingSubs } = useListSubscriptionsQuery({
    per_page: 100,
  });

  // 3. Fetch institution's pending requests to prevent duplicate requests
  const { data: requestsData, isLoading: loadingRequests, refetch: refetchRequests } = useListCourseRequestsQuery({
    per_page: 100,
  });

  const subscribedCourseIds = useMemo(() => {
    const ids = new Set<string>();
    for (const sub of subsData?.items ?? []) {
      if (sub.status === "active") {
        ids.add(sub.course_id);
      }
    }
    return ids;
  }, [subsData]);

  const pendingCourseIds = useMemo(() => {
    const ids = new Set<string>();
    for (const req of requestsData?.items ?? []) {
      if (req.status === "submitted") {
        ids.add(req.course_id);
      }
    }
    return ids;
  }, [requestsData]);

  // Available courses = published courses NOT in active subscriptions
  const availableCourses = useMemo(() => {
    return (coursesData?.items ?? []).filter((c) => {
      // Must have at least one published version
      const isPublished = c.versions.some((v) => v.status === "published");
      if (!isPublished) return false;
      // Must not already have active access
      return !subscribedCourseIds.has(c.course_id);
    });
  }, [coursesData, subscribedCourseIds]);

  const isLoading = loadingCourses || loadingSubs || loadingRequests;

  if (isLoading) {
    return <PageLoader />;
  }

  if (availableCourses.length === 0) {
    return (
      <EmptyState
        icon="graduation"
        title="No Available Courses to Request"
        description="All published courses have already been subscribed to or there are no new courses available."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-1">
        <p className="text-xs text-slate-500 font-medium">
          Explore courses published on the platform and request access for your students.
        </p>
        <span className="text-xs font-semibold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-lg">
          {availableCourses.length} {availableCourses.length === 1 ? "Course Available" : "Courses Available"}
        </span>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {availableCourses.map((course) => {
          const isPending = pendingCourseIds.has(course.course_id);
          const publishedVersion =
            course.versions.find((v) => v.status === "published") ?? course.versions[0];

          return (
            <article
              key={course.course_id}
              className="flex flex-col justify-between overflow-hidden rounded-2xl bg-white border border-slate-200 shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5"
            >
              <div>
                {/* Header */}
                <div className="p-4 bg-slate-50/70 border-b border-slate-100">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <Badge tone="green">Published</Badge>
                    {isPending && <Badge tone="amber">Request Pending</Badge>}
                  </div>
                  <h3 className="line-clamp-2 text-base font-bold text-slate-900 leading-snug">
                    {course.title}
                  </h3>
                </div>

                {/* Body */}
                <div className="p-4 space-y-3">
                  <p className="line-clamp-2 text-xs text-slate-500 leading-relaxed min-h-[32px]">
                    {course.summary || "Comprehensive curriculum and practical modules designed for institution learners."}
                  </p>

                  <div className="grid grid-cols-2 gap-2 border-y border-slate-100 py-2.5 text-center">
                    <div className="flex flex-col items-center">
                      <span className="flex items-center gap-1 text-xs font-bold text-slate-800">
                        <Icon name="clock" size={13} className="text-indigo-600" />
                        Self-Paced
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">Duration</span>
                    </div>
                    <div className="flex flex-col items-center border-l border-slate-100">
                      <span className="flex items-center gap-1 text-xs font-bold text-slate-800">
                        <Icon name="layers" size={13} className="text-blue-600" />
                        v{publishedVersion?.version_number ?? 1}
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">Modules</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="p-4 pt-0 space-y-2">
                <Button
                  variant="secondary"
                  className="w-full text-xs"
                  onClick={() => navigate(`/courses/${course.course_id}`)}
                >
                  <Icon name="eye" size={13} className="mr-1" />
                  View Details
                </Button>

                {isPending ? (
                  <Button
                    variant="secondary"
                    disabled
                    className="w-full text-xs font-semibold bg-amber-50 text-amber-800 border-amber-200 cursor-not-allowed"
                  >
                    <Icon name="clock" size={13} className="mr-1" />
                    Request Pending Approval
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    className="w-full text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
                    onClick={() => setSelectedCourseForRequest(course)}
                  >
                    <Icon name="plus" size={13} className="mr-1" />
                    Request Access
                  </Button>
                )}
              </div>
            </article>
          );
        })}
      </div>

      <RequestCourseAccessModal
        open={Boolean(selectedCourseForRequest)}
        onClose={() => setSelectedCourseForRequest(null)}
        course={selectedCourseForRequest}
        onSuccess={() => {
          refetchRequests();
          refetchCourses();
        }}
      />
    </div>
  );
}
