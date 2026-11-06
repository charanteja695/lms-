import { useMemo } from "react";

import { formatDateTime } from "@/core/lib/format";
import { AttemptResultBadge } from "@/modules/assessments/common/components/AttemptResultBadge";
import { AttemptStatusBadge } from "@/modules/assessments/common/components/AttemptStatusBadge";
import { IntegrityStatusBadge } from "@/modules/assessments/common/components/IntegrityStatusBadge";
import type { AttemptListItem } from "@/modules/assessments/attempts/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, type Column } from "@/shared/ui";

export function useAttemptColumns() {
  return useMemo<Column<AttemptListItem>[]>(
    () => [
      { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.user_id} /> },
      { key: "attempt", header: "Attempt", hideOnMobile: true, render: (item) => `#${item.attempt_no}` },
      { key: "status", header: "Status", render: (item) => <AttemptStatusBadge status={item.status} /> },
      { key: "result", header: "Result", render: (item) => <AttemptResultBadge result={item.result} /> },
      { key: "score", header: "Score", hideOnMobile: true, render: (item) => (item.percent != null ? `${item.percent.toFixed(0)}%` : "—") },
      { key: "integrity", header: "Integrity", hideOnMobile: true, render: (item) => <IntegrityStatusBadge status={item.integrity_status} /> },
      { key: "flagged", header: "", render: (item) => (item.plagiarism_flagged ? <Badge tone="red">Flagged</Badge> : null) },
      { key: "submitted", header: "Submitted", hideOnMobile: true, render: (item) => (item.submitted_at ? formatDateTime(item.submitted_at) : "—") },
    ],
    [],
  );
}
