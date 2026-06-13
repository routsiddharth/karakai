import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
await page.goto("file:///Users/siddharthrout/Desktop/Projects/karakai/index.html");
await page.waitForFunction(() => window.__karak && window.__karak.map && window.__karak.map.loaded(), null, { timeout: 20000 });
// click Bahrain region button
await page.click('.region-btn[data-region="bh"]');
await page.waitForTimeout(3500);
await page.screenshot({ path: "shot-bahrain.png" });
// open a Bahrain spot card with fils pricing
await page.evaluate(() => {
  const s = window.__karak.SPOTS.find((x) => x.name.startsWith("Karak 1977 — Arad"));
  window.__karak.selectSpot(s, { fly: true });
});
await page.waitForTimeout(2800);
await page.screenshot({ path: "shot-bahrain-card.png" });
const count = await page.textContent("#spot-count");
console.log("spots in Bahrain view:", count.trim());
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console/page errors");
await browser.close();
