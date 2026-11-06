import { formatDateTime, formatRelative } from "@/core/lib/format";
import type { User } from "@/modules/user-management/users/types";
import { Badge, Card, DescriptionList } from "@/shared/ui";

export function AccountCard({ user }: { user: User }) {
  const { account } = user;
  return (
    <Card title="Account">
      <DescriptionList
        columns={1}
        items={[
          {
            label: "Email",
            value: (
              <span className="flex items-center gap-2">
                {account.email}
                {account.email_verified ? <Badge tone="green">Verified</Badge> : <Badge>Unverified</Badge>}
              </span>
            ),
          },
          { label: "Username", value: account.username },
          { label: "Last active", value: account.last_login_time ? formatRelative(account.last_login_time) : "Never signed in" },
          { label: "Password changed", value: formatDateTime(account.password_changed_time) },
        ]}
      />
    </Card>
  );
}
