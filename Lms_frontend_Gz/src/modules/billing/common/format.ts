import { formatMinor } from "@/core/lib/money";

/** Billing amounts are paise; every invoice is in rupees. */
export const inr = (paise: number | null | undefined) => formatMinor(paise, "INR");

/** Rupees typed in a form -> paise for the API (rounded to the paisa). */
export const toPaise = (rupees: string) => Math.round(Number(rupees) * 100);
