import type { Address } from "@/modules/user-management/common/types";
import { Card } from "@/shared/ui";

export function AddressCard({ address }: { address: Address }) {
  return (
    <Card title="Address">
      <p className="text-sm leading-6 text-slate-800">
        {address.line1}
        {address.line2 && <>, {address.line2}</>}
        <br />
        {address.city}, {address.state} {address.postal_code}
        <br />
        {address.country}
      </p>
    </Card>
  );
}
