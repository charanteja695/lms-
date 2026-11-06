import { formatDateTime } from "@/core/lib/format";
import { CaseSeverityBadge } from "@/modules/proctoring/common/components/CaseSeverityBadge";
import { CaseStatusBadge } from "@/modules/proctoring/common/components/CaseStatusBadge";
import type { ProctorCaseDetail } from "@/modules/proctoring/cases/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Card, DescriptionList } from "@/shared/ui";

export function CaseOverviewCard({ proctorCase }: { proctorCase: ProctorCaseDetail }) {
  return (
    <Card title="Overview">
      <DescriptionList
        items={[
          { label: "Student", value: <UserNameCell userId={proctorCase.user_id} /> },
          { label: "Test", value: proctorCase.test_title ?? "—" },
          { label: "Status", value: <CaseStatusBadge status={proctorCase.status} /> },
          { label: "Severity", value: <CaseSeverityBadge severity={proctorCase.severity} /> },
          { label: "Risk score", value: proctorCase.risk_score },
          { label: "Overdue", value: proctorCase.overdue ? <Badge tone="red">Yes</Badge> : "No" },
          { label: "Assigned to", value: proctorCase.assigned_to ? <UserNameCell userId={proctorCase.assigned_to} /> : "Unclaimed" },
          { label: "Reasons", value: proctorCase.reasons.length ? proctorCase.reasons.join("; ") : "—", span: 2 },
          { label: "Opened", value: formatDateTime(proctorCase.created_at) },
          { label: "Decision", value: proctorCase.decision ?? "—" },
          { label: "Decided by", value: proctorCase.decided_by ? <UserNameCell userId={proctorCase.decided_by} /> : "—" },
          { label: "Decided at", value: proctorCase.decided_at ? formatDateTime(proctorCase.decided_at) : "—" },
          { label: "Decision note", value: proctorCase.decision_note ?? "—", span: 2 },
          { label: "Appeal status", value: proctorCase.appeal_status },
          { label: "Appeal reason", value: proctorCase.appeal_reason ?? "—", span: 2 },
          { label: "Appeal note", value: proctorCase.appeal_note ?? "—", span: 2 },
        ]}
      />
    </Card>
  );
}
