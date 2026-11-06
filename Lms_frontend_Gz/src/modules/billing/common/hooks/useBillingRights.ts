import { useCan } from "@/modules/user-management/common/permissions/useCan";

/**
 * Mirrors billing-service's policy.py: an institution head or employer admin handles their own organisation's billing
 * (heads ask for course quotes, employer admins buy plans); `billing.manage` (or super admin) handles everyone's.
 */
export function useBillingRights() {
  const { can, holds, acts, organizationType } = useCan();
  const isManager = can("billing.manage");
  /** Sees their organisation's invoices and quotes (the Billing page's View cell). */
  const isContact = acts("billing.view", "billing.contact");
  /** Edits the billing profile, asks for and accepts quotes, pays (the Update cell). */
  const canUpdate = acts("billing.update", "billing.contact");
  const isHead = canUpdate && organizationType === "institution";
  return { isManager, isHead, isEmployerAdmin: holds("billing.plans.buy"), isContact, canUpdate, canQuote: (isContact && organizationType === "institution") || isManager };
}

