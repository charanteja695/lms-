import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import { useGetCourseRequestQuery } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { ApproveDialog } from "@/modules/subscriptions/course-requests/components/detail/ApproveDialog";
import { RejectDialog } from "@/modules/subscriptions/course-requests/components/detail/RejectDialog";
import { CourseRequestStatusBadge } from "@/modules/subscriptions/common/components/CourseRequestStatusBadge";
import { Alert, Button, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function CourseRequestDetailPage() {
  const { can } = useCan();
  const { courseRequestId = "" } = useParams();
  const navigate = useNavigate();
  const canDecide = can("accounts.manage");
  const { data: request, isLoading, isError } = useGetCourseRequestQuery(courseRequestId, { skip: !courseRequestId });
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  if (isLoading) return <PageLoader />;
  if (isError || !request) {
    return <EmptyState icon="alert" title="Course request not found" action={<Button onClick={() => navigate("/course-requests")}>Back to course requests</Button>} />;
  }

  return (
    <>
      <PageHeader
        backTo="/course-requests"
        backLabel="Course requests"
        title={
          <span className="flex flex-wrap items-center gap-3">
            <CourseTitleCell courseId={request.course_id} />
            <CourseRequestStatusBadge status={request.status} />
          </span>
        }
        actions={
          canDecide &&
          request.status === "submitted" && (
            <>
              <Button variant="secondary" icon="x" onClick={() => setRejecting(true)}>
                Reject
              </Button>
              <Button icon="check" onClick={() => setApproving(true)}>
                Approve
              </Button>
            </>
          )
        }
      />

      {request.status === "rejected" && request.decision_reason && (
        <Alert tone="warning" title="Rejected" className="mb-6">
          {request.decision_reason}
        </Alert>
      )}

      <DescriptionList
        items={[
          { label: "Institution", value: <InstitutionNameCell organizationId={request.organization_id} /> },
          { label: "Requested by", value: request.requested_by },
          { label: "Requested seats", value: request.requested_seats.toLocaleString() },
          { label: "Requested term", value: `${request.requested_term_days} days` },
          { label: "Submitted", value: formatDateTime(request.created_at) },
          ...(request.decided_at
            ? [
                { label: "Decided by", value: request.decided_by },
                { label: "Decided", value: formatDateTime(request.decided_at) },
              ]
            : []),
        ]}
      />

      {approving && <ApproveDialog open={approving} onClose={() => setApproving(false)} request={request} />}
      {rejecting && <RejectDialog open={rejecting} onClose={() => setRejecting(false)} courseRequestId={request.course_request_id} />}
    </>
  );
}
