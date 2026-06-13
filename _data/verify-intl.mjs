import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
await page.goto("file:///Users/siddharthrout/Desktop/Projects/karakai/index.html");
await page.waitForFunction(() => window.__karak && window.__karak.map && window.__karak.map.loaded(), null, { timeout: 20000 });
await page.waitForTimeout(2000);

// counts by state
const counts = await page.evaluate(() => {
  const by = {};
  for (const s of window.__karak.SPOTS) { const k = (s.country||"US")+"/"+s.state; by[k]=(by[k]||0)+1; }
  return by;
});
console.log("counts:", JSON.stringify(counts));

// placement sanity: every spot must sit inside its expected geo box
const BOX = {
  BH: [25.7,26.5,50.2,50.9], DU: [24.7,25.4,54.8,55.7], AD: [24.2,24.8,54.1,54.9],
  ON: [43.3,44.0,-80.1,-78.8], NY: [40.4,41.0,-74.3,-73.6], NJ: [40.5,41.0,-74.3,-73.9],
};
const oob = await page.evaluate((BOX) => {
  const bad = [];
  for (const s of window.__karak.SPOTS) {
    const b = BOX[s.state]; if (!b) continue;
    if (!(s.lat>=b[0] && s.lat<=b[1] && s.lng>=b[2] && s.lng<=b[3])) bad.push(`${s.name} (${s.state} ${s.lat},${s.lng})`);
  }
  return bad;
}, BOX);
console.log("placement out-of-box:", oob.length ? oob.length+" -> "+oob.slice(0,12).join(" | ") : "none");

// screenshot each region
const regions = ["bh","dubai","abudhabi","toronto","nyc","us"];
for (const r of regions) {
  await page.click(`.region-btn[data-region="${r}"]`);
  await page.waitForTimeout(2200);
  await page.screenshot({ path: `_data/shots/intl-${r}.png` });
}
console.log(errors.length ? "ERRORS:\n"+errors.join("\n") : "no console/page errors");
await browser.close();
