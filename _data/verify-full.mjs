import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
await page.goto("file:///Users/siddharthrout/Desktop/Projects/karakai/index.html");
await page.waitForFunction(() => window.__karak && window.__karak.map && window.__karak.map.loaded(), null, { timeout: 20000 });
await page.waitForTimeout(2500);

const all = await page.evaluate(() => window.__karak.SPOTS.length);
const bh = await page.evaluate(() => window.__karak.SPOTS.filter(s => s.state === "BH").length);
const ny = await page.evaluate(() => window.__karak.SPOTS.filter(s => s.state === "NY").length);
const qh = await page.evaluate(() => window.__karak.SPOTS.filter(s => s.name.startsWith("Qahwah House")).length);
console.log(`total=${all} bahrain=${bh} NY=${ny} qahwahHouse=${qh}`);

// Bahrain init screenshot
await page.screenshot({ path: "_data/shots/shot-bh-final.png" });

// switch to US, fly to Manhattan
await page.click('.region-btn[data-region="us"]');
await page.waitForTimeout(2500);
await page.screenshot({ path: "_data/shots/shot-us-final.png" });

// fly to Manhattan + open a Curry Hill spot
await page.evaluate(() => {
  const s = window.__karak.SPOTS.find(x => x.name === "Haandi");
  window.__karak.selectSpot(s);
});
await page.waitForTimeout(2600);
await page.screenshot({ path: "_data/shots/shot-manhattan.png" });

// dedupe sanity: any exact name+address dup?
const dups = await page.evaluate(() => {
  const seen = {}, out = [];
  for (const s of window.__karak.SPOTS) {
    const k = (s.name + "|" + s.address).toLowerCase();
    if (seen[k]) out.push(s.name); else seen[k] = 1;
  }
  return out;
});
console.log("exact dup name+address:", dups.length ? dups.join(", ") : "none");
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console/page errors");
await browser.close();
