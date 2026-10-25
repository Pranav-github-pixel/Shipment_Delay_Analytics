import { test, expect } from "@playwright/test";

test("real geographic map follows filters, renders offline and handles failures", async ({
  page,
  request,
}, testInfo) => {
  const status = await (await request.get("/api/status")).json();
  expect(status.job.state).toBe("completed");
  const actual = await (await request.get("/api/analytics/map")).json();
  expect(actual.total_orders).toBe(status.quality.eligible_orders);
  expect(actual.countries.length).toBeGreaterThan(100);
  expect(actual.unmapped_orders).toBe(0);
  expect(
    actual.countries.reduce((sum, row) => sum + row.delayed_orders, 0),
  ).toBe(actual.delayed_orders);
  const external = [];
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (
      r.frame().parentFrame() &&
      !r.url().startsWith("http://127.0.0.1") &&
      !r.url().startsWith("data:") &&
      !r.url().startsWith("about:")
    )
      external.push(r.url());
  });
  await page.goto("/");
  await expect(
    page.getByText("Eligible orders", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Delay Analytics", exact: true })
    .click();
  const map = page.locator('section[aria-labelledby="geographic-map-heading"]');
  await expect(
    map.getByRole("heading", { name: "Late deliveries around the world" }),
  ).toBeVisible();
  const mapResponse = page.frameLocator("iframe.world-map");
  await expect(mapResponse.locator('svg circle[tabindex="0"]')).toHaveCount(
    actual.countries.length,
  );
  await expect(
    mapResponse.locator('svg circle[tabindex="0"]').first(),
  ).toHaveAttribute("aria-label", /delayed.*eligible orders/);
  expect(
    await page
      .locator('section[aria-labelledby="heatmap-heading"]')
      .evaluate((node) =>
        node.nextElementSibling.getAttribute("aria-labelledby"),
      ),
  ).toBe("geographic-map-heading");
  await map.screenshot({ path: testInfo.outputPath("world-map-desktop.png") });
  await page
    .getByLabel("Region", { exact: true })
    .selectOption("Western Europe");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  const filtered = await (
    await request.get("/api/analytics/map?region=Western%20Europe")
  ).json();
  await expect(map).toContainText(
    filtered.total_orders.toLocaleString("en-US"),
  );
  await page.getByLabel("From", { exact: true }).fill("2030-01-01");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(map).toContainText("No eligible orders match these filters.");
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(mapResponse.locator('svg circle[tabindex="0"]')).toHaveCount(
    actual.countries.length,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await map.scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await map.screenshot({ path: testInfo.outputPath("world-map-mobile.png") });
  // Simulate only transport failure; displayed map data above came from real Spark.
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.route("**/api/analytics/map*", (route) => route.abort("failed"));
  await page
    .getByRole("button", { name: "Delay Analytics", exact: true })
    .click();
  await expect(map.getByRole("alert")).toBeVisible();
  await page.unroute("**/api/analytics/map*");
  await map.getByRole("button", { name: "Retry map", exact: true }).click();
  await expect(mapResponse.locator('svg circle[tabindex="0"]')).toHaveCount(
    actual.countries.length,
  );
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
});
