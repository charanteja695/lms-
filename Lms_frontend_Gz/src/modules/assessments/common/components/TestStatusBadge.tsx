import { TEST_STATUS_LABELS, TEST_STATUS_TONES } from "@/modules/assessments/common/labels";
import type { TestStatus } from "@/modules/assessments/common/types";
import { Badge } from "@/shared/ui";

export function TestStatusBadge({ status }: { status: TestStatus }) {
  return <Badge tone={TEST_STATUS_TONES[status]}>{TEST_STATUS_LABELS[status]}</Badge>;
}
