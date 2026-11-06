import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useBuyCourseMutation, useConfirmPurchaseMutation } from "@/modules/store/api/storeApi";
import { useRazorpayCheckout } from "@/modules/store/hooks/useRazorpayCheckout";
import type { StoreOffer } from "@/modules/store/types";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";

/** Buy -> Razorpay's window -> the server verifies the payment -> the course opens in My learning. */
export function useBuyCourse() {
  const notify = useNotify();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [startPurchase] = useBuyCourseMutation();
  const [confirm] = useConfirmPurchaseMutation();
  const openCheckout = useRazorpayCheckout();
  const [busy, setBusy] = useState<string | null>(null);

  const buy = async (offer: StoreOffer) => {
    if (!user) return;
    setBusy(offer.course_id);
    try {
      const name = user.full_name;
      const email = user.email || null;
      const { purchase, checkout } = await startPurchase({ courseId: offer.course_id, name, email }).unwrap();
      const outcome = await openCheckout(checkout, { description: offer.name, name, email });
      if (outcome.status === "closed") {
        notify.info("Payment cancelled. You can buy it any time.");
        return;
      }
      if (outcome.status === "failed") {
        notify.error(outcome.reason);
        return;
      }
      const confirmed = await confirm({ purchaseId: purchase.purchase_id, ...outcome.result }).unwrap();
      notify.success(confirmed.status === "paid" ? `${offer.name} is yours: it opens in My learning within moments.` : "Payment received: confirming it now.");
      navigate("/my-learning");
    } catch (error) {
      notify.apiError(error, "The purchase could not be completed");
    } finally {
      setBusy(null);
    }
  };

  return { buy, busy };
}
