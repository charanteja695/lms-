import type { UserStatus } from "@/modules/user-management/common/types";
import { Badge } from "@/shared/ui";

/** Whether the person or institution can sign in: "Active", or "Access revoked" after a suspend. */
export function AccessBadge({ status }: { status: UserStatus }) {
  if (status === "active") return <Badge tone="green">Active</Badge>;
  if (status === "suspended") return <Badge tone="amber">Access revoked</Badge>;
  return <Badge tone="red">Deleted</Badge>;
}
