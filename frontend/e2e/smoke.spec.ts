import { test, expect } from "@playwright/test";

test.describe("SentinelGuard UI", () => {
  test("login page loads", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "SentinelGuard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });
});
