import { Link } from "react-router-dom";

import type { User } from "@/modules/user-management/users/types";
import { Icon } from "@/shared/ui";

export function PersonLink({ person }: { person: NonNullable<User["manager"]> }) {
  const path = person.role === "admin" ? `/admins/${person.user_id}` : person.role === "super_admin" ? null : `/users/${person.user_id}`;
  return path ? (
    <Link to={path} className="inline-flex items-center gap-1 text-brand-700 hover:underline">
      {person.full_name}
      <Icon name="chevronRight" size={14} />
    </Link>
  ) : (
    <span>{person.full_name}</span>
  );
}
