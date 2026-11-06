import { Link } from "react-router-dom";

import { env } from "@/core/config/env";
import { useGetUnreadCountQuery } from "@/modules/notifications/inbox/api/inboxApi";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { Icon } from "@/shared/ui";

/** Header bell: the unread count, re-checked every VITE_NOTIFICATION_POLL_SECONDS while the tab is focused. */
export function NotificationBell() {
  const { can } = usePermissions();
  const allowed = can("notifications");
  const { data: unread = 0 } = useGetUnreadCountQuery(undefined, { skip: !allowed, pollingInterval: env.notificationPollMs, skipPollingIfUnfocused: true });
  if (!allowed) return null;

  return (
    <Link to="/notifications" className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}>
      <Icon name="bell" />
      {unread > 0 && (
        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-500 px-1 text-[10px] font-semibold leading-none text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
