import { expect, test } from "@playwright/test";

import { settle } from "./helpers";

// Sleeper-era visual baselines (D8), on the mixed-era fixture (`sleeper` project): weeks 1-8 of 2026
// final, week 9 awaiting final. Same rules as visual.spec.ts; the "data as of" line is masked.
// Player detail is left out on purpose: its "latest status" card follows today's date (7-day rule).

const PAGES: { name: string; path: string; ready: string }[] = [
  { name: "sleeper-home", path: "/", ready: "This week" },
  { name: "sleeper-standings", path: "/standings", ready: "Standings" },
  { name: "sleeper-playoffs", path: "/playoffs", ready: "Playoffs" },
  { name: "sleeper-matchups-pending", path: "/matchups?week=9", ready: "Matchups" },
  { name: "sleeper-team", path: "/teams/17", ready: "Roster" },
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
