import { useMemo } from "react";
import { Link } from "react-router-dom";

import { DifficultyBadge } from "@/modules/code-execution/common/components/DifficultyBadge";
import { ProblemStatusBadge } from "@/modules/code-execution/common/components/ProblemStatusBadge";
import { PROBLEM_TYPE_LABELS } from "@/modules/code-execution/common/labels";
import type { ProblemListItem } from "@/modules/code-execution/problems/types";
import { Badge, type Column, Icon } from "@/shared/ui";

export function useProblemColumns({ canAuthor }: { canAuthor: boolean }) {
  return useMemo<Column<ProblemListItem>[]>(
    () => [
      {
        key: "title",
        header: "Problem",
        render: (item) => (
          <div className="min-w-0">
            <Link to={`/problems/${item.problem_id}`} onClick={(event) => event.stopPropagation()} className="block truncate font-medium text-slate-900 hover:text-brand-700">
              {item.title}
            </Link>
            {item.tags.length > 0 && <p className="truncate text-xs text-slate-500">{item.tags.join(", ")}</p>}
          </div>
        ),
      },
      { key: "type", header: "Type", hideOnMobile: true, render: (item) => PROBLEM_TYPE_LABELS[item.problem_type] },
      { key: "difficulty", header: "Difficulty", render: (item) => <DifficultyBadge difficulty={item.difficulty} /> },
      ...(canAuthor ? [{ key: "status", header: "Status", render: (item: ProblemListItem) => <ProblemStatusBadge status={item.status} /> }] : []),
      {
        key: "progress",
        header: "Progress",
        className: "w-28",
        render: (item) =>
          item.solved ? (
            <Badge tone="green">
              <Icon name="check" size={12} className="mr-1" />
              Solved
            </Badge>
          ) : item.attempted ? (
            <Badge tone="amber">Attempted</Badge>
          ) : null,
      },
    ],
    [canAuthor],
  );
}
