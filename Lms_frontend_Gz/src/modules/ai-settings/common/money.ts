/** AI providers bill in US dollars; ai-gateway stores integer US cents. */
export function formatUsd(cents: number): string {
  return (cents / 100).toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

export function formatCount(value: number): string {
  return value.toLocaleString();
}
