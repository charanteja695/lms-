import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { SectionTabs } from "@/shared/ui";

/** The billing pages this person may use, as tabs. */
export function BillingTabs() {
  const { isManager, isContact, isEmployerAdmin, canQuote } = useBillingRights();
  return (
    <SectionTabs
      tabs={[
        { to: "/billing/subscription-plans", label: "Subscription Plans", icon: "creditCard", show: isManager },
        { to: "/billing/transactions", label: "Transactions", icon: "fileText", show: isManager },
        { to: "/billing/reports", label: "Reports", icon: "chart", show: isManager },
        { to: "/billing/plans", label: "Plans", icon: "briefcase", show: isEmployerAdmin },
        { to: "/billing/invoices", label: "Invoices", icon: "fileText" },
        { to: "/billing/quotes", label: "Quotes", icon: "edit", show: canQuote },
        { to: "/billing/prices", label: "Prices", icon: "layers", show: isManager },
        { to: "/billing/profile", label: "Billing profile", icon: "building", show: isContact },
      ]}
    />
  );
}
