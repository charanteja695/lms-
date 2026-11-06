import { useNotificationRights } from "@/modules/notifications/common/hooks/useNotificationRights";
import { SectionTabs } from "@/shared/ui";

/** Inbox and email preferences for everyone; templates and deliveries for a super admin. */
export function NotificationsTabs() {
  const { isSuperAdmin } = useNotificationRights();
  return (
    <SectionTabs
      tabs={[
        { to: "/notifications", label: "Inbox", icon: "bell" },
        { to: "/notifications/preferences", label: "Email preferences", icon: "mail" },
        { to: "/notifications/templates", label: "Templates", icon: "fileText", show: isSuperAdmin },
        { to: "/notifications/deliveries", label: "Deliveries", icon: "refresh", show: isSuperAdmin },
      ]}
    />
  );
}
