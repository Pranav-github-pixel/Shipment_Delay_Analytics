import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 120000,
  expect: { timeout: 30000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173",
    channel: "chrome",
    headless: true,
  },
  workers: 1,
  reporter: "list",
});
