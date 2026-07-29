import { defineConfig, devices } from "@playwright/test";
import { config as loadEnvironment } from "dotenv";
import { resolve } from "node:path";

loadEnvironment({ path: resolve(process.cwd(), ".env.e2e") });

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global.setup.ts",
  globalTeardown: "./e2e/global.teardown.ts",
  timeout: 60_000,
  expect: {
    timeout: 20_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
