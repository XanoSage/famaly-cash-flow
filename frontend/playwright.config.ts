import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const frontendDirectory = fileURLToPath(new URL(".", import.meta.url));
const backendDirectory = fileURLToPath(new URL("../backend/", import.meta.url));
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:4173";
const apiBaseURL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";
const frontendOrigin = new URL(baseURL).origin;
const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: isCI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL,
    ...devices["Desktop Chrome"],
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
      cwd: backendDirectory,
      url: `${apiBaseURL}/health`,
      timeout: 60_000,
      reuseExistingServer: !isCI,
      stdout: "ignore",
      stderr: "pipe",
      env: {
        ...process.env,
        APP_ENV: "test",
        AUTH_COOKIE_SECURE: "false",
        AUTH_COOKIE_SAMESITE: "lax",
        CORS_ALLOWED_ORIGINS: JSON.stringify([frontendOrigin]),
      },
    },
    {
      command: "npm run preview -- --host 0.0.0.0 --port 4173 --strictPort",
      cwd: frontendDirectory,
      url: baseURL,
      timeout: 30_000,
      reuseExistingServer: !isCI,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
