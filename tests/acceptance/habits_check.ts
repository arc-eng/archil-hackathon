// qa part 8: check Coach B's habit check-in log against its "done when" lines, in a real browser, with a video.
// PW_EXE=<chromium> bun tests/acceptance/habits_check.ts <app url> <out dir>
import { chromium } from "playwright";

const [url, outDir] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: "America/Los_Angeles", recordVideo: { dir: outDir, size: { width: 1280, height: 900 } } });
const page = await ctx.newPage();
const res = (name: string, ok: boolean, detail = "") => console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " · " + detail : ""}`);
await page.goto(url, { waitUntil: "networkidle" });
const today = await page.inputValue("#date");
const shift = (day: string, n: number) => { const d = new Date(day + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const add = async (client: string, date: string, habit: string) => {
  await page.fill("#client", client);
  await page.fill("#date", date);
  await page.fill("#habit", habit);
  await page.selectOption("#done", "yes");
  await page.click("#f button[type=submit]");
  await page.waitForTimeout(500);
};
await add("Client 1", shift(today, -2), "10-minute walk");
await add("Client 1", shift(today, -1), "10-minute walk");
await add("Client 1", today, "10-minute walk");
const first = (await page.locator("#list li").first().innerText()).trim();
res("adding a check-in shows it at the top", first.startsWith(today) && first.includes("Client 1"), first);
const st = await page.locator("#streaks").innerText();
res("three done days in a row show a streak of 3", st.includes("Client 1: streak of 3"), st.replace(/\n/g, "; "));
await page.screenshot({ path: `${outDir}/habits-before-reload.png`, fullPage: true });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(800);
const n = await page.locator("#list li").count();
res("check-ins are still there after a reload", n === 3, `${n} check-ins after reload`);
await page.screenshot({ path: `${outDir}/habits-after-reload.png`, fullPage: true });
await ctx.close();
await browser.close();
