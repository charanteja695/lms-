import { ROLE_LABELS, ROLE_TONES, STATUS_LABELS, STATUS_TONES } from "@/modules/user-management/common/labels";
import type { Role, UserStatus } from "@/modules/user-management/common/types";
import { Badge } from "@/shared/ui";

export function RoleBadge({ role }: { role: Role }) {
  return <Badge tone={ROLE_TONES[role]}>{ROLE_LABELS[role]}</Badge>;
}

export function StatusBadge({ status }: { status: UserStatus }) {
  return <Badge tone={STATUS_TONES[status]}>{STATUS_LABELS[status]}</Badge>;
}
