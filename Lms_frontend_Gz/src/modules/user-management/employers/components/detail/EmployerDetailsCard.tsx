import type { Employer } from "@/modules/user-management/employers/types";
import { Card, DescriptionList } from "@/shared/ui";

export function EmployerDetailsCard({ employer }: { employer: Employer }) {
  const { contact, address } = employer;
  const fullAddress = `${address.line1}${address.line2 ? `, ${address.line2}` : ""}, ${address.city}, ${address.state} ${address.postal_code}, ${address.country}`;
  return (
    <Card title="Details" className="lg:col-span-2">
      <DescriptionList
        items={[
          { label: "Industry", value: employer.industry },
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
          { label: "Registration number", value: employer.registration_number },
          { label: "Established", value: employer.established_year },
          { label: "Time zone", value: employer.timezone },
          { label: "Address", span: 2, value: fullAddress },
        ]}
      />
    </Card>
  );
}
