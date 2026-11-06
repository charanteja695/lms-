import { useMemo } from "react";

import { formatDate } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { SubscriptionStatusBadge } from "@/modules/subscriptions/common/components/SubscriptionStatusBadge";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import type { Subscription } from "@/modules/subscriptions/subscriptions/types";
import type { Column } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function useSubscriptionColumns() {
  const { can } = useCan();
  const showInstitution = can("accounts.manage");
  return useMemo<Column<Subscription>[]>(
    () => [
      { key: "course", header: "Course", render: (item) => <CourseTitleCell courseId={item.course_id} /> },
      ...(showInstitution
        ? [{ key: "institution", header: "Institution", hideOnMobile: true, render: (item: Subscription) => <InstitutionNameCell organizationId={item.organization_id} /> }]
        : []),
      {
        key: "seats",
        header: "Seats used",
        hideOnMobile: true,
        render: (item) => (
          <span className="tabular-nums" title={`${item.seats_used} of ${item.seats_total}`}>
            {item.seats_used.toLocaleString()} / {item.seats_total.toLocaleString()}
          </span>
        ),
      },
      { key: "status", header: "Status", render: (item) => <SubscriptionStatusBadge status={item.status} /> },
      { key: "ends", header: "Ends", hideOnMobile: true, render: (item) => formatDate(item.ends_at.slice(0, 10)) },
    ],
    [showInstitution],
  );
}
