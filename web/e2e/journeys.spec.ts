import { expect, test } from "@playwright/test";

import { selectSeason, settle } from "./helpers";

// Critical user journeys (docs/08 §End-to-end), run against the real BFF bound
// to the fixture DB. Assertions lean on the fixture's KNOWN answers.

test("home loads and the primary nav is present", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "The Danger Zone" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav.getByRole("link", { name: "Standings" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Records" })).toBeVisible();
});

test("nav → standings renders a populated table", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Standings" }).click();
  await expect(page).toHaveURL(/\/standings$/);
  await expect(page.getByRole("heading", { name: "Standings" })).toBeVisible();
  // A real, scored standings table — at least the four fixture managers.
  const rows = page.locator("table.dz-table tbody tr");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(4);
});

test("records book shows the known highest team score", async ({ page }) => {
  await page.goto("/records");
  await expect(page.getByRole("heading", { name: "Records Book" })).toBeVisible();
  // KNOWN["highest_team_score"] == 160.4 (Maverick, 2017 wk1).
  await expect(page.getByText("160.4").first()).toBeVisible();
});

test("records → click a record deep-links to its source matchup box score", async ({ page }) => {
  await page.goto("/records");
  // Each record card links to its source via an aria-label "… — view source".
  await page.getByRole("link", { name: /view source/ }).first().click();
  await expect(page).toHaveURL(/\/matchups\/\d+$/);
  await expect(page.getByRole("heading", { name: "Box Score" })).toBeVisible();
});

test("matchups → box score shows points-left-on-bench", async ({ page }) => {
  await page.goto("/matchups");
  await page.locator('a[href^="/matchups/"]').first().click();
  await expect(page).toHaveURL(/\/matchups\/\d+$/);
  await expect(page.getByRole("heading", { name: "Box Score" })).toBeVisible();
  // The optimal-lineup analytics surface: "Left on bench" Stat is present.
  await expect(page.getByText("Left on bench").first()).toBeVisible();
});

test("rivalry matrix renders", async ({ page }) => {
  await page.goto("/rivalries");
  await expect(page.getByRole("heading", { name: "Rivalries" })).toBeVisible();
});

test("gap honesty: a pre-2016 box score is shown as not-scored, never faked", async ({ page }) => {
  // 2015 is present but unscored at the player level; its box score must render
  // a DataGap (role="note"), never invented zeros.
  await page.goto("/standings");
  await selectSeason(page, "2015 · not scored");
  await settle(page);
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Matchups" }).click();
  await page.locator('a[href^="/matchups/"]').first().click();
  await expect(page.getByRole("heading", { name: "Box Score" })).toBeVisible();
  await expect(page.getByRole("note").first()).toBeVisible();
});
