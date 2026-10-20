import { test, expect } from "@playwright/test";

test("real dashboard filters, model, prediction, SQL and responsive layout", async ({
  page,
  request,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const status = await (
    await request.get("http://127.0.0.1:8000/api/status")
  ).json();
  expect(status.job.state).toBe("completed");
  expect(status.model.state).not.toBe("unavailable");
  await page.goto("/");
  await expect(
    page.getByText("Eligible orders", { exact: true }),
  ).toBeVisible();
  const metrics = page.locator(".metric strong");
  const total = await metrics.first().innerText();
  const options = await page
    .getByLabel("Region", { exact: true })
    .locator("option")
    .allTextContents();
  await page
    .getByLabel("Region", { exact: true })
    .selectOption({ label: options[1] });
  const filtered = page.waitForResponse(
    (r) =>
      r.url().includes("/api/analytics?") && r.request().method() === "GET",
  );
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  expect((await filtered).ok()).toBeTruthy();
  await expect(metrics.first()).not.toHaveText(total);
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(metrics.first()).toHaveText(total);
  await page
    .getByRole("button", { name: "Delay Analytics", exact: true })
    .click();
  await expect(
    page.getByText("Monthly delay trend", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Regional performance", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Data Quality", exact: true }).click();
  await expect(
    page.getByText("Validation and exclusions", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Model Evaluation", exact: true })
    .click();
  await expect(
    page.getByText("Confusion matrix", { exact: true }),
  ).toBeVisible();
  const form = {
    "Order Date": "2018-01-15T12:00",
    "Scheduled Days": "4",
    Quantity: "2",
    "Net Sales": "180",
    "Item Count": "2",
    Market: "Europe",
    Region: "Western Europe",
    "Customer Segment": "Consumer",
    "Payment Type": "DEBIT",
  };
  for (const [label, value] of Object.entries(form))
    await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByRole("button", { name: "Predict delay risk" }).click();
  await expect(page.getByText(/estimated delay risk/)).toBeVisible();
  await page
    .getByRole("button", { name: "SQL Analytics", exact: true })
    .click();
  await page.getByLabel("Query name").fill("Browser verification");
  await page
    .getByLabel("SQL", { exact: true })
    .fill("SELECT COUNT(*) AS total FROM shipments");
  await page.getByRole("button", { name: "Save query", exact: true }).click();
  await expect(page.getByText("Query saved.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.locator("tbody td")).toHaveText(
    String(status.quality.eligible_orders),
  );
  await page
    .getByRole("button", { name: "Delete Browser verification", exact: true })
    .click();
  await expect(page.getByText("Query deleted.", { exact: true })).toBeVisible();
  await page.getByLabel("SQL", { exact: true }).fill("DROP TABLE shipments");
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("SELECT");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: "test-results/overview-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/overview-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
