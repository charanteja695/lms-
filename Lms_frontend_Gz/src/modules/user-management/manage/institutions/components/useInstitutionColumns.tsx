import type { InstitutionListItem } from "@/modules/user-management/institutions/types";
import { AccessBadge } from "@/modules/user-management/manage/common/components/AccessBadge";
import { RowActions } from "@/modules/user-management/manage/common/components/RowActions";
import type { InstitutionRowActions } from "@/modules/user-management/manage/institutions/hooks/useInstitutionRowActions";
import { Icon, type Column } from "@/shared/ui";

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function useInstitutionColumns(actions: InstitutionRowActions): Column<InstitutionListItem>[] {
  return [
    {
      key: "name",
      header: "Institution",
      render: (row) => (
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
            <Icon name="building" size={16} />
          </span>
          <div className="min-w-0">
            <p className="truncate font-semibold text-navy-950">{row.name}</p>
            <p className="truncate text-[13px] text-slate-500">{[row.code, row.city].filter(Boolean).join(" · ")}</p>
          </div>
        </div>
      ),
    },
    { key: "admin", header: "Owner admin", render: (row) => row.admin.full_name, hideOnMobile: true },
    {
      key: "people",
      header: "People",
      hideOnMobile: true,
      render: (row) => {
        const { institution_heads: heads, staff, students } = row.member_counts;
        return (
          <span className="text-slate-600">
            {heads ? count(heads, "head") : <span className="font-medium text-amber-700">No head yet</span>} · {count(staff, "staff", "staff")} · {count(students, "student")}
          </span>
        );
      },
    },
    { key: "access", header: "Access", render: (row) => <AccessBadge status={row.status} /> },
    { key: "actions", header: "", render: (row) => <RowActions name={row.name} {...actions.handlersFor(row)} /> },
  ];
}
