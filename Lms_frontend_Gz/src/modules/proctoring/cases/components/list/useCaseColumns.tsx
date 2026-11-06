import { useMemo } from "react";

import { formatDateTime } from "@/core/lib/format";
import { CaseSeverityBadge } from "@/modules/proctoring/common/components/CaseSeverityBadge";
import { CaseStatusBadge } from "@/modules/proctoring/common/components/CaseStatusBadge";
import type { ProctorCase } from "@/modules/proctoring/cases/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, type Column } from "@/shared/ui";

export function useCaseColumns() {
  return useMemo<Column<ProctorCase>[]>(
    () => [
      { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.user_id} /> },
      { key: "test", header: "Test", hideOnMobile: true, render: (item) => item.test_title ?? "—" },
      { key: "status", header: "Status", render: (item) => <CaseStatusBadge status={item.status} /> },
      { key: "severity", header: "Severity", render: (item) => <CaseSeverityBadge severity={item.severity} /> },
      { key: "risk", header: "Risk", hideOnMobile: true, render: (item) => item.risk_score },
      { key: "overdue", header: "", render: (item) => (item.overdue ? <Badge tone="red">Overdue</Badge> : null) },
      { key: "created", header: "Opened", hideOnMobile: true, render: (item) => formatDateTime(item.created_at) },
    ],
    [],
  );
}
