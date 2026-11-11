// qa part 8: check Coach A's package tracker against its "done when" lines, in a real browser, with a video.
// PW_EXE=<chromium> bun tests/acceptance/tracker_check.ts <app url> <out dir>
import { chromium } from "playwright";

const [url, outDir] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: outDir, size: { width: 1280, height: 800 } } });
const page = await ctx.newPage();
const res = (name: string, ok: boolean, detail = "") => console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " · " + detail : ""}`);
await page.goto(url, { waitUntil: "networkidle" });
const add = async (name: string, n: number) => {
  await page.fill("#name", name);
  await page.fill("#bought", String(n));
  await page.click("#add button[type=submit]");
  await page.waitForTimeout(600);
};
await add("Client 1", 10);
await add("Client 2", 3);
const row1 = () => page.locator("#rows tr", { hasText: "Client 1" }).locator("td").allInnerTexts();
let r = await row1();
res("adding a client with 10 sessions shows them with 10 left", r[1] === "10" && r[3] === "10", r.slice(0, 4).join(" | "));
await page.locator("#rows tr", { hasText: "Client 1" }).getByRole("button", { name: "+1 used" }).click();
await page.waitForTimeout(600);
r = await row1();
res("+1 used lowers sessions left by one", r[2] === "1" && r[3] === "9", r.slice(0, 4).join(" | "));
await page.locator("#rows tr", { hasText: "Client 2" }).getByRole("button", { name: "+1 used" }).click();
await page.waitForTimeout(600);
const re = await page.locator("#reengage").innerText();
res("a client with 2 or fewer left is in Re-engage", re.includes("Client 2") && !re.includes("Client 1"), re.replace(/\n/g, "; "));
await page.screenshot({ path: `${outDir}/tracker-before-reload.png`, fullPage: true });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(1000);
const after = await page.locator("#rows").innerText();
res("the list is still there after a reload", after.includes("Client 1") && after.includes("Client 2"), after.replace(/\s+/g, " "));
await page.screenshot({ path: `${outDir}/tracker-after-reload.png`, fullPage: true });
await ctx.close();
await browser.close();
