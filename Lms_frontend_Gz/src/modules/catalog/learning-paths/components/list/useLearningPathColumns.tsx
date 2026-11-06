import { useMemo } from "react";
import { Link } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { ContentStatusBadge } from "@/modules/catalog/common/components/ContentStatusBadge";
import type { LearningPath } from "@/modules/catalog/learning-paths/types";
import { Button, type Column, Icon } from "@/shared/ui";

export function useLearningPathColumns({ canAuthor, onEdit }: { canAuthor: boolean; onEdit: (path: LearningPath) => void }) {
  return useMemo<Column<LearningPath>[]>(
    () => [
      {
        key: "title",
        header: "Learning path",
        render: (item) => (
          <div className="min-w-0">
            <Link to={`/learning-paths/${item.learning_path_id}`} onClick={(event) => event.stopPropagation()} className="block truncate font-medium text-slate-900 hover:text-brand-700">
              {item.title}
            </Link>
            <p className="truncate text-xs text-slate-500">{item.slug}</p>
          </div>
        ),
      },
      { key: "status", header: "Status", render: (item) => <ContentStatusBadge status={item.status} /> },
      { key: "courses", header: "Courses", hideOnMobile: true, render: (item) => <span className="tabular-nums">{item.items.length}</span> },
      {
        key: "published",
        header: "Published",
        hideOnMobile: true,
        render: (item) => (item.published_at ? formatDate(item.published_at.slice(0, 10)) : "—"),
      },
      {
        key: "actions",
        header: <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        render: (item) =>
          canAuthor && item.status === "draft" ? (
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Edit ${item.title}`}
              onClick={(event) => {
                event.stopPropagation();
                onEdit(item);
              }}
            >
              <Icon name="edit" />
            </Button>
          ) : null,
      },
    ],
    [canAuthor, onEdit],
  );
}
