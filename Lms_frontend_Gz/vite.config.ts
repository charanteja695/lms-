import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

// All values come from .env (copy .env.example); nothing environment-specific is hard-coded here.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL(".", import.meta.url)), "");
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    server: {
      port: Number(env.DEV_SERVER_PORT),
      // Same-origin API calls in development: no CORS, and the refresh cookie stays first-party.
      proxy: { "/api": { target: env.DEV_API_PROXY_TARGET, changeOrigin: true } },
      // Playwright writes traces while it runs; watching them crashes the dev server on Windows (EBUSY).
      watch: { ignored: ["**/e2e/**"] },
    },
    test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },  // e2e/ is Playwright's (npm run e2e)
  };
});
