import { defineConfig } from "@playwright/test";

const port = Number(process.env.SELECTS_BROWSER_PORT || 20000 + process.pid % 20000);
process.env.SELECTS_BROWSER_PORT = String(port);

export default defineConfig({
  testDir: "./tests/browser",
  timeout: 240_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["line"]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    viewport: { width: 1440, height: 1050 },
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  webServer: {
    command: "python3 scripts/run_browser_acceptance_server.py",
    url: `http://127.0.0.1:${port}`,
    env: { SELECTS_BROWSER_PORT: String(port) },
    reuseExistingServer: false,
    timeout: 120_000
  }
});
