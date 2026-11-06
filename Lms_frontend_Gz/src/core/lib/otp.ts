/** A one-time code as typed or pasted: spaces, dashes and anything else that is not a digit are dropped. */
export function cleanOtp(value: string): string {
  return value.replace(/\D/g, "");
}

/** Whether a cleaned code is complete (6 digits). */
export function isCompleteOtp(value: string): boolean {
  return /^\d{6}$/.test(value);
}
