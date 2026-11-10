import { defineConfig, devices } from "@playwright/test";

// e2e runs against a REAL BFF bound to the hand-authored fixture database
// (scripts/serve_e2e.py), serving the built SPA single-origin on :8810. Journeys
// assert against the fixture's KNOWN answers, so they are deterministic.
const PORT = 8810;
const BASE_URL = `http://127.0.0.1:${PORT}`;
// Sleeper-era journeys (D3+) run against the mixed-era fixture (legacy + a Sleeper 2026 season)
// on their own server, so 2026 never becomes the legacy suite's default season.
const MIXED_PORT = 8811;
const MIXED_URL = `http://127.0.0.1:${MIXED_PORT}`;
const SLEEPER_SPECS = /sleeper\.spec\.ts$/;

export default defineConfig({
  testDir: "./e2e",
  // The dashboard reads a shared in-process cache + one SQLite file; keep it
  // serial so screenshots and journeys don't race the season switcher.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : [["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  // Small tolerance for sub-pixel anti-aliasing differences across machines;
  // layout/content drift still trips the snapshot. Refresh with `make e2e-update`.
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.02 },
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: SLEEPER_SPECS },
    {
      name: "sleeper",
      use: { ...devices["Desktop Chrome"], baseURL: MIXED_URL },
      testMatch: SLEEPER_SPECS,
    },
  ],
  webServer: [
    {
      command: "npm run build && cd .. && uv run python scripts/serve_e2e.py",
      url: `${BASE_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // Waits for the server above (i.e. for the SPA build) before it starts.
      command: "cd .. && uv run python scripts/serve_e2e.py --mixed",
      url: `${MIXED_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
