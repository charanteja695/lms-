import { useMemo } from "react";
import { Link } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { BatchStatusBadge } from "@/modules/learning/common/components/BatchStatusBadge";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import type { Batch } from "@/modules/learning/batches/types";
import type { Column } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function useBatchColumns() {
  const { can } = useCan();
  const showInstitution = can("accounts.manage");
  return useMemo<Column<Batch>[]>(
    () => [
      {
        key: "name",
        header: "Batch",
        render: (item) => (
          <div className="min-w-0">
            <p className="truncate font-medium text-slate-900">{item.name}</p>
            <p className="truncate text-xs text-slate-500">{item.title}</p>
          </div>
        ),
      },
      ...(showInstitution
        ? [{ key: "institution", header: "Institution", hideOnMobile: true, render: (item: Batch) => <InstitutionNameCell organizationId={item.organization_id} /> }]
        : []),
      { key: "status", header: "Status", render: (item) => <BatchStatusBadge status={item.status} /> },
      { key: "created", header: "Created", hideOnMobile: true, render: (item) => formatDate(item.created_at.slice(0, 10)) },
      {
        key: "actions",
        header: "Actions",
        render: (item) => (
          <Link
            to={`/batches/${item.batch_id}`}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-800"
          >
            Manage Roster →
          </Link>
        ),
      },
    ],
    [showInstitution],
  );
}
