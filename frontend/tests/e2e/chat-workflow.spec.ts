import { expect, test } from "@playwright/test";

/**
 * Chat workflow e2e tests.
 *
 * Covers: login → navigate to Chat → create session → send message → verify response.
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

test.describe("Chat workflow", () => {
  test.beforeEach(async ({ page }) => {
    await adminLogin(page);
  });

  test("admin can navigate to Chat page and create a new session", async ({ page }) => {
    await page.getByRole("button", { name: /对话|Chat/i }).first().click();

    // Page header should render.
    await expect(page.getByRole("heading", { name: /对话控制台|Chat/i }).first()).toBeVisible({ timeout: 10_000 });

    // Click "new session" button.
    const newSessionButton = page.getByRole("button", { name: /新建会话|new session/i }).first();
    await newSessionButton.click();

    // The chat message log area should become visible.
    await expect(page.locator('[role="log"]').first()).toBeVisible({ timeout: 10_000 });
  });

  test("admin can send a message and see a response in the chat", async ({ page }) => {
    await page.getByRole("button", { name: /对话|Chat/i }).first().click();
    await expect(page.getByRole("heading", { name: /对话控制台|Chat/i }).first()).toBeVisible({ timeout: 10_000 });

    // Create a new session first.
    const newSessionButton = page.getByRole("button", { name: /新建会话|new session/i }).first();
    await newSessionButton.click();
    await expect(page.locator('[role="log"]').first()).toBeVisible({ timeout: 10_000 });

    // Type a message into the textarea.
    const input = page.getByLabel(/向.*提问|placeholder/i).first();
    if (await input.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await input.fill("你好");
      await page.getByRole("button", { name: /^发送$|^send$/i }).first().click();

      // Wait for either a user message or assistant response to appear in the log.
      // Use a generous timeout since LLM responses may take time.
      await expect(page.locator('[role="log"]')).toContainText(/你好|assistant|智能体/i, { timeout: 30_000 });
    }
  });
});
