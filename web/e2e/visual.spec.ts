import { expect, test } from "@playwright/test";

import { settle } from "./helpers";

// Lightweight visual-regression (docs/08): a small, maintainable set of key
// pages in the default dark theme to catch unintended layout/style drift.
// The live "data as of" timestamp is masked so it never trips the diff.
// Refresh baselines with `make e2e-update` after an intended UI change.

const PAGES: { name: string; path: string; ready: string }[] = [
  { name: "home", path: "/", ready: "The Danger Zone" },
  { name: "standings", path: "/standings", ready: "Standings" },
  { name: "records", path: "/records", ready: "Records Book" },
  { name: "rivalries", path: "/rivalries", ready: "Rivalries" },
  // matchup_id 17 == the fixture's highest team score (Maverick, 2017 wk1).
  { name: "box-score", path: "/matchups/17", ready: "Box Score" },
];

for (const p of PAGES) {
  test(`visual: ${p.name}`, async ({ page }) => {
    await page.goto(p.path);
    await expect(page.getByRole("heading", { name: p.ready, exact: true })).toBeVisible();
    await settle(page);
    await expect(page).toHaveScreenshot(`${p.name}.png`, {
      fullPage: true,
      mask: [page.locator(".dz-data-status")],
      animations: "disabled",
    });
  });
}

test("visual: standings-historical-mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/standings");
  await expect(page.getByRole("heading", { name: "Westeros" })).toBeVisible();
  await settle(page);
  await expect(page).toHaveScreenshot("standings-historical-mobile.png", {
    fullPage: true,
    mask: [page.locator(".dz-data-status")],
    animations: "disabled",
  });
});
