import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useClaimCaseMutation } from "@/modules/proctoring/cases/api/casesApi";
import { DecideAppealDialog } from "@/modules/proctoring/cases/components/detail/DecideAppealDialog";
import { DecideCaseDialog } from "@/modules/proctoring/cases/components/detail/DecideCaseDialog";
import type { ProctorCaseDetail } from "@/modules/proctoring/cases/types";
import { Button } from "@/shared/ui";

export function CaseDecisionActions({ proctorCase }: { proctorCase: ProctorCaseDetail }) {
  const notify = useNotify();
  const [claim, { isLoading: claiming }] = useClaimCaseMutation();
  const [deciding, setDeciding] = useState(false);
  const [decidingAppeal, setDecidingAppeal] = useState(false);

  const openForDecision = proctorCase.status === "open" || proctorCase.status === "under_review";

  return (
    <div className="flex flex-wrap items-center gap-2">
      {openForDecision && (
        <Button
          variant="secondary"
          icon="user"
          loading={claiming}
          onClick={async () => {
            try {
              await claim(proctorCase.case_id).unwrap();
              notify.success("Case claimed");
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          Claim
        </Button>
      )}
      {openForDecision && <Button onClick={() => setDeciding(true)}>Decide</Button>}
      {proctorCase.status === "appealed" && (
        <Button variant="secondary" onClick={() => setDecidingAppeal(true)}>
          Decide appeal
        </Button>
      )}
      <DecideCaseDialog open={deciding} onClose={() => setDeciding(false)} caseId={proctorCase.case_id} />
      <DecideAppealDialog open={decidingAppeal} onClose={() => setDecidingAppeal(false)} caseId={proctorCase.case_id} />
    </div>
  );
}
