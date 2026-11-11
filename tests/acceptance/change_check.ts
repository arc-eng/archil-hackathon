// qa part 8: check Coach A's changed tracker (unpaid invoices + chart). Seeds the browser with what the FIRST version
// saved (same keys and shape), to prove clients added before the change are still there.
// PW_EXE=<chromium> bun tests/acceptance/change_check.ts <app url> <out dir>
import { chromium } from "playwright";

const [url, outDir] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, recordVideo: { dir: outDir, size: { width: 1280, height: 900 } } });
const page = await ctx.newPage();
const res = (name: string, ok: boolean, detail = "") => console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " · " + detail : ""}`);
await page.goto(url, { waitUntil: "networkidle" });
// exactly what version 1 wrote after the tracker check: {name, bought, used}, no "paid"
await page.evaluate(() => localStorage.setItem("app:clients", JSON.stringify([{ name: "Client 1", bought: 10, used: 1 }, { name: "Client 2", bought: 3, used: 1 }])));
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(800);
const rows = await page.locator("#rows").innerText();
res("clients added before the change are still there", rows.includes("Client 1") && rows.includes("Client 2"), rows.replace(/\s+/g, " "));
await page.locator("#rows tr", { hasText: "Client 2" }).getByRole("checkbox", { name: "Paid" }).uncheck();
await page.waitForTimeout(600);
const un = await page.locator("#unpaid").innerText();
res("unticking Paid puts the client in the Unpaid list", un.includes("Client 2") && !un.includes("Client 1"), un.replace(/\n/g, "; "));
const bars = await page.locator("#chart .bar-row").allInnerTexts();
res("the chart shows one bar per client with sessions left", bars.length === 2 && bars[0].includes("9") && bars[1].includes("2"), bars.map((b) => b.replace(/\s+/g, " ")).join("; "));
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(800);
const un2 = await page.locator("#unpaid").innerText();
res("Unpaid is still set after a reload", un2.includes("Client 2"), un2.replace(/\n/g, "; "));
await page.screenshot({ path: `${outDir}/tracker-v2.png`, fullPage: true });
await ctx.close();
await browser.close();
