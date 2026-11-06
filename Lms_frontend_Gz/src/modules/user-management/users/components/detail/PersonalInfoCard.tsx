import { LANGUAGES } from "@/core/constants/locale";
import { formatDate } from "@/core/lib/format";
import { GENDER_LABELS } from "@/modules/user-management/common/labels";
import type { User } from "@/modules/user-management/users/types";
import { Card, DescriptionList } from "@/shared/ui";

export function PersonalInfoCard({ user }: { user: User }) {
  const info = user.personal_info;
  const language = LANGUAGES.find((option) => option.value === info.preferred_language.split("-")[0])?.label ?? info.preferred_language;
  return (
    <Card title="Personal information">
      <DescriptionList
        items={[
          { label: "Full name", value: info.full_name },
          { label: "Gender", value: info.gender ? GENDER_LABELS[info.gender] : null },
          { label: "Date of birth", value: info.date_of_birth && formatDate(info.date_of_birth) },
          { label: "Phone", value: info.phone },
          { label: "Alternate phone", value: info.alternate_phone },
          { label: "Language", value: language },
          { label: "Time zone", value: info.timezone },
        ]}
      />
    </Card>
  );
}
