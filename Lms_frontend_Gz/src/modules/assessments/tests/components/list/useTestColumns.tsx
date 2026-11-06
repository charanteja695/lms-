import { useMemo } from "react";
import { Link } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { TEST_KIND_LABELS } from "@/modules/assessments/common/labels";
import { TestStatusBadge } from "@/modules/assessments/common/components/TestStatusBadge";
import type { TestListItem } from "@/modules/assessments/tests/types";
import type { Column } from "@/shared/ui";

export function useTestColumns() {
  return useMemo<Column<TestListItem>[]>(
    () => [
      {
        key: "title",
        header: "Test",
        render: (item) => (
          <Link to={`/tests/${item.test_id}`} onClick={(event) => event.stopPropagation()} className="font-medium text-slate-900 hover:text-brand-700">
            {item.title}
          </Link>
        ),
      },
      { key: "kind", header: "Kind", hideOnMobile: true, render: (item) => TEST_KIND_LABELS[item.kind] },
      { key: "questions", header: "Questions", hideOnMobile: true, render: (item) => item.question_count ?? "—" },
      { key: "marks", header: "Marks", hideOnMobile: true, render: (item) => item.total_marks ?? "—" },
      { key: "status", header: "Status", render: (item) => <TestStatusBadge status={item.status} /> },
      { key: "published", header: "Published", hideOnMobile: true, render: (item) => (item.published_at ? formatDate(item.published_at.slice(0, 10)) : "—") },
    ],
    [],
  );
}
