import { expect, test } from "@playwright/test";

import { settle } from "./helpers";

// Sleeper-era journeys (D3) on the mixed-era fixture: weeks 1-8 of 2026 are final, week 9 is
// unfinished. The unfinished week is unscored: pairings only, "Awaiting final", never a score.

test("home → this week's matchup → box score", async ({ page }) => {
  await page.goto("/");
  await settle(page);
  const thisWeek = page.locator(".dz-card", { has: page.getByRole("heading", { name: "This week" }) });
  await expect(thisWeek).toBeVisible();
  await expect(thisWeek.getByText(/through week 8 · week 9 awaiting final/)).toBeVisible();
  await expect(thisWeek.getByText("Week 8 results")).toBeVisible();
  await expect(thisWeek.getByText("Awaiting final").first()).toBeVisible();

  // Pending pairings show no live score.
  await expect(thisWeek.getByLabel("No score yet").first()).toBeVisible();

  // A finalized result deep-links to its box score.
  await thisWeek.getByTestId("this-week-results").locator('a[href^="/matchups/"]').first().click();
  await expect(page).toHaveURL(/\/matchups\/\d+$/);
  await expect(page.getByRole("heading", { name: "Box Score" })).toBeVisible();
  await expect(page.getByText(/2026 · week 8/)).toBeVisible();
});

test("an unfinished week's box score is a gap, not live points", async ({ page }) => {
  await page.goto("/");
  await settle(page);
  const thisWeek = page.locator(".dz-card", { has: page.getByRole("heading", { name: "This week" }) });
  await thisWeek.getByTestId("this-week-pending").locator('a[href^="/matchups/"]').first().click();
  await expect(page.getByText(/This week isn.t final yet/)).toBeVisible();
});

test("standings and matchups mark the unfinished week", async ({ page }) => {
  await page.goto("/standings");
  await settle(page);
  await expect(page.getByText(/Standings through week 8 · week 9 awaiting final/)).toBeVisible();

  await page.goto("/matchups?week=9");
  await settle(page);
  await expect(page.getByText(/Week 9 isn.t final yet/)).toBeVisible();
  await expect(page.getByText("Awaiting final").first()).toBeVisible();
});

test("playoffs show the official bracket's current seeds; standings show potential points", async ({
  page,
}) => {
  await page.goto("/playoffs");
  await expect(page.getByRole("heading", { name: "Playoffs" })).toBeVisible();
  await expect(page.getByText("Official bracket, as recorded by Sleeper.")).toBeVisible();
  await expect(page.getByText(/may change until the playoffs are decided/)).toBeVisible();
  await expect(page.getByText("Championship Bracket")).toBeVisible();
  await expect(page.getByText("TBD").first()).toBeVisible();

  await page.goto("/standings");
  await expect(page.getByRole("columnheader", { name: "Potential" })).toBeVisible();
  await expect(page.getByText(/Weeks 1–8: an injured-reserve player may sit on the bench/)).toBeVisible();
});
