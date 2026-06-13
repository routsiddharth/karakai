import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await page.goto("file:///Users/siddharthrout/Desktop/Projects/karakai/index.html");
await page.waitForFunction(() => window.__karak && window.__karak.map && window.__karak.map.loaded(), null, { timeout: 20000 });
await page.waitForTimeout(1200);
await page.evaluate(() => {
  const s = window.__karak.SPOTS.find((x) => x.city === "Brooklyn");
  window.__karak.selectSpot(s, { fly: false });
});
await page.waitForTimeout(500);
await page.screenshot({ path: "shot-mobile.png" });
await browser.close();
