// qa: Marco's simple admin page (arc-eng/hq#782, 7:52 pm): title, table right below it, quick access with words and the
// publish controls; no metric widgets, no refused requests. Row click still opens details. Run against pages_local.py.
// Never clicks Publish (it publishes for real).
// PW_EXE=<chromium> bun tests/acceptance/admin_simple_check.ts <base url> <paths file> <out dir>
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";

const [base, pathsFile, outDir] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const admin = readFileSync(pathsFile, "utf8").split("\n")[0];
const browser = await chromium.launch({ executablePath: process.env.PW_EXE });
const errors: string[] = [];
for (const [w, h] of [[1440, 900], [1920, 1080], [1024, 768]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto(base + admin, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${outDir}/admin-${w}.png`, fullPage: true });
  const r = await page.evaluate(() => {
    const top = (el: Element | null) => (el ? Math.round(el.getBoundingClientRect().top) : -1);
    const h1 = document.querySelector("h1");
    const table = document.querySelector("table");
    const qa = [...document.querySelectorAll("h2")].find((e) => e.textContent?.includes("Quick access"));
    return {
      h1Bottom: h1 ? Math.round(h1.getBoundingClientRect().bottom) : -1, tableTop: top(table), quickTop: top(qa ?? null),
      tableBottom: table ? Math.round(table.getBoundingClientRect().bottom) : -1,
      tabs: document.querySelectorAll("[role=tab]").length, hscroll: document.documentElement.scrollWidth > innerWidth,
    };
  });
  const body = (await page.innerText("body")).replace(/\s+/g, " ");
  const rows = await page.locator("section li").evaluateAll((lis) =>
    lis.map((li) => li.textContent?.replace(/\s+/g, " ").trim()),
  );
  console.log(`== ${w}x${h}`, JSON.stringify(r));
  console.log("mentions refused:", /refus/i.test(body), "| widgets:", /People\b.*Live apps|Sandbox minutes|Building now/.test(body));
  console.log("quick access rows:\n  " + rows.join("\n  "));
  const links = await page.locator("section a").evaluateAll((as) => as.map((a) => `${a.textContent?.trim()} -> ${a.getAttribute("target")} ${a.getAttribute("href")?.slice(0, 70)}`));
  console.log("links:\n  " + links.join("\n  "));
  if (w === 1440) {
    await page.locator("tbody tr").first().locator("td").first().click();
    await page.waitForURL(/\/app\//, { timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(1000);
    console.log("row click opens details:", /\/admin\/[0-9a-f]+\/app\/[0-9a-f]+$/.test(page.url()));
    await page.screenshot({ path: `${outDir}/details-1440.png`, fullPage: true });
  }
  await page.close();
}
console.log("errors:", errors.length ? errors.join(" | ") : "none");
await browser.close();
