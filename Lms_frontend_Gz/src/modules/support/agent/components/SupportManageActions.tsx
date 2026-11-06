import { useLocation, useNavigate } from "react-router-dom";

import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { Button, type IconName } from "@/shared/ui";

/** Header links between the agent screens, showing only the ones this agent can open. */
export function SupportManageActions() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const rights = useSupportRights();
  const links: Array<{ to: string; label: string; icon: IconName; show: boolean }> = [
    { to: "/support/queue", label: "Queue", icon: "mail", show: true },
    { to: "/support/reports", label: "SLA report", icon: "clock", show: true },
    { to: "/support/canned-replies", label: "Canned replies", icon: "fileText", show: true },
    { to: "/support/sla-policies", label: "SLA policies", icon: "shield", show: rights.isManager },
  ];
  return (
    <>
      {links
        .filter((link) => link.show && pathname !== link.to)
        .map((link) => (
          <Button key={link.to} variant="secondary" icon={link.icon} onClick={() => navigate(link.to)}>
            {link.label}
          </Button>
        ))}
    </>
  );
}
