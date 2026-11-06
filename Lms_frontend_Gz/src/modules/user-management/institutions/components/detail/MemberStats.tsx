import type { Institution } from "@/modules/user-management/institutions/types";
import { StatTile } from "@/shared/ui";

/** Member counts; the tiles open the filtered users list when the viewer may see members. */
export function MemberStats({ institution }: { institution: Institution }) {
  const counts = institution.member_counts;
  const canOpen = institution.allowed_actions.includes("view_members");
  const usersLink = (roleFilter?: string) =>
    `/users?organization_id=${institution.organization_id}&organization_label=${encodeURIComponent(institution.name)}${roleFilter ? `&role=${roleFilter}` : ""}`;

  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile icon="users" label="Total members" value={counts.total} to={canOpen ? usersLink() : undefined} />
      <StatTile icon="shield" label="Institution heads" value={counts.institution_heads} to={canOpen ? usersLink("institution_head") : undefined} />
      <StatTile icon="briefcase" label="Staff" value={counts.staff} to={canOpen ? usersLink("staff") : undefined} />
      <StatTile icon="graduation" label="Students" value={counts.students} to={canOpen ? usersLink("student") : undefined} />
    </div>
  );
}
