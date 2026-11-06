import { useState, useEffect } from "react";

import { formatDate, formatDateTime } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { CourseRequestStatusBadge } from "@/modules/subscriptions/common/components/CourseRequestStatusBadge";
import type { CourseRequestStatus } from "@/modules/subscriptions/common/types";
import { useListCourseRequestsQuery } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { ApproveDialog } from "@/modules/subscriptions/course-requests/components/detail/ApproveDialog";
import { RejectDialog } from "@/modules/subscriptions/course-requests/components/detail/RejectDialog";
import type { CourseRequest } from "@/modules/subscriptions/course-requests/types";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import { RequesterNameCell } from "@/modules/user-management/common/components/RequesterNameCell";
import { Button, Card, DescriptionList, EmptyState, Modal, Pagination } from "@/shared/ui";

type FilterStatus = "all" | "submitted" | "approved" | "rejected";

export function AdminCourseRequestsTab({
  initialStatus = "all",
  hideInternalFilter = false,
}: {
  initialStatus?: FilterStatus;
  hideInternalFilter?: boolean;
} = {}) {
  const [selectedStatus, setSelectedStatus] = useState<FilterStatus>(initialStatus);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(15);

  const [activeRequestForApproval, setActiveRequestForApproval] = useState<CourseRequest | null>(null);
  const [activeRequestIdForRejection, setActiveRequestIdForRejection] = useState<string | null>(null);
  const [detailsRequest, setDetailsRequest] = useState<CourseRequest | null>(null);

  useEffect(() => {
    setSelectedStatus(initialStatus);
  }, [initialStatus]);

  const queryParams = {
    page,
    per_page: perPage,
    ...(selectedStatus !== "all" ? { status: selectedStatus as CourseRequestStatus } : {}),
  };

  const { data, isFetching, isError, refetch } = useListCourseRequestsQuery(queryParams, {
    refetchOnMountOrArgChange: true,
  });

  const requests = data?.items ?? [];

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      {!hideInternalFilter && (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-2xs">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-slate-500 mr-1.5">Filter by Status:</span>
          {(
            [
              { id: "all", label: "All Requests" },
              { id: "submitted", label: "Pending" },
              { id: "approved", label: "Approved" },
              { id: "rejected", label: "Rejected" },
            ] as const
          ).map((tab) => {
            const isActive = selectedStatus === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setSelectedStatus(tab.id);
                  setPage(1);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                  isActive
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => void refetch()}
          loading={isFetching}
          className="text-xs"
        >
          Refresh
        </Button>
      </div>
      )}

      {/* Requests Table */}
      <Card bodyClassName="p-0" className="overflow-hidden">
        {isError ? (
          <EmptyState
            icon="alert"
            title="Could not load course requests"
            action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}
          />
        ) : requests.length === 0 && !isFetching ? (
          <EmptyState
            icon="graduation"
            title={selectedStatus !== "all" ? "No matching course requests" : "No course requests yet"}
            description={
              selectedStatus !== "all"
                ? "Try selecting another status filter."
                : "Course access requests submitted by Institution Heads will appear here."
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-semibold text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Course Name</th>
                    <th className="px-4 py-3">Requesting Institution</th>
                    <th className="px-4 py-3">Institution Head</th>
                    <th className="px-4 py-3">Request Date</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {requests.map((req) => {
                    const isPending = req.status === "submitted";
                    return (
                      <tr key={req.course_request_id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-4 py-3.5 font-medium text-slate-900">
                          {req.course_name ? (
                            <span>{req.course_name}</span>
                          ) : (
                            <CourseTitleCell courseId={req.course_id} />
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-slate-700">
                          {req.institution_name ? (
                            <span>{req.institution_name}</span>
                          ) : (
                            <InstitutionNameCell organizationId={req.organization_id} />
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-slate-700">
                          {req.requester_name ? (
                            <span>{req.requester_name}</span>
                          ) : (
                            <RequesterNameCell userId={req.requested_by} />
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-slate-500 whitespace-nowrap">
                          {formatDate(req.created_at.slice(0, 10))}
                        </td>
                        <td className="px-4 py-3.5">
                          <CourseRequestStatusBadge status={req.status} />
                        </td>
                        <td className="px-4 py-3.5 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="secondary"
                              size="sm"
                              className="text-xs py-1 px-2.5"
                              onClick={() => setDetailsRequest(req)}
                            >
                              View
                            </Button>
                            {isPending && (
                              <>
                                <Button
                                  variant="primary"
                                  size="sm"
                                  className="text-xs py-1 px-2.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                                  onClick={() => setActiveRequestForApproval(req)}
                                >
                                  Approve
                                </Button>
                                <Button
                                  variant="danger"
                                  size="sm"
                                  className="text-xs py-1 px-2.5"
                                  onClick={() => setActiveRequestIdForRejection(req.course_request_id)}
                                >
                                  Reject
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="border-t border-slate-100 p-3">
              <Pagination
                pageContext={data?.pageContext}
                disabled={isFetching}
                onPageChange={(p) => setPage(p)}
                onPerPageChange={(pp) => setPerPage(pp)}
              />
            </div>
          </>
        )}
      </Card>

      {/* Details Modal */}
      {detailsRequest && (
        <Modal
          open={Boolean(detailsRequest)}
          onClose={() => setDetailsRequest(null)}
          title="Course Access Request Details"
          description={`Request #${detailsRequest.course_request_id}`}
          footer={
            <div className="flex items-center justify-between w-full">
              <Button variant="secondary" onClick={() => setDetailsRequest(null)}>
                Close
              </Button>
              {detailsRequest.status === "submitted" && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      const id = detailsRequest.course_request_id;
                      setDetailsRequest(null);
                      setActiveRequestIdForRejection(id);
                    }}
                  >
                    Reject
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={() => {
                      const req = detailsRequest;
                      setDetailsRequest(null);
                      setActiveRequestForApproval(req);
                    }}
                  >
                    Approve
                  </Button>
                </div>
              )}
            </div>
          }
        >
          <div className="space-y-4 py-2">
            <DescriptionList
              items={[
                {
                  label: "Course",
                  value: detailsRequest.course_name || (
                    <CourseTitleCell courseId={detailsRequest.course_id} />
                  ),
                },
                {
                  label: "Institution",
                  value: detailsRequest.institution_name || (
                    <InstitutionNameCell organizationId={detailsRequest.organization_id} />
                  ),
                },
                {
                  label: "Requester",
                  value: detailsRequest.requester_name || (
                    <RequesterNameCell userId={detailsRequest.requested_by} />
                  ),
                },
                {
                  label: "Status",
                  value: <CourseRequestStatusBadge status={detailsRequest.status} />,
                },
                {
                  label: "Seats Requested",
                  value: detailsRequest.requested_seats.toLocaleString(),
                },
                {
                  label: "Term Duration",
                  value: `${detailsRequest.requested_term_days} days`,
                },
                {
                  label: "Submitted At",
                  value: formatDateTime(detailsRequest.created_at),
                },
                ...(detailsRequest.decided_at
                  ? [
                      {
                        label: "Decided At",
                        value: formatDateTime(detailsRequest.decided_at),
                      },
                      ...(detailsRequest.decision_reason
                        ? [
                            {
                              label: "Reason",
                              value: detailsRequest.decision_reason,
                            },
                          ]
                        : []),
                    ]
                  : []),
              ]}
            />
          </div>
        </Modal>
      )}

      {/* Approval Dialog */}
      {activeRequestForApproval && (
        <ApproveDialog
          open={Boolean(activeRequestForApproval)}
          onClose={() => {
            setActiveRequestForApproval(null);
            refetch();
          }}
          request={activeRequestForApproval}
        />
      )}

      {/* Rejection Dialog */}
      {activeRequestIdForRejection && (
        <RejectDialog
          open={Boolean(activeRequestIdForRejection)}
          onClose={() => {
            setActiveRequestIdForRejection(null);
            refetch();
          }}
          courseRequestId={activeRequestIdForRejection}
        />
      )}
    </div>
  );
}
