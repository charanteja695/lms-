import { useMemo } from "react";
import { Link } from "react-router-dom";

import { formatRelative } from "@/core/lib/format";
import { RoleBadge, StatusBadge } from "@/modules/user-management/common/components/UserBadges";
import type { UserResource } from "@/modules/user-management/users/api/usersApi";
import type { useUserActions } from "@/modules/user-management/users/hooks/useUserActions";
import type { AdminListItem, UserListItem } from "@/modules/user-management/users/types";
import { Avatar, Button, type Column, Icon, Menu } from "@/shared/ui";

type Row = UserListItem | AdminListItem;

/** Table columns for the users and admins lists. */
export function useUserColumns(resource: UserResource, actions: ReturnType<typeof useUserActions>) {
  const isAdmins = resource === "admins";
  return useMemo<Column<Row>[]>(
    () => [
      {
        key: "name",
        header: "Name",
        render: (user) => (
          <div className="flex items-center gap-3">
            <Avatar name={user.full_name} size="sm" />
            <div className="min-w-0">
              <Link to={`/${resource}/${user.user_id}`} onClick={(event) => event.stopPropagation()} className="block truncate font-medium text-slate-900 hover:text-brand-700">
                {user.full_name}
              </Link>
              <p className="truncate text-xs text-slate-500">{user.email ?? user.username}</p>
            </div>
          </div>
        ),
      },
      ...(!isAdmins ? [{ key: "role", header: "Role", render: (user: Row) => <RoleBadge role={user.role} /> }] : []),
      isAdmins
        ? {
            key: "organizations",
            header: "Owns",
            hideOnMobile: true,
            render: (user) => {
              const admin = user as AdminListItem;
              return `${admin.institution_count} institution(s) · ${admin.employer_count} employer(s)`;
            },
          }
        : { key: "institution", header: "Organisation", hideOnMobile: true, render: (user) => user.institution?.name ?? "—" },
      ...(!isAdmins
        ? [
            {
              key: "code",
              header: "Code / class",
              hideOnMobile: true,
              render: (user: Row) => {
                if (user.employee_code) return user.employee_code;
                const studentParts = [
                  user.admission_number,
                  [user.branch, user.section ? `Sec ${user.section}` : null].filter(Boolean).join(" "),
                  user.cgpa ? `CGPA: ${Number(user.cgpa).toFixed(2)}` : null,
                ].filter(Boolean);
                return studentParts.length > 0 ? studentParts.join(" · ") : "—";
              },
            },
          ]
        : []),
      { key: "status", header: "Status", render: (user) => <StatusBadge status={user.status} /> },
      { key: "last_login", header: "Last active", hideOnMobile: true, render: (user) => <span className="whitespace-nowrap">{formatRelative(user.last_login_time)}</span> },
      {
        key: "actions",
        header: <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        render: (user) => (
          <Menu
            trigger={
              <Button variant="ghost" size="icon" aria-label={`Actions for ${user.full_name}`}>
                <Icon name="more" />
              </Button>
            }
            items={actions.itemsFor(user, { includeView: true })}
          />
        ),
      },
    ],
    [actions, isAdmins, resource],
  );
}
