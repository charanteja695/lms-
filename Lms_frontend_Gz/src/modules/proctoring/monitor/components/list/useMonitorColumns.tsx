import { useMemo } from "react";

import { formatRelative } from "@/core/lib/format";
import { SessionStatusBadge } from "@/modules/proctoring/common/components/SessionStatusBadge";
import type { MonitorSession } from "@/modules/proctoring/monitor/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, type Column } from "@/shared/ui";

function riskTone(score: number) {
  if (score >= 75) return "red" as const;
  if (score >= 50) return "amber" as const;
  return "gray" as const;
}

export function useMonitorColumns() {
  return useMemo<Column<MonitorSession>[]>(
    () => [
      { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.user_id} /> },
      { key: "test", header: "Test", hideOnMobile: true, render: (item) => item.test_title ?? "—" },
      { key: "level", header: "Level", hideOnMobile: true, render: (item) => item.level },
      { key: "status", header: "Status", render: (item) => <SessionStatusBadge status={item.status} /> },
      { key: "risk", header: "Risk", render: (item) => <Badge tone={riskTone(item.risk_score)}>{item.risk_score}</Badge> },
      { key: "critical", header: "", render: (item) => (item.critical ? <Badge tone="red">Critical</Badge> : null) },
      { key: "heartbeat", header: "Last heartbeat", hideOnMobile: true, render: (item) => formatRelative(item.last_heartbeat_at) },
    ],
    [],
  );
}
