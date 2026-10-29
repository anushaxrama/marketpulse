import { test, expect } from "@playwright/test";
const ready = async (page: any) => {
  await expect(page.locator(".view")).toHaveAttribute("aria-busy", "false");
};
test("six pages show real data without document overflow or runtime errors", async ({
  page,
  isMobile,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const route of [
    "overview",
    "symbols",
    "operations",
    "lab",
    "catalog",
    "architecture",
  ]) {
    await page.goto("/#" + route);
    await ready(page);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.locator(".error")).toHaveCount(0);
    if (process.env.MP_CAPTURE_SCREENSHOTS === "true" && route === "overview")
      await page.screenshot({
        path: `../../docs/screenshots/overview-${isMobile ? "mobile" : "desktop"}.png`,
        fullPage: true,
      });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});
test("chart controls, keyboard inspection and CSV reflect the selected symbol and interval", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await page.getByRole("button", { name: /^ETH/ }).click();
  await page.getByRole("button", { name: "1H", exact: true }).click();
  await ready(page);
  await expect(
    page.getByRole("img", {
      name: "ETHUSDT historical one-minute close price chart",
    }),
  ).toBeVisible();
  const slider = page.getByRole("slider", {
    name: "Inspect historical price bar",
  });
  await expect(slider).toHaveAttribute("max", "59");
  await slider.focus();
  await slider.press("ArrowLeft");
  await expect(slider).toHaveValue("58");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export selected bars" }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe(
    "marketpulse-ETHUSDT-1h-historical.csv",
  );
  const { readFile } = await import("node:fs/promises");
  const text = await readFile((await file.path())!, "utf8");
  const lines = text.trim().split(/\r?\n/);
  expect(lines).toHaveLength(61);
  expect(lines.slice(1).every((l) => l.includes(",ETHUSDT,"))).toBe(true);
});
test("symbol search has an honest empty state and API outage can recover", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await page.getByRole("textbox", { name: "Find a symbol" }).fill("not-listed");
  await expect(page.getByText("No symbols match this search.")).toBeVisible();
  await page.route("**/api/overview*", (r) =>
    r.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Injected test outage" }),
    }),
  );
  await page.getByRole("button", { name: "Refresh warehouse data" }).click();
  await expect(page.locator(".error[role=alert]")).toContainText(
    "Injected test outage",
  );
  await page.unroute("**/api/overview*");
  await page.getByRole("button", { name: "Try again" }).click();
  await ready(page);
  await expect(page.locator(".error")).toHaveCount(0);
});
test("lab requires explicit confirmation and themes persist", async ({
  page,
  isMobile,
}) => {
  await page.goto("/#lab");
  await ready(page);
  await page.getByRole("button", { name: "Review replay" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Launch replay", exact: true }),
  ).toBeDisabled();
  await page.getByRole("checkbox").check();
  await page.route("**/api/lab/replays", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "browser-fixture-no-real-job",
        status: "queued",
      }),
    }),
  );
  await page
    .getByRole("button", { name: "Launch replay", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Queued replay");
  if (isMobile)
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await ready(page);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
