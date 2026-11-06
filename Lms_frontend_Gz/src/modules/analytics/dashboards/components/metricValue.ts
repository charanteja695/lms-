import { formatMinor } from "@/core/lib/money";
import type { MetricFormat } from "@/modules/analytics/common/dashboards";

/** Display text for one total. Billing amounts are paise, CTC whole rupees; AI cost is US cents. */
export function metricValue(value: unknown, format: MetricFormat = "count"): string {
  if (value == null || typeof value !== "number") return "—";
  switch (format) {
    case "percent":
      return `${(value * 100).toFixed(1)}%`; // rates are fractions 0–1
    case "score":
      return value.toFixed(1);
    case "rupees":
      return formatMinor(value * 100, "INR");
    case "inr":
      return formatMinor(value, "INR");
    case "usd":
      return formatMinor(value, "USD");
    default:
      return Math.round(value).toLocaleString();
  }
}
