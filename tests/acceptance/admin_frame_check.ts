// qa: the admin page in Marco's SaaS frame (arc-eng/hq#782, 8:24 pm): navbar (name + Sam), sidebar Quick access (publish
// under Golden image) then Builders (click filters via ?who=), apps in main; details page in the same frame.
// Run against pages_local.py. Never clicks Publish (it publishes for real).
// PW_EXE=<chromium> bun tests/acceptance/admin_frame_check.ts <base url> <paths file> <out dir>
import { chromium, type Page } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";

const [base, pathsFile, outDir] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const admin = readFileSync(pathsFile, "utf8").split("\n")[0];
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const errors: string[] = [];
const open = async (w: number, h: number) => {
  const p = await browser.newPage({ viewport: { width: w, height: h } });
  p.on("pageerror", (e) => errors.push(String(e)));
  p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  p.on("dialog", (d) => { errors.push("DIALOG " + d.message()); d.dismiss(); });
  return p;
};
const settle = async (p: Page) => { await p.waitForLoadState("networkidle"); await p.waitForTimeout(2500); };
const rows = (p: Page) => p.locator("main tbody tr").evaluateAll((t) => t.map((r) => r.textContent?.replace(/\s+/g, " ").trim()));
const hscroll = (p: Page) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth);

for (const [w, h] of [[1920, 1080], [1440, 900], [1280, 800], [1024, 768]]) {
  const p = await open(w, h);
  await p.goto(base + admin, { waitUntil: "networkidle" });
  await settle(p);
  await p.screenshot({ path: `${outDir}/admin-${w}.png` });
  console.log(`== ${w}x${h} hscroll=${await hscroll(p)} navbar="${(await p.locator("header").innerText()).replace(/\s+/g, " ")}"`);
  if (w !== 1440) { await p.close(); continue; }
  const side = (await p.locator("aside").innerText()).replace(/\s+/g, " ");
  console.log("sidebar:", side);
  console.log("order Quick access < Builders:", side.indexOf("Quick access".toUpperCase()) >= 0 ? side.toUpperCase().indexOf("QUICK ACCESS") < side.toUpperCase().indexOf("BUILDERS") : "?");
  console.log("publish under Golden image:", side.indexOf("Golden image") < side.search(/Publish/) && side.search(/Publish/) < side.indexOf("App servers"));
  console.log("quick links:", await p.locator("aside nav").first().locator("a").evaluateAll((as) => as.map((a) => `${a.textContent?.trim()}[${a.getAttribute("target")}] title="${a.getAttribute("title")}"`)));
  console.log("rows (all):", (await rows(p)).length);
  await p.locator("aside a", { hasText: "Diego" }).click();
  await settle(p);
  console.log("filter Diego url:", p.url().slice(p.url().indexOf("?")), "| rows:", await rows(p));
  console.log("chip:", (await p.locator("main").innerText()).split("\n").slice(0, 2).join(" | "));
  await p.screenshot({ path: `${outDir}/filter-diego.png` });
  await p.locator("main a, main button", { hasText: "✕" }).first().click();
  await settle(p);
  console.log("after ✕ url has who:", p.url().includes("who="), "| rows:", (await rows(p)).length);
  await p.locator("aside a", { hasText: "Priya" }).click();
  await settle(p);
  console.log("filter Priya rows:", await rows(p));
  await p.goto(base + admin + "?who=" + encodeURIComponent('<img src=x onerror=alert(1)>'), { waitUntil: "networkidle" });
  await settle(p);
  console.log("xss param: injected img in DOM:", await p.locator("main img[src=x]").count());
  await p.goto(base + admin, { waitUntil: "networkidle" });
  await settle(p);
  await p.locator("main tbody tr").first().locator("td").first().click();
  await p.waitForURL(/\/app\//, { timeout: 5000 }).catch(() => {});
  await settle(p);
  console.log("details in frame: header", await p.locator("header").count(), "aside", await p.locator("aside").count(), "builders", await p.locator("aside nav").nth(1).locator("a").count(), "hscroll", await hscroll(p));
  await p.screenshot({ path: `${outDir}/details-1440.png` });
  await p.locator("aside a", { hasText: "Maya" }).click();
  await settle(p);
  console.log("builder link from details ->", p.url().replace(/\/admin\/[0-9a-f]+/, "/admin/<key>"), "| rows:", await rows(p));
  await p.close();
}
console.log("errors:", errors.length ? errors.join(" | ") : "none");
await browser.close();
