import { useMemo } from "react";

import { formatDateTime } from "@/core/lib/format";
import { VerdictBadge } from "@/modules/code-execution/common/components/VerdictBadge";
import { ProblemTitleCell } from "@/modules/code-execution/problems/components/ProblemTitleCell";
import type { ReviewSubmissionListItem } from "@/modules/code-execution/review/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, type Column, Icon } from "@/shared/ui";

export function useReviewColumns() {
  return useMemo<Column<ReviewSubmissionListItem>[]>(
    () => [
      { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.user_id} /> },
      { key: "problem", header: "Problem", render: (item) => <ProblemTitleCell problemId={item.problem_id} /> },
      { key: "score", header: "Score", hideOnMobile: true, render: (item) => (item.total_count > 0 ? `${item.passed_count}/${item.total_count}` : "—") },
      { key: "verdict", header: "Verdict", render: (item) => <VerdictBadge verdict={item.verdict} /> },
      {
        key: "flag",
        header: "Plagiarism",
        render: (item) =>
          item.flagged ? (
            <Badge tone="red">
              <Icon name="alert" size={12} className="mr-1" />
              {item.similarity_percent}% match
            </Badge>
          ) : null,
      },
      { key: "submitted", header: "Submitted", hideOnMobile: true, render: (item) => formatDateTime(item.created_at) },
    ],
    [],
  );
}
