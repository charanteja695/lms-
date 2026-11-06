/** An amount in a currency's minor unit (paise, cents) as display money, e.g. 1234567 INR -> "₹12,345.67". */
export function formatMinor(amount: number | null | undefined, currency: string): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(amount / 100);
}
