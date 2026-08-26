import { expect, test } from "@playwright/test";

/**
 * Agent management workflow e2e tests.
 *
 * Covers: login → navigate to Agents → verify catalog/instances → open create form.
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

test.describe("Agents workflow", () => {
  test.beforeEach(async ({ page }) => {
    await adminLogin(page);
  });

  test("admin can navigate to Agents page and see the instance panel", async ({ page }) => {
    await page.getByRole("button", { name: /智能体|Agents/i }).first().click();

    // Page header should render the title.
    await expect(page.getByRole("heading", { name: /智能体管理/i })).toBeVisible({ timeout: 10_000 });

    // The agent instance panel should be visible.
    await expect(page.locator("#agent-instance-panel")).toBeVisible({ timeout: 10_000 });
  });

  test("admin can open the create agent form", async ({ page }) => {
    await page.getByRole("button", { name: /智能体|Agents/i }).first().click();
    await expect(page.locator("#agent-instance-panel")).toBeVisible({ timeout: 10_000 });

    // Click the "create agent" button.
    const createButton = page.getByRole("button", { name: /创建智能体|create/i }).first();
    await createButton.click();

    // A drawer or dialog should appear with a name input.
    await expect(page.locator('input[type="text"]').first()).toBeVisible({ timeout: 10_000 });
  });
});
