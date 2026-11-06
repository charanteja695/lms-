/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_APP_NAME?: string;
  readonly VITE_ORGANIZATION_NAME?: string;
  readonly VITE_NOTIFICATION_POLL_SECONDS?: string;
  readonly VITE_LIVE_REFRESH_SECONDS?: string;
}
