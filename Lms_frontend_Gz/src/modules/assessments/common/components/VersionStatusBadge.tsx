import { VERSION_STATUS_LABELS, VERSION_STATUS_TONES } from "@/modules/assessments/common/labels";
import type { VersionStatus } from "@/modules/assessments/common/types";
import { Badge } from "@/shared/ui";

export function VersionStatusBadge({ status }: { status: VersionStatus }) {
  return <Badge tone={VERSION_STATUS_TONES[status]}>{VERSION_STATUS_LABELS[status]}</Badge>;
}
