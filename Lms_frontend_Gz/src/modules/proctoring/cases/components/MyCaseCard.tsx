import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useState } from "react";

import { formatDateTime } from "@/core/lib/format";
import { AppealCaseDialog } from "@/modules/proctoring/cases/components/AppealCaseDialog";
import { CaseStatusBadge } from "@/modules/proctoring/common/components/CaseStatusBadge";
import type { StudentCase } from "@/modules/proctoring/cases/types";
import { Button, Card } from "@/shared/ui";

export function MyCaseCard({ studentCase }: { studentCase: StudentCase }) {
  const [appealing, setAppealing] = useState(false);
  const { acts } = useCan();

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-navy-950">{studentCase.test_title ?? "A proctored test"}</p>
          <p className="text-sm text-slate-500">Opened {formatDateTime(studentCase.created_at)}</p>
          {studentCase.decision && <p className="mt-1 text-sm text-slate-700">Decision: {studentCase.decision.replace(/_/g, " ")}</p>}
          {studentCase.decision_note && <p className="mt-1 text-sm text-slate-600">{studentCase.decision_note}</p>}
          {studentCase.appeal_status !== "none" && <p className="mt-1 text-xs text-slate-500">Appeal: {studentCase.appeal_status}</p>}
        </div>
        <div className="flex flex-col items-end gap-2">
          <CaseStatusBadge status={studentCase.status} />
          {studentCase.can_appeal && acts("exam_reviews.create", "proctoring.take") && (
            <Button variant="secondary" size="sm" onClick={() => setAppealing(true)}>
              Appeal
            </Button>
          )}
        </div>
      </div>
      <AppealCaseDialog open={appealing} onClose={() => setAppealing(false)} caseId={studentCase.case_id} />
    </Card>
  );
}
