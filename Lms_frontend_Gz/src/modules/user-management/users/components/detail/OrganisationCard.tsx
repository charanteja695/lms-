import { Link } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import type { UserResource } from "@/modules/user-management/users/api/usersApi";
import { PersonLink } from "@/modules/user-management/users/components/detail/PersonLink";
import type { Admin, User } from "@/modules/user-management/users/types";
import { Card, DescriptionList, type DescriptionItem } from "@/shared/ui";

export function OrganisationCard({ user, resource }: { user: User | Admin; resource: UserResource }) {
  const items: DescriptionItem[] = [];
  if (resource === "admins") {
    const to = `/institutions?admin_user_id=${user.user_id}&admin_label=${encodeURIComponent(user.personal_info.full_name)}`;
    items.push({ label: "Institutions owned", value: <Link className="text-brand-700 hover:underline" to={to}>{(user as Admin).institution_count}</Link> });
  }
  if (user.institution) {
    items.push({ label: "Institution", value: <Link className="text-brand-700 hover:underline" to={`/institutions/${user.institution.organization_id}`}>{user.institution.name}</Link> });
  }
  if (user.manager) items.push({ label: "Reports to", value: <PersonLink person={user.manager} /> });
  items.push(
    { label: "Created by", value: user.created_by ? <PersonLink person={user.created_by} /> : "System" },
    { label: "Created", value: formatDateTime(user.created_time) },
    { label: "Last updated", value: formatDateTime(user.modified_time) },
  );

  return (
    <Card title="Organisation">
      <DescriptionList columns={1} items={items} />
    </Card>
  );
}
