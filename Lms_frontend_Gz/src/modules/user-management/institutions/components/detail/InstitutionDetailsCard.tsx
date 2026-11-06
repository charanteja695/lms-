import { INSTITUTION_TYPE_LABELS } from "@/modules/user-management/common/labels";
import type { Institution } from "@/modules/user-management/institutions/types";
import { Card, DescriptionList } from "@/shared/ui";

export function InstitutionDetailsCard({ institution }: { institution: Institution }) {
  const { contact, address } = institution;
  const fullAddress = `${address.line1}${address.line2 ? `, ${address.line2}` : ""}, ${address.city}, ${address.state} ${address.postal_code}, ${address.country}`;
  return (
    <Card title="Details" className="lg:col-span-2">
      <DescriptionList
        items={[
          { label: "Type", value: INSTITUTION_TYPE_LABELS[institution.type] },
          { label: "Email", value: contact.email },
          { label: "Phone", value: contact.phone },
          { label: "Alternate phone", value: contact.alternate_phone },
          {
            label: "Website",
            value: contact.website && (
              <a className="text-brand-700 hover:underline" href={contact.website} target="_blank" rel="noreferrer noopener">
                {contact.website}
              </a>
            ),
          },
          { label: "Affiliation", value: institution.affiliation },
          { label: "Registration number", value: institution.registration_number },
          { label: "Established", value: institution.established_year },
          { label: "Time zone", value: institution.timezone },
          { label: "Address", span: 2, value: fullAddress },
        ]}
      />
    </Card>
  );
}
