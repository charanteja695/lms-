import { formatDate } from "@/core/lib/format";
import { ContactForm } from "@/modules/user-management/account/components/profile/ContactForm";
import { useGetMeQuery } from "@/modules/user-management/auth/api/authApi";
import { RoleBadge } from "@/modules/user-management/common/components/UserBadges";
import { GENDER_LABELS } from "@/modules/user-management/common/labels";
import { Avatar, Card, DescriptionList, PageHeader, PageLoader } from "@/shared/ui";

export function ProfilePage() {
  const { data: me, isLoading } = useGetMeQuery();
  if (isLoading || !me) return <PageLoader />;
  return (
    <>
      <PageHeader title="My profile" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <Avatar name={me.personal_info.full_name} size="lg" />
            <div>
              <p className="text-lg font-semibold text-slate-900">{me.personal_info.full_name}</p>
              <p className="text-sm text-slate-500">{me.account.email}</p>
            </div>
            <RoleBadge role={me.role} />
          </div>
          <DescriptionList
            columns={1}
            items={[
              { label: "Username", value: me.account.username },
              { label: "Institution", value: me.institution?.name },
              { label: "Gender", value: me.personal_info.gender && GENDER_LABELS[me.personal_info.gender] },
              { label: "Date of birth", value: me.personal_info.date_of_birth && formatDate(me.personal_info.date_of_birth) },
              ...(me.employment ? [{ label: "Designation", value: me.employment.designation }, { label: "Employee code", value: me.employment.employee_code }] : []),
              ...(me.student ? [{ label: "Admission number", value: me.student.admission_number }] : []),
            ]}
          />
        </Card>
        <div className="lg:col-span-2">
          <ContactForm me={me} />
        </div>
      </div>
    </>
  );
}
