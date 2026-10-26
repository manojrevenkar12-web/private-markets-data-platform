import { expect, type Page, test } from "@playwright/test";

/** Fails the test on any script error; 4xx answers the console handles on purpose are not errors. */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("status of 4")) errors.push(m.text());
  });
  return errors;
}

async function noSideways(page: Page) {
  const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(wide).toBeLessThanOrEqual(1);
}

async function go(page: Page, name: string) {
  const nav = page.getByRole("navigation", { name: "Main" });
  await nav.getByRole("link", { name, exact: true }).click();
}

test("every view loads from the published build without errors or sideways scrolling", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: /What clients see on/ })).toBeVisible();
  await expect(page.getByRole("region", { name: "Gates of the last runs" })).toBeVisible();
  await noSideways(page);
  for (const [link, heading] of [
    ["Breaks", "Breaks"],
    ["Funds", "Target funds"],
    ["Clients", "Clients"],
    ["Data health", "Data health"],
    ["Runs", "Runs"],
    ["Lineage", "Lineage"],
  ] as const) {
    await go(page, link);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
    await noSideways(page);
  }
  expect(errors).toEqual([]);
});

test("a restated fund shows what was known before the restatement", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/funds");
  await page.getByRole("link", { name: "Kestrel European Buyout IV" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Kestrel European Buyout IV" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Restated quarters" })).toBeVisible();
  await page.getByText("As known on", { exact: true }).click();
  await expect(page.getByRole("img", { name: /as known on 14 Jan 2026/ })).toBeVisible();
  await noSideways(page);
  expect(errors).toEqual([]);
});

test("operations notes a break, and the note survives a reload", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/breaks?kind=unmatched_receipt");
  await page.getByLabel("Acting as").selectOption("operations");
  await page.getByLabel("Your name").fill("E2E Operations");
  const table = page.getByRole("region", { name: "Breaks" });
  await expect(table).toBeVisible();
  await page.waitForTimeout(500); // the name is sent once typing pauses
  await table
    .getByRole("button", { name: /^Act on/ })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByText("Add note", { exact: true }).click();
  const note = `Asked the custodian for the remitter ${Date.now()}`;
  await dialog.getByLabel("Note", { exact: true }).fill(note);
  await dialog.getByRole("button", { name: "Add note" }).click();
  await expect(dialog.getByText(/Note added by E2E Operations/)).toBeVisible();
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.reload();
  await expect(page.getByText(note)).toBeVisible();
  expect(errors).toEqual([]);
});

test("an analyst cannot see who a client is; operations can, and is told it is logged", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/clients");
  const table = page.getByRole("region", { name: "Clients" });
  await table.getByRole("link").first().click();
  await page.getByRole("button", { name: "See who this is" }).click();
  await expect(page.getByRole("dialog").getByText(/Only operations can see/)).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByLabel("Acting as").selectOption("operations");
  await page.getByLabel("Your name").fill("E2E Operations");
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: "See who this is" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Reason").fill("E2E: checking the reveal log");
  await dialog.getByRole("button", { name: "Show identity" }).click();
  await expect(dialog.getByText(/Logged with your reason/)).toBeVisible();
  expect(errors).toEqual([]);
});
