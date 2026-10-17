import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e", timeout: 45_000, expect: { timeout: 12_000 }, fullyParallel: true,
  use: { baseURL: process.env.FRONTEND_TEST_URL || "http://127.0.0.1:5173", viewport: { width: 1366, height: 900 }, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }, { name: "webkit", use: { ...devices["Desktop Safari"] } }],
  webServer: process.env.FRONTEND_TEST_URL ? undefined : { command: "npm run dev -- --port 5173", url: "http://127.0.0.1:5173", reuseExistingServer: !process.env.CI },
});
