import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { formatDateTime } from "@/core/lib/format";
import { CATEGORY_LINKS } from "@/modules/notifications/common/categoryLinks";
import type { Notification } from "@/modules/notifications/common/types";
import { useMarkReadMutation } from "@/modules/notifications/inbox/api/inboxApi";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { Button } from "@/shared/ui";

export function NotificationItem({ notification: n }: { notification: Notification }) {
  const { can } = usePermissions();
  const [markRead, { isLoading }] = useMarkReadMutation();
  const link = CATEGORY_LINKS[n.category];
  const unread = !n.read_at;

  return (
    <li className={cn("flex gap-3 px-4 py-3", unread && "bg-brand-50/40")}>
      <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", unread ? "bg-brand-600" : "bg-transparent")} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm text-slate-900", unread && "font-semibold")}>{n.title}</p>
        <p className="mt-0.5 whitespace-pre-wrap text-sm text-slate-600">{n.body}</p>
        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span>{formatDateTime(n.created_at)}</span>
          {link && can(link.section) && (
            <Link to={link.to} className="font-medium text-brand-700 hover:underline" onClick={() => unread && void markRead(n.notification_id)}>
              Open {link.label}
            </Link>
          )}
        </div>
      </div>
      {unread && <Button size="sm" variant="ghost" loading={isLoading} onClick={() => void markRead(n.notification_id)}>Mark read</Button>}
    </li>
  );
}
