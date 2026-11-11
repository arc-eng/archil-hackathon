// qa acceptance: screenshot the admin page and each status page, and report what's on them.
// bun tests/acceptance/pages_shots.ts <base url> <paths file> <out dir>
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";

const [base, pathsFile, outDir] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const paths = readFileSync(pathsFile, "utf8").trim().split("\n");
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
for (const [i, p] of paths.entries()) {
  for (const width of i === 0 ? [1440, 1280] : [1440, 500]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    await page.goto(base + p, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const name = i === 0 ? `admin-${width}` : `status-${i}-${width}`;
    await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: true });
    const text = (await page.innerText("body")).replace(/\s+/g, " ").slice(0, 700);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    const font = await page.evaluate(() => getComputedStyle(document.body).fontSize + " " + getComputedStyle(document.body).fontFamily.slice(0, 20));
    console.log(`== ${name} overflow=${overflow} font=${font} errors=${errors.length ? errors.join(" | ") : "none"}\n${text}`);
    await page.close();
  }
}
await browser.close();
