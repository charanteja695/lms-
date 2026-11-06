import { formatDate, formatDateTime } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { CourseRequestStatusBadge } from "@/modules/subscriptions/common/components/CourseRequestStatusBadge";
import { useListCourseRequestsQuery } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { Button, Card, EmptyState, PageLoader } from "@/shared/ui";

export function InstitutionMyRequestsTab({
  filterStatus = "all",
}: {
  filterStatus?: "all" | "submitted" | "approved" | "rejected";
} = {}) {
  const queryParam = filterStatus !== "all" ? { status: filterStatus as any, per_page: 50 } : { per_page: 50 };
  const { data, isLoading, isError, refetch } = useListCourseRequestsQuery(
    queryParam,
    { refetchOnMountOrArgChange: true }
  );

  const rawRequests = data?.items ?? [];
  const requests = filterStatus === "all" ? rawRequests : rawRequests.filter((r) => r.status === filterStatus);

  if (isLoading) return <PageLoader />;

  if (isError) {
    return (
      <EmptyState
        icon="alert"
        title="Could not load requests"
        action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}
      />
    );
  }

  if (requests.length === 0) {
    return (
      <EmptyState
        icon="graduation"
        title="No Course Requests Submitted"
        description="Browse the Available Courses tab to request courses for your institution."
      />
    );
  }

  return (
    <Card bodyClassName="p-0" className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-semibold text-slate-600">
            <tr>
              <th className="px-4 py-3">Course Name</th>
              <th className="px-4 py-3">Request Date</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Decision Date</th>
              <th className="px-4 py-3">Remarks / Rejection Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {requests.map((req) => (
              <tr key={req.course_request_id} className="hover:bg-slate-50/60 transition-colors">
                <td className="px-4 py-3.5 font-medium text-slate-900">
                  {req.course_name ? (
                    <span>{req.course_name}</span>
                  ) : (
                    <CourseTitleCell courseId={req.course_id} />
                  )}
                </td>
                <td className="px-4 py-3.5 text-slate-600 whitespace-nowrap">
                  {formatDate(req.created_at.slice(0, 10))}
                </td>
                <td className="px-4 py-3.5">
                  <CourseRequestStatusBadge status={req.status} />
                </td>
                <td className="px-4 py-3.5 text-slate-500 whitespace-nowrap">
                  {req.decided_at ? formatDateTime(req.decided_at) : "—"}
                </td>
                <td className="px-4 py-3.5 text-slate-700">
                  {req.status === "rejected" ? (
                    <span className="text-rose-600 font-medium">
                      {req.decision_reason || "Access request rejected by administrator."}
                    </span>
                  ) : req.status === "approved" ? (
                    <span className="text-emerald-700 font-medium">
                      Approved with {req.requested_seats} seats ({req.requested_term_days} days)
                    </span>
                  ) : (
                    <span className="text-slate-400 italic">Awaiting administrator review</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
