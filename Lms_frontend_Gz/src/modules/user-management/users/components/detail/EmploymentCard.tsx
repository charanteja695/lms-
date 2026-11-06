import { formatDate } from "@/core/lib/format";
import { EMPLOYMENT_TYPE_LABELS } from "@/modules/user-management/common/labels";
import type { User } from "@/modules/user-management/users/types";
import { Card, DescriptionList } from "@/shared/ui";

export function EmploymentCard({ employment }: { employment: NonNullable<User["employment"]> }) {
  return (
    <Card title="Employment">
      <DescriptionList
        items={[
          { label: "Employee code", value: employment.employee_code },
          { label: "Designation", value: employment.designation },
          { label: "Department", value: employment.department },
          { label: "Employment type", value: employment.employment_type && EMPLOYMENT_TYPE_LABELS[employment.employment_type] },
          { label: "Date of joining", value: employment.date_of_joining && formatDate(employment.date_of_joining) },
        ]}
      />
    </Card>
  );
}
