import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await page.goto("file:///Users/siddharthrout/Desktop/Projects/karakai/index.html");
await page.waitForFunction(() => window.__karak && window.__karak.map && window.__karak.map.loaded(), null, { timeout: 20000 });
await page.evaluate(() => {
  const s = window.__karak.SPOTS.find((x) => x.name === "Karak Tea Bakery & Cafe");
  window.__karak.selectSpot(s, { fly: false });
});
await page.waitForTimeout(600);
await page.click(".c-hours summary");
await page.waitForTimeout(300);
await page.locator("#card").screenshot({ path: "card-closeup.png" });
// search ranking check
await page.fill("#search", "houston");
await page.waitForTimeout(400);
const first = await page.textContent(".search-result .r-name");
console.log("first result for 'houston':", first.trim());
await browser.close();
