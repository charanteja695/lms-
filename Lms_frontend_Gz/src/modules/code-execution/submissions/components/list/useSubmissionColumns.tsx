import { useMemo } from "react";

import { formatDateTime } from "@/core/lib/format";
import { VerdictBadge } from "@/modules/code-execution/common/components/VerdictBadge";
import { ProblemTitleCell } from "@/modules/code-execution/problems/components/ProblemTitleCell";
import type { SubmissionListItem } from "@/modules/code-execution/submissions/types";
import type { Column } from "@/shared/ui";

export function useSubmissionColumns() {
  return useMemo<Column<SubmissionListItem>[]>(
    () => [
      { key: "problem", header: "Problem", render: (item) => <ProblemTitleCell problemId={item.problem_id} /> },
      { key: "language", header: "Language", hideOnMobile: true, render: (item) => item.language },
      { key: "score", header: "Score", hideOnMobile: true, render: (item) => (item.total_count > 0 ? `${item.passed_count}/${item.total_count}` : "—") },
      { key: "verdict", header: "Verdict", render: (item) => <VerdictBadge verdict={item.verdict} /> },
      { key: "submitted", header: "Submitted", hideOnMobile: true, render: (item) => formatDateTime(item.created_at) },
    ],
    [],
  );
}
