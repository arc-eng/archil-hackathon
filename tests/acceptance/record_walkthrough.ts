// qa backup (arc-eng/hq#781): record the demo walkthrough as one video plus screenshots, read-only (no clicks that change
// anything; never Publish). Steps: "<url>" shows a page; "<url>|scroll" also scrolls to the bottom; "<url>|switch" also
// presses Space to flip the /how slide. Admin URLs carry a key: keep the output folder's admin URL list off GitHub.
// PW_EXE=<chromium> bun tests/acceptance/record_walkthrough.ts <out dir> <seconds per step> <step> [<step> ...]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const [outDir, secs, ...steps] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const ms = Number(secs) * 1000;
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: outDir, size: { width: 1440, height: 900 } } });
const page = await ctx.newPage();
const errors: string[] = [];
page.on("pageerror", (e) => errors.push(String(e)));
let n = 0;
const shot = async () => page.screenshot({ path: `${outDir}/shot-${String(++n).padStart(2, "0")}.png` });
for (const step of steps) {
  const [url, action] = step.split("|");
  const r = await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(ms);
  await shot();
  if (action === "scroll") {
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
    await page.waitForTimeout(ms);
    await shot();
  } else if (action === "switch") {
    await page.keyboard.press("Space");
    await page.waitForTimeout(ms);
    await shot();
  }
  console.log(`step ${steps.indexOf(step) + 1}: HTTP ${r?.status()} ${action ?? ""} title="${await page.title()}"`);
}
await ctx.close();
await browser.close();
console.log(`errors: ${errors.length ? errors.join(" | ") : "none"}`);
