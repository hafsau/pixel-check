// Calibration render: full-page screenshot + span boxes for out/calib/App.jsx (local only).
import { chromium } from "playwright";
import fs from "node:fs";
import { build } from "./render.mjs";
const html = await build(process.argv[2], []);
const b = await chromium.launch({ args: ["--font-render-hinting=none"] });
const p = await (await b.newContext({ viewport: { width: 1280, height: 9000 }, deviceScaleFactor: 1 })).newPage();
await p.setContent(html, { waitUntil: "load" });
await p.evaluate(() => document.fonts.ready);
await p.screenshot({ path: process.argv[3], fullPage: true });
const boxes = await p.evaluate(() => [...document.querySelectorAll("#root span")].map((s) => {
  const r = s.parentElement.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }));
fs.writeFileSync(process.argv[4], JSON.stringify(boxes));
await b.close();
