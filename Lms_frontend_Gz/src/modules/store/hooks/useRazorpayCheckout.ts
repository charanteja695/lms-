import { useCallback } from "react";

import type { Checkout } from "@/modules/store/types";

const SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

interface RazorpayResult {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open: () => void;
  on: (event: "payment.failed", handler: (response: { error?: { description?: string } }) => void) => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

let loading: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  loading ??= new Promise((resolve, reject) => {
    const tag = document.createElement("script");
    tag.src = SCRIPT;
    tag.async = true;
    tag.onload = () => resolve();
    tag.onerror = () => {
      loading = null;
      reject(new Error("The payment window could not be loaded. Check your connection and try again."));
    };
    document.body.appendChild(tag);
  });
  return loading;
}

export type CheckoutOutcome = { status: "paid"; result: RazorpayResult } | { status: "closed" } | { status: "failed"; reason: string };

/** Opens Razorpay's checkout for an order the server created; resolves with what the learner did. */
export function useRazorpayCheckout() {
  return useCallback(async (checkout: Checkout, details: { description: string; name: string; email?: string | null }): Promise<CheckoutOutcome> => {
    await loadScript();
    const Razorpay = window.Razorpay;
    if (!Razorpay || !checkout.key_id) return { status: "failed", reason: "Online payment is not available right now." };
    return new Promise<CheckoutOutcome>((resolve) => {
      let settled = false;
      const done = (outcome: CheckoutOutcome) => {
        if (!settled) {
          settled = true;
          resolve(outcome);
        }
      };
      const instance = new Razorpay({
        key: checkout.key_id,
        order_id: checkout.order_id,
        amount: checkout.amount,
        currency: checkout.currency,
        name: checkout.seller_name,
        description: details.description,
        prefill: { name: details.name, email: details.email ?? undefined },
        theme: { color: getComputedStyle(document.documentElement).getPropertyValue("--color-brand-700").trim() || undefined },
        handler: (result: RazorpayResult) => done({ status: "paid", result }),
        modal: { ondismiss: () => done({ status: "closed" }) },
      });
      instance.on("payment.failed", (response) => done({ status: "failed", reason: response.error?.description ?? "The payment did not go through." }));
      instance.open();
    });
  }, []);
}
