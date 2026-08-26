import { expect, test } from "@playwright/test";

/**
 * Knowledge base management workflow e2e tests.
 *
 * Covers: login → navigate to Knowledge → verify base list → open create drawer.
 */
const DEMO_TENANT = "demo";
const DEMO_ADMIN_EMAIL = "admin@example.com";
const DEMO_ADMIN_PASSWORD = "AgentHive123!";

async function adminLogin(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel(/组织|tenant/i).fill(DEMO_TENANT);
  await page.getByLabel(/邮箱|email/i).fill(DEMO_ADMIN_EMAIL);
  await page.getByLabel(/密码|password/i).fill(DEMO_ADMIN_PASSWORD);
  await page.getByRole("button", { name: /sign in|登录/i }).click();
  await expect(page.locator(".sidebar")).toBeVisible();
}

test.describe("Knowledge workflow", () => {
  test.beforeEach(async ({ page }) => {
    await adminLogin(page);
  });

  test("admin can navigate to Knowledge page and see the base list", async ({ page }) => {
    await page.getByRole("button", { name: /知识库|Knowledge/i }).first().click();

    // Page header should render.
    await expect(page.getByRole("heading", { name: /知识库/i }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("admin can open the create knowledge base drawer", async ({ page }) => {
    await page.getByRole("button", { name: /知识库|Knowledge/i }).first().click();
    await expect(page.getByRole("heading", { name: /知识库/i }).first()).toBeVisible({ timeout: 10_000 });

    // Click the create button.
    const createButton = page.getByRole("button", { name: /创建知识库|create/i }).first();
    await createButton.click();

    // The drawer should appear with aria-label "创建知识库".
    await expect(page.locator('[aria-label="创建知识库"]').first()).toBeVisible({ timeout: 10_000 });
  });
});
