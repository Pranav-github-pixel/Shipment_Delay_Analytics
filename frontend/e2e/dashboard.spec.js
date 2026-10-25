import { test, expect } from "@playwright/test";

test("real dashboard filters, model, prediction, SQL and responsive layout", async ({
  page,
  request,
}) => {
  const errors = [];
  const summaryRequests = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/predict/summary")) summaryRequests.push(r);
  });
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
  await expect(
    page.getByRole("heading", { name: "Delay rate heatmap", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("table", { name: "Delay rates by region and shipping mode" })
      .locator("tbody tr")
      .first(),
  ).toContainText("n =");
  await page
    .getByRole("heading", { name: "Delay rate heatmap", exact: true })
    .scrollIntoViewIfNeeded();
  await page
    .locator('section[aria-labelledby="heatmap-heading"]')
    .screenshot({ path: "test-results/delay-heatmap.png" });
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
  await expect(
    page.getByRole("heading", { name: "Model comparison", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Selected", exact: true }),
  ).toHaveCount(1);
  const form = {
    "Order Date": "2018-01-15T12:00",
    "Scheduled Days": "1",
    Quantity: "2",
    "Item Count": "2",
    Market: "Europe",
    Region: "Western Europe",
    "Customer Segment": "Consumer",
    "Payment Type": "DEBIT",
  };
  await expect(
    page.getByLabel("Scheduled Days", { exact: true }).locator("option"),
  ).toHaveText([
    "Select scheduled days",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
  ]);
  await expect(
    page.getByRole("button", { name: "Generate summary", exact: true }),
  ).toBeDisabled();
  for (const [label, value] of Object.entries(form)) {
    const field = page.getByLabel(label, { exact: true });
    if (["Order Date", "Quantity", "Item Count"].includes(label))
      await field.fill(value);
    else await field.selectOption(value);
  }
  await page.getByLabel("Net Sales", { exact: true }).fill("125.50");
  expect(
    await page
      .getByLabel("Net Sales", { exact: true })
      .evaluate((el) => el.tagName),
  ).toBe("INPUT");
  expect(summaryRequests).toHaveLength(0);
  await page.getByRole("button", { name: "Predict delay risk" }).click();
  await expect(page.getByText(/estimated delay risk/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Local SHAP explanation", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Operator recommendations",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Check dispatch readiness",
      exact: true,
    }),
  ).toBeVisible();
  expect(summaryRequests).toHaveLength(0);
  const assistant = await (
    await request.get("http://127.0.0.1:8000/api/assistant/status")
  ).json();
  if (assistant.configured) {
    await page
      .getByRole("button", { name: "Generate summary", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Groq operator summary", exact: true }),
    ).toBeVisible();
    expect(summaryRequests).toHaveLength(1);
    await page.screenshot({
      path: "test-results/prediction-shap-summary.png",
      fullPage: true,
    });
    await page.getByLabel("Quantity", { exact: true }).fill("3");
    await expect(
      page.getByRole("heading", { name: "Groq operator summary", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Generate summary", exact: true }),
    ).toBeDisabled();
  }
  await page
    .getByRole("button", { name: "Model Explainability", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Global SHAP importance",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Scheduled shipping days", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/Encoded categories and derived features/).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/explainability-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/explainability-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
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
  if (assistant.configured) {
    await page
      .getByRole("button", { name: "Natural language", exact: true })
      .click();
    await page
      .getByLabel("Analytics question")
      .fill(
        "How many eligible orders are in shipments? Return COUNT(*) AS total in one row.",
      );
    await page
      .getByRole("button", { name: "Generate SQL and run", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Generated SQL", exact: true }),
    ).toBeVisible();
    await expect(page.locator("tbody td")).toHaveText(
      String(status.quality.eligible_orders),
    );
    await page.screenshot({
      path: "test-results/natural-language-sql.png",
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Edit generated SQL", exact: true })
      .click();
    await expect(page.getByLabel("SQL", { exact: true })).toHaveValue(
      /SELECT/i,
    );
  }
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
