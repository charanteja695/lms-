import { COURSE_REQUEST_STATUS_LABELS, COURSE_REQUEST_STATUS_TONES } from "@/modules/subscriptions/common/labels";
import type { CourseRequestStatus } from "@/modules/subscriptions/common/types";
import { Badge } from "@/shared/ui";

export function CourseRequestStatusBadge({ status }: { status: CourseRequestStatus }) {
  return <Badge tone={COURSE_REQUEST_STATUS_TONES[status]}>{COURSE_REQUEST_STATUS_LABELS[status]}</Badge>;
}
