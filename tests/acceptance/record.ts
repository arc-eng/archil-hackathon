// qa acceptance (part 8): record a screen video and screenshots of a list of pages, each shown for a few seconds.
// PW_EXE=<chromium> bun tests/acceptance/record.ts <out dir> <seconds per page> <url> [<url> ...]
// Admin URLs carry a key: keep the output folder off GitHub.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const [outDir, secs, ...urls] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: outDir, size: { width: 1440, height: 900 } } });
const page = await ctx.newPage();
const errors: string[] = [];
page.on("pageerror", (e) => errors.push(String(e)));
for (const [i, u] of urls.entries()) {
  const r = await page.goto(u, { waitUntil: "networkidle" });
  await page.waitForTimeout(Number(secs) * 1000);
  await page.screenshot({ path: `${outDir}/shot-${String(i + 1).padStart(2, "0")}.png`, fullPage: true });
  console.log(`page ${i + 1}: HTTP ${r?.status()} title="${await page.title()}"`);
}
await ctx.close();
await browser.close();
console.log(`errors: ${errors.length ? errors.join(" | ") : "none"}`);
