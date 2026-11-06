/** Values from .env (see .env.example). A missing value fails fast instead of silently using a guess. */
function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (typeof value !== "string" || value === "") throw new Error(`Missing ${name} in .env (see .env.example)`);
  return value;
}

export const env = {
  apiBaseUrl: required("VITE_API_BASE_URL").replace(/\/$/, ""),
  appName: required("VITE_APP_NAME"),
  /** Shown under the app name; optional (empty: not shown). */
  organizationName: (import.meta.env.VITE_ORGANIZATION_NAME ?? "").trim(),
  notificationPollMs: Number(required("VITE_NOTIFICATION_POLL_SECONDS")) * 1000,
  liveRefreshMs: Number(required("VITE_LIVE_REFRESH_SECONDS")) * 1000,
} as const;
