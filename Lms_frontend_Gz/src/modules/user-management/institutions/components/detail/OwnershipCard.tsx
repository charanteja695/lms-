import { Link } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import type { Institution } from "@/modules/user-management/institutions/types";
import { Card, DescriptionList } from "@/shared/ui";

export function OwnershipCard({ institution }: { institution: { admin: Institution["admin"]; created_by: Institution["created_by"]; created_time: string; modified_time: string } }) {
  const { permissions } = usePermissions();
  const admin = institution.admin;
  const linkToAdmin = permissions.admins.view;

  return (
    <Card title="Ownership">
      <DescriptionList
        columns={1}
        items={[
          {
            label: "Admin",
            value: linkToAdmin ? <Link className="text-brand-700 hover:underline" to={`/admins/${admin.user_id}`}>{admin.full_name}</Link> : admin.full_name,
          },
          { label: "Admin email", value: admin.email },
          { label: "Created by", value: institution.created_by?.full_name },
          { label: "Created", value: formatDateTime(institution.created_time) },
          { label: "Last updated", value: formatDateTime(institution.modified_time) },
        ]}
      />
    </Card>
  );
}
