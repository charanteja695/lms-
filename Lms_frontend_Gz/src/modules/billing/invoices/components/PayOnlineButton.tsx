import { useNotify } from "@/core/hooks/useNotify";
import { inr } from "@/modules/billing/common/format";
import type { InvoiceDetail } from "@/modules/billing/common/types";
import { usePayOnlineMutation } from "@/modules/billing/invoices/api/invoicesApi";
import { Button } from "@/shared/ui";

/**
 * Opens a payment-provider order for what is still owed. The service only creates the order (its README: "a contract
 * only"); the provider's checkout and webhook complete it. With no provider configured the server says so (503).
 */
export function PayOnlineButton({ invoice }: { invoice: InvoiceDetail }) {
  const notify = useNotify();
  const [pay, { isLoading }] = usePayOnlineMutation();
  if (!(invoice.status === "issued" || invoice.status === "overdue") || invoice.balance_due <= 0) return null;
  return (
    <Button icon="check" loading={isLoading} onClick={() => void pay({ id: invoice.invoice_id }).unwrap().then((o) => notify.success(`Payment order ${o.order_id} for ${inr(o.amount)} created`), notify.apiError)}>
      Pay {inr(invoice.balance_due)} online
    </Button>
  );
}
