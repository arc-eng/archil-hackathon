// qa: admin page A (totals, Apps / Refused tabs, row click → details page). Run against pages_local.py.
// PW_EXE=<chromium> bun tests/acceptance/admin_a_check.ts <base url> <paths file> <out dir>
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";

const [base, pathsFile, outDir] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const admin = readFileSync(pathsFile, "utf8").split("\n")[0];
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors: string[] = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.goto(base + admin, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.screenshot({ path: `${outDir}/a-apps.png`, fullPage: true });
console.log("APPS TAB:", (await page.innerText("body")).replace(/\s+/g, " ").slice(0, 600));
await page.getByRole("tab", { name: /Refused/ }).click();
await page.waitForTimeout(600);
await page.screenshot({ path: `${outDir}/a-refused.png`, fullPage: true });
console.log("REFUSED TAB:", (await page.locator("[role=tabpanel][data-state=active]").innerText()).replace(/\s+/g, " ").slice(0, 400));
await page.getByRole("tab", { name: /Apps/ }).click();
await page.waitForTimeout(400);
// the link cell must not open details; the row must
const pagesBefore = browser.contexts()[0].pages().length;
const live = page.locator("tbody tr", { hasText: "Live" }).first();
await live.locator("a").first().click({ modifiers: [] }).catch(() => {});
await page.waitForTimeout(800);
console.log("after link click, still on admin:", page.url().endsWith(admin), "new tabs:", browser.contexts()[0].pages().length - pagesBefore);
for (const p of browser.contexts()[0].pages()) if (p !== page) await p.close();
await page.locator("tbody tr").first().locator("td").first().click();
await page.waitForURL(/\/app\//, { timeout: 5000 }).catch(() => {});
await page.waitForTimeout(1200);
console.log("details url is /admin/<key>/app/<id>:", /\/admin\/[0-9a-f]+\/app\/[0-9a-f]+$/.test(page.url()));
await page.screenshot({ path: `${outDir}/a-details.png`, fullPage: true });
console.log("DETAILS:", (await page.innerText("body")).replace(/\s+/g, " ").slice(0, 700));
const bad = await page.request.get(base + "/api/admin/wrongkey/app/x");
console.log("wrong key API:", bad.status());
console.log("errors:", errors.length ? errors.join(" | ") : "none");
await browser.close();
