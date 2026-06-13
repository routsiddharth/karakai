import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

await page.goto("file:///Users/siddharthrout/Desktop/Projects/karakai/index.html");
await page.waitForFunction(() => window.__karak && window.__karak.map && window.__karak.map.loaded(), null, { timeout: 20000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: "shot-country.png" });

// open a spot card (Qahwah House Dearborn)
await page.evaluate(() => {
  const s = window.__karak.SPOTS.find((x) => x.name === "Qahwah House" && x.city === "Dearborn");
  window.__karak.selectSpot(s);
});
await page.waitForTimeout(2600);
await page.screenshot({ path: "shot-card.png" });

// expand hours
await page.click(".c-hours summary");
await page.waitForTimeout(300);
await page.screenshot({ path: "shot-card-hours.png" });

// search interaction
await page.evaluate(() => document.getElementById("card-close").click());
await page.fill("#search", "houston");
await page.waitForTimeout(400);
await page.screenshot({ path: "shot-search.png" });
await page.keyboard.press("Enter");
await page.waitForTimeout(2200);
await page.screenshot({ path: "shot-city.png" });

// open-now filter
await page.click("#chip-open");
await page.waitForTimeout(700);
await page.screenshot({ path: "shot-filter.png" });

const count = await page.textContent("#spot-count");
console.log("spot count after filter+houston view:", count.trim());
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console/page errors");
await browser.close();
