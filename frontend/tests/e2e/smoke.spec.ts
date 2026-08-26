import { expect, test } from "@playwright/test";

/**
 * AgentHive end-to-end smoke tests.
 *
 * Prerequisites:
 *   1. The dev stack is running: `docker compose -f docker-compose.dev.yml up -d`
 *   2. Demo data has been seeded (the dev compose does this automatically).
 *   3. Playwright browsers are installed: `npm run e2e:install`
 *
 * Run: `npm run e2e`
 *
 * These tests use the demo tenant seeded by `backend/scripts/seed_demo.py`.
 */

const DEMO_TENANT = "demo";
const DEMO_ADMIN_EMAIL = "admin@example.com";
const DEMO_ADMIN_PASSWORD = "AgentHive123!";

test.describe("Authentication smoke", () => {
  test("admin can log in and see the admin workspace", async ({ page }) => {
    await page.goto("/");

    // Login form
    await page.getByLabel(/组织|tenant/i).fill(DEMO_TENANT);
    await page.getByLabel(/邮箱|email/i).fill(DEMO_ADMIN_EMAIL);
    await page.getByLabel(/密码|password/i).fill(DEMO_ADMIN_PASSWORD);
    await page.getByRole("button", { name: /sign in|登录/i }).click();

    // After login, the app shell should render with the sidebar.
    await expect(page.locator(".sidebar")).toBeVisible();
    await expect(page.locator(".brand-copy strong")).toHaveText("AgentHive");

    // The admin workspace should expose the Agents nav item.
    await expect(page.getByRole("button", { name: /智能体|Agents/i }).first()).toBeVisible();
  });

  test("rejects invalid credentials with a 401 notice", async ({ page }) => {
    await page.goto("/");

    await page.getByLabel(/组织|tenant/i).fill(DEMO_TENANT);
    await page.getByLabel(/邮箱|email/i).fill(DEMO_ADMIN_EMAIL);
    await page.getByLabel(/密码|password/i).fill("wrong-password");
    await page.getByRole("button", { name: /sign in|登录/i }).click();

    // Should stay on the login page and surface an error notice.
    await expect(page).toHaveURL(/\/$|\/login/i);
    await expect(page.locator(".api-notice, .form-error, [role='alert']").first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Builder page navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.getByLabel(/组织|tenant/i).fill(DEMO_TENANT);
    await page.getByLabel(/邮箱|email/i).fill(DEMO_ADMIN_EMAIL);
    await page.getByLabel(/密码|password/i).fill(DEMO_ADMIN_PASSWORD);
    await page.getByRole("button", { name: /sign in|登录/i }).click();
    await expect(page.locator(".sidebar")).toBeVisible();
  });

  test("admin can open the Builder page and see the form", async ({ page }) => {
    // Navigate to Builder via the sidebar.
    await page.getByRole("button", { name: /builder|低代码/i }).first().click();

    // The builder form should render with at least the name field.
    await expect(page.locator(".builder-editor-workspace, [class*='builder']").first()).toBeVisible({
      timeout: 10_000,
    });
  });
});
