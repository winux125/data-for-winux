import vinext from "vinext";
import { defineConfig, loadEnv } from "vite";
import { resolve } from "node:path";
import { reactAriaKazakh } from "./build/react-aria-kazakh-plugin";

// The bank deployment is a Node server. No Sites session, Cloudflare binding,
// ignored hosting.json or preview owner is needed for a clean checkout.
export default defineConfig(async ({ command }) => ({
  plugins: [
    reactAriaKazakh(resolve(process.cwd(), "lib/react-aria-kazakh.ts")),
    ...(command === "serve" && (process.env.FORTE_FRONTEND_FIXTURES === "1" ||
      loadEnv("development", process.cwd(), "FORTE_FRONTEND_FIXTURES").FORTE_FRONTEND_FIXTURES === "1")
      ? [(await import("./tests/support/frontend-fixtures")).frontendFixtures()] : []),
    vinext(),
  ],
}));
