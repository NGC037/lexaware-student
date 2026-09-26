import { expect, test } from "@playwright/test";

test("registers, signs in, onboards, refreshes, logs out, and signs in again", async ({ page }) => {
  const email = `lexaware-e2e-${crypto.randomUUID()}@example.com`;
  const password = `LexawareE2E-${crypto.randomUUID()}-Student!`;
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) browserErrors.push(message.text());
  });

  await page.goto("/register");
  await expect(page.getByRole("heading", { name: "Create your LexAware account" })).toBeVisible();
  await page.getByLabel("Name (optional)").fill("Integration Student");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByRole("heading", { name: "Check what to do next" })).toBeVisible();
  await page.getByRole("link", { name: "Continue to sign in" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "Welcome to LexAware Student" })).toBeFocused();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Information for real questions" })).toBeFocused();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Understand the limits" })).toBeVisible();
  await expect(page.getByText(/not saved to your account yet/i)).toBeVisible();
  const helpResponsePromise = page.waitForResponse((response) => response.url().includes("/api/v1/help?limit=3") && response.request().method() === "GET");
  await page.getByRole("button", { name: "Continue to your account" }).click();

  await expect(page).toHaveURL(/\/app(?:#dashboard-support)?$/);
  await expect(page.getByRole("heading", { name: /Integration Student\./ })).toBeVisible();
  const helpResponse = await helpResponsePromise;
  expect(helpResponse.ok()).toBeTruthy();
  const realHelp = await helpResponse.json() as { name: string }[];
  if (realHelp.length) await expect(page.getByRole("heading", { name: realHelp[0]!.name })).toBeVisible();
  else await expect(page.getByRole("heading", { name: "No current contacts are listed" })).toBeVisible();

  const searchResponsePromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/articles?") && response.url().includes("q=student") && response.request().method() === "GET");
  await page.getByRole("textbox", { name: "Search reviewed student guidance" }).fill("student");
  await page.getByRole("button", { name: "Search published guidance" }).click();
  const searchResponse = await searchResponsePromise;
  expect(searchResponse.ok()).toBeTruthy();
  const realArticles = await searchResponse.json() as { title: string }[];
  if (realArticles.length) await expect(page.getByRole("heading", { name: realArticles[0]!.title })).toBeVisible();
  else await expect(page.getByRole("heading", { name: "No published guidance matched" })).toBeVisible();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Support" }).click();
  await expect(page).toHaveURL(/#dashboard-support$/);
  await expect(page.getByRole("heading", { name: "Need help finding a next step?" })).toBeVisible();

  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBeTruthy();
  await page.getByLabel("Color theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".workspace-art__mark")).toHaveCSS("transform", "none");

  await page.route("**/api/v1/help?limit=3", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "private backend failure" }) }));
  await page.reload();
  await expect(page).toHaveURL(/\/app(?:#dashboard-support)?$/);
  await expect(page.getByRole("heading", { name: /Integration Student\./ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Support contacts are temporarily unavailable" })).toBeVisible();
  await page.unroute("**/api/v1/help?limit=3");
  await expect(page.locator("body")).not.toContainText("private backend failure");
  expect(browserErrors).toEqual([]);

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /know your rights/i })).toBeVisible();
  await page.goto("/app");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: /Integration Student\./ })).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/$/);
});
