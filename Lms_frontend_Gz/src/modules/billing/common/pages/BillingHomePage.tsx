import { Navigate } from "react-router-dom";

import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { EmptyState } from "@/shared/ui";

/** Everyone in billing has invoices; an employer admin's first stop is buying a plan. */
export function BillingHomePage() {
  const { isManager, isContact, isEmployerAdmin } = useBillingRights();
  if (!isManager && !isContact) return <EmptyState icon="ban" title="Billing is handled by your organisation's head or admin" description="Ask them, or a super admin, if you need access." />;
  return <Navigate to={isEmployerAdmin ? "/billing/plans" : "/billing/invoices"} replace />;
}
