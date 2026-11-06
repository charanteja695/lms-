import { AccessBadge } from "@/modules/user-management/manage/common/components/AccessBadge";
import { RowActions } from "@/modules/user-management/manage/common/components/RowActions";
import type { PersonKind } from "@/modules/user-management/manage/people/config";
import type { PeopleActions } from "@/modules/user-management/manage/people/hooks/usePeopleActions";
import type { AdminListItem, UserListItem } from "@/modules/user-management/users/types";
import { Avatar, type Column } from "@/shared/ui";

type Row = UserListItem & Partial<Pick<AdminListItem, "institution_count">>;

const dash = (value: string | number | null | undefined) => (value === null || value === undefined || value === "" ? "—" : String(value));

function placement(row: Row) {
  const parts = [row.branch, row.year_of_study ? `Year ${row.year_of_study}` : null, row.section ? `Section ${row.section}` : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

/** Columns differ by screen; name, access and the row buttons are on every one. */
export function usePeopleColumns(kind: PersonKind, actions: PeopleActions): Column<Row>[] {
  const name: Column<Row> = {
    key: "name",
    header: "Name",
    render: (row) => (
      <div className="flex min-w-0 items-center gap-3">
        <Avatar name={row.full_name} size="sm" />
        <div className="min-w-0">
          <p className="truncate font-semibold text-navy-950">{row.full_name}</p>
          <p className="truncate text-[13px] text-slate-500">{row.email ?? `Username: ${row.username}`}</p>
        </div>
      </div>
    ),
  };
  // hidden on phones so the access badge and the row buttons stay on screen
  const institution: Column<Row> = { key: "institution", header: "Institution", render: (row) => dash(row.institution?.name), hideOnMobile: true };

  const middle: Record<PersonKind, Column<Row>[]> = {
    admin: [
      { key: "phone", header: "Phone", render: (row) => dash(row.phone), hideOnMobile: true },
      { key: "institutions", header: "Institutions", render: (row) => dash(row.institution_count), hideOnMobile: true },
    ],
    institution_head: [institution, { key: "code", header: "Employee code", render: (row) => dash(row.employee_code), hideOnMobile: true }],
    staff: [
      institution,
      { key: "phone", header: "Phone", render: (row) => dash(row.phone), hideOnMobile: true },
      { key: "code", header: "Employee code", render: (row) => dash(row.employee_code), hideOnMobile: true },
    ],
    student: [
      institution,
      { key: "admission", header: "Admission no.", render: (row) => dash(row.admission_number), hideOnMobile: true },
      { key: "class", header: "Class", render: placement, hideOnMobile: true },
    ],
  };

  return [
    name,
    ...middle[kind],
    { key: "access", header: "Access", render: (row) => <AccessBadge status={row.status} /> },
    { key: "actions", header: "", render: (row) => <RowActions name={row.full_name} {...actions.handlersFor(row)} /> },
  ];
}
