import { defineConfig, devices } from "@playwright/test";

const apiEnv = {
  APP_ENV: "test",
  DATABASE_URL: process.env.DATABASE_URL ?? "postgresql+psycopg://pulsegrid:pulsegrid@127.0.0.1:5432/pulsegrid_test",
  CORS_ORIGINS: "http://127.0.0.1:3000",
  BOOTSTRAP_TOKEN: "e2e-bootstrap-token-placeholder",
  SESSION_TTL_HOURS: "12",
  INVITATION_TTL_HOURS: "72",
  MAX_UPLOAD_MB: "5",
  MIN_BASELINE_POINTS: "6",
  ANOMALY_Z_THRESHOLD: "3.5",
  MIN_WORKFORCE_COHORT_SIZE: "20",
};

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "./apps/api",
      url: "http://127.0.0.1:8000/health",
      env: apiEnv,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1",
      cwd: "./apps/web",
      url: "http://127.0.0.1:3000",
      env: { ...process.env, NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
