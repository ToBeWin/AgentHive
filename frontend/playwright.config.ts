import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration for AgentHive.
 *
 * E2E tests are opt-in: they require a running stack (docker-compose.dev.yml)
 * and are NOT invoked by `npm test` or `npm run check`. Run them explicitly:
 *
 *   1. Start the dev stack:        docker compose -f docker-compose.dev.yml up -d
 *   2. Install browsers (once):    npx playwright install --with-deps chromium
 *   3. Run E2E:                    npx playwright test
 *
 * CI integration: wire `npx playwright test` into a separate job that brings
 * up the stack as a service container, then tears it down.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false, // tests share a demo tenant, serialise to avoid state races
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: process.env.AGENTHIVE_E2E_BASE_URL ?? "http://127.0.0.1:18080",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
