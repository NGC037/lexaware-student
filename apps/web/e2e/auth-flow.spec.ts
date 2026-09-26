import { expect, test } from "@playwright/test";
function contrastRatio(foreground: string, background: string): number {
  const luminance = (color: string) => {
    const channels = color.match(/[0-9.]+/g)?.slice(0, 3).map(Number) ?? [];
    const linear = channels.map((channel) => { const value = channel / 255; return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * linear[0]! + 0.7152 * linear[1]! + 0.0722 * linear[2]!;
  };
  const first = luminance(foreground);
  const second = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

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
  const rightsListPromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/articles?") && response.url().includes("audience=students") && response.request().method() === "GET");
  const categoriesPromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/categories") && response.request().method() === "GET");
  const jurisdictionsPromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/jurisdictions") && response.request().method() === "GET");
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Know your rights" }).click();
  const [rightsListResponse, categoriesResponse, jurisdictionsResponse] = await Promise.all([rightsListPromise, categoriesPromise, jurisdictionsPromise]);
  expect(rightsListResponse.ok()).toBeTruthy();
  expect(categoriesResponse.ok()).toBeTruthy();
  expect(jurisdictionsResponse.ok()).toBeTruthy();
  const publishedArticles = await rightsListResponse.json() as { slug: string; title: string; category: string; jurisdiction: { code: string; name: string }; source_url: string; last_reviewed_at: string | null }[];
  const supportedCategories = await categoriesResponse.json() as { category: string }[];
  const supportedJurisdictions = await jurisdictionsResponse.json() as { code: string; name: string }[];
  if (publishedArticles.length) {
    const firstArticle = publishedArticles[0]!;
    expect(supportedCategories.some((item) => item.category === firstArticle.category)).toBeTruthy();
    expect(supportedJurisdictions.some((item) => item.code === firstArticle.jurisdiction.code)).toBeTruthy();
    await expect(page.locator(".rights-article-list").getByRole("heading", { name: firstArticle.title }).first()).toBeVisible();
    const searchTerm = firstArticle.title.split(/\s+/).find((word) => word.length >= 4) ?? firstArticle.title;
    const realSearchPromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/articles?") && response.url().includes("q=") && response.request().method() === "GET");
    await page.getByRole("searchbox", { name: "Search guidance" }).fill(searchTerm);
    await page.getByRole("button", { name: "Apply filters" }).click();
    expect((await realSearchPromise).ok()).toBeTruthy();

    const filteredPromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/articles?") && response.url().includes("category=") && response.url().includes("jurisdiction=") && response.request().method() === "GET");
    await page.getByRole("searchbox", { name: "Search guidance" }).fill("");
    await page.getByRole("combobox", { name: "Category" }).selectOption(firstArticle.category);
    await page.getByRole("combobox", { name: "Jurisdiction" }).selectOption(firstArticle.jurisdiction.code);
    await page.getByRole("button", { name: "Apply filters" }).click();
    const filteredResponse = await filteredPromise;
    expect(filteredResponse.ok()).toBeTruthy();
    const filteredArticles = await filteredResponse.json() as { slug: string }[];
    expect(filteredArticles.some((article) => article.slug === firstArticle.slug)).toBeTruthy();

    const detailResponsePromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/articles/" + encodeURIComponent(firstArticle.slug)) && response.request().method() === "GET");
    await page.getByRole("link", { name: /Read guidance/ }).first().click();
    const detailResponse = await detailResponsePromise;
    expect(detailResponse.ok()).toBeTruthy();
    const realDetail = await detailResponse.json() as { title: string; source: { title: string; source_url: string; retrieved_at: string }; last_reviewed_at: string | null };
    await expect(page.getByRole("heading", { name: realDetail.title })).toBeVisible();
    await expect(page.getByRole("heading", { name: realDetail.source.title })).toBeVisible();
    await expect(page.getByRole("link", { name: /Open original source/ })).toHaveAttribute("href", realDetail.source.source_url);
    expect(realDetail.source.retrieved_at).toBeTruthy();
    await page.reload();
    await expect(page.getByRole("heading", { name: realDetail.title })).toBeVisible();
    await page.getByRole("link", { name: /All guidance/ }).click();
  } else {
    await expect(page.getByRole("heading", { name: "No guidance matched these filters" })).toBeVisible();
  }

  const emptyTerm = "rights-empty-" + crypto.randomUUID();
  const emptyResponsePromise = page.waitForResponse((response) => response.url().includes("/api/v1/knowledge/articles?") && response.url().includes("q=" + encodeURIComponent(emptyTerm)) && response.request().method() === "GET");
  await page.getByRole("searchbox", { name: "Search guidance" }).fill(emptyTerm);
  await page.getByRole("button", { name: "Apply filters" }).click();
  expect((await emptyResponsePromise).ok()).toBeTruthy();
  await expect(page.getByRole("heading", { name: "No guidance matched these filters" })).toBeVisible();

  await page.route("**/api/v1/knowledge/articles*", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "private knowledge service failure" }) }));
  await page.getByRole("searchbox", { name: "Search guidance" }).fill("service failure");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByRole("heading", { name: "Guidance is temporarily unavailable" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("private knowledge service failure");
  await page.unroute("**/api/v1/knowledge/articles*");

  await page.goto("/app/rights");
  await expect(page.getByRole("heading", { name: "Know Your Rights" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Published guidance", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBeTruthy();
  await page.getByLabel("Color theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const darkPalette = await page.locator(".rights-hero h1").evaluate("heading => ({ primary: getComputedStyle(heading).color, secondary: getComputedStyle(document.querySelector('.rights-hero > p:last-child')).color, background: getComputedStyle(document.body).backgroundColor })") as { primary: string; secondary: string; background: string };
  expect(contrastRatio(darkPalette.primary, darkPalette.background)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(darkPalette.secondary, darkPalette.background)).toBeGreaterThanOrEqual(4.5);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".rights-page")).toHaveCSS("animation-name", "none");
  expect(browserErrors).toEqual([]);
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: /Integration Student\./ })).toBeVisible();
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
