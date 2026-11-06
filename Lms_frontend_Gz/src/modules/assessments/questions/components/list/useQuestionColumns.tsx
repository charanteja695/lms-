import { useMemo } from "react";
import { Link } from "react-router-dom";

import { QUESTION_TYPE_LABELS } from "@/modules/assessments/common/labels";
import { VersionStatusBadge } from "@/modules/assessments/common/components/VersionStatusBadge";
import type { QuestionListItem } from "@/modules/assessments/questions/types";
import { Badge, type Column } from "@/shared/ui";

export function useQuestionColumns() {
  return useMemo<Column<QuestionListItem>[]>(
    () => [
      {
        key: "text",
        header: "Question",
        render: (item) => (
          <div className="min-w-0">
            <Link to={`/questions/${item.question_id}`} onClick={(event) => event.stopPropagation()} className="block truncate font-medium text-slate-900 hover:text-brand-700">
              {item.text}
            </Link>
            {item.tags.length > 0 && <p className="truncate text-xs text-slate-500">{item.tags.join(", ")}</p>}
          </div>
        ),
      },
      { key: "type", header: "Type", hideOnMobile: true, render: (item) => QUESTION_TYPE_LABELS[item.question_type] },
      { key: "difficulty", header: "Difficulty", hideOnMobile: true, render: (item) => `${item.difficulty}/5` },
      { key: "marks", header: "Marks", hideOnMobile: true, render: (item) => item.default_marks },
      { key: "status", header: "Status", render: (item) => <VersionStatusBadge status={item.latest_version_status} /> },
      { key: "retired", header: "", render: (item) => (item.status === "retired" ? <Badge tone="red">Retired</Badge> : null) },
    ],
    [],
  );
}
