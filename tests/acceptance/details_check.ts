// qa: one table row per app, the DETAILS 1 page, and Stop through its confirm dialog. Run ONLY against
// pages_local.py (in-memory registry copy, clear is a no-op): Stop here never touches a real app.
// PW_EXE=<chromium> bun tests/acceptance/details_check.ts <base url> <paths file> <out dir>
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";

const [base, pathsFile, outDir] = process.argv.slice(2);
if (!/127\.0\.0\.1|localhost/.test(base)) throw new Error("local only: Stop must never run against the live connector");
mkdirSync(outDir, { recursive: true });
const admin = readFileSync(pathsFile, "utf8").split("\n")[0];
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors: string[] = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.goto(base + admin, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const rows = await page.locator("tbody tr").allInnerTexts();
const tracker = rows.filter((r) => r.includes("Client package tracker") && r.includes("Coach A"));
console.log(`table rows: ${rows.length}; Coach A tracker rows: ${tracker.length} (${tracker.map((r) => r.replace(/\s+/g, " ")).join(" / ")})`);
await page.screenshot({ path: `${outDir}/table.png`, fullPage: true });
await page.locator("tbody tr", { hasText: "Coach A" }).filter({ hasText: "Live" }).first().locator("td").first().click();
await page.waitForURL(/\/app\//, { timeout: 5000 });
await page.waitForTimeout(1200);
await page.screenshot({ path: `${outDir}/details.png`, fullPage: true });
console.log("DETAILS:", (await page.innerText("body")).replace(/\s+/g, " ").slice(0, 900));
const stop = page.getByRole("button", { name: /Stop app/ });
console.log("Stop enabled on a live app:", await stop.isEnabled());
await stop.click();
await page.waitForTimeout(500);
const dlg = page.getByRole("alertdialog");
console.log("confirm dialog:", (await dlg.innerText()).replace(/\s+/g, " "));
await page.screenshot({ path: `${outDir}/confirm.png` });
await dlg.getByRole("button", { name: /Cancel/ }).click();
await page.waitForTimeout(500);
console.log("after Cancel, still live:", (await page.innerText("body")).includes("Live"));
await stop.click();
await page.waitForTimeout(400);
await page.getByRole("alertdialog").getByRole("button", { name: /Stop/ }).click();
await page.waitForTimeout(6500);
const after = (await page.innerText("body")).replace(/\s+/g, " ");
console.log("after confirm:", after.slice(0, 200), "| Stop disabled:", !(await stop.isEnabled()));
await page.screenshot({ path: `${outDir}/stopped.png`, fullPage: true });
console.log("errors:", errors.length ? errors.join(" | ") : "none");
await browser.close();
