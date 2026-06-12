import type { Page } from "@playwright/test";

/** Wait for webfonts + network to settle so screenshots are stable. */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

/** Pick a season by its visible option label (e.g. "2015 · not scored"). */
export async function selectSeason(page: Page, label: string | RegExp): Promise<void> {
  await page.getByLabel("Season").selectOption({ label: label as string });
}
