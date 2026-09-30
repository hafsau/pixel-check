// Dev-only: capture an existing page at the 3 Pixel-Check breakpoints, normalised
// so the sandbox can fairly reproduce it (Inter/Plex fonts forced, media → solid blocks,
// animations off). Output is git-ignored; never commit, publish or report these.
//
// Usage: node capture.mjs <slug> <url> [--wait ms] [--hide "<css selectors>"]
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT_ROOT = path.resolve(HERE, "../../benchmarks-dev");
const BPS = { mobile: [390, 844], tablet: [768, 1024], desktop: [1280, 800] };

const [slug, url] = process.argv.slice(2);
const waitIdx = process.argv.indexOf("--wait");
const extraWait = waitIdx > 0 ? Number(process.argv[waitIdx + 1]) : 1500;
// --hide "<css selector list>" removes pop-ups, cookie banners, chat widgets.
const hideIdx = process.argv.indexOf("--hide");
const hideCss = hideIdx > 0 ? process.argv[hideIdx + 1] : "";
if (!slug || !url) {
  console.error("usage: node capture.mjs <slug> <url> [--wait ms]");
  process.exit(1);
}

const font = (pkg, file) =>
  fs.readFileSync(path.join(HERE, "node_modules/@fontsource", pkg, "files", file)).toString("base64");
const face = (family, pkg, w) =>
  `@font-face{font-family:'${family}';font-weight:${w};font-style:normal;` +
  `src:url(data:font/woff2;base64,${font(pkg, `${pkg}-latin-${w}-normal.woff2`)}) format('woff2');}`;
const FONT_CSS = [400, 500, 600, 700].map((w) => face("Inter", "inter", w)).join("") +
  [400, 500].map((w) => face("IBM Plex Mono", "ibm-plex-mono", w)).join("");

const NORMALISE_CSS = `${FONT_CSS}
*,*::before,*::after{font-family:'Inter',sans-serif!important;animation:none!important;
  transition:none!important;caret-color:transparent!important;background-image:none!important;
  -webkit-font-smoothing:antialiased!important}
code,pre,kbd,samp,code *,pre *{font-family:'IBM Plex Mono',monospace!important}
::-webkit-scrollbar{display:none!important} html{scrollbar-width:none!important}`;

// Replace media with solid blocks of the same box so the target is reproducible without images.
function replaceMedia() {
  const sel = "img,picture,video,canvas,iframe,object,embed,svg";
  const nodes = [...document.querySelectorAll(sel)].filter((n) => !n.parentElement?.closest("svg"));
  // Decorative = sits in an out-of-flow layer with no text, or is hidden from AT / faint.
  // Those are removed (not blocked out) so targets don't fill up with grey tile noise.
  const decorative = (n) => {
    const cs = getComputedStyle(n);
    if (Number(cs.opacity) < 0.5 || n.getAttribute("aria-hidden") === "true" && n.tagName !== "svg") return true;
    for (let a = n; a && a !== document.body; a = a.parentElement) {
      const p = getComputedStyle(a).position;
      if ((p === "absolute" || p === "fixed") && !a.innerText?.trim()) return true;
    }
    return false;
  };
  for (const n of nodes) {
    const r = n.getBoundingClientRect();
    const cs = getComputedStyle(n);
    if (decorative(n)) { n.style.setProperty("visibility", "hidden", "important"); continue; }
    const d = document.createElement("div");
    d.style.cssText = `display:${cs.display === "inline" ? "inline-block" : cs.display};` +
      `width:${r.width}px;height:${r.height}px;background:#d4d4d8;` +
      `border-radius:${cs.borderRadius};flex-shrink:0;margin:${cs.margin};vertical-align:middle;` +
      (cs.position !== "static" ? `position:${cs.position};top:${cs.top};left:${cs.left};right:${cs.right};bottom:${cs.bottom};` : "");
    if (r.width === 0 || r.height === 0) d.style.display = "none";
    n.replaceWith(d);
  }
  return nodes.length;
}

const outDir = path.join(OUT_ROOT, slug);
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const meta = { slug, url, captured_at: new Date().toISOString(), dev_only: true, breakpoints: {} };
try {
  for (const [bp, [w, h]] of Object.entries(BPS)) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
    await page.addStyleTag({ content: NORMALISE_CSS + (hideCss ? `${hideCss}{display:none!important}` : "") });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(extraWait);
    const replaced = await page.evaluate(replaceMedia);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    // Ground-truth visible text inside the viewport (for scorer tests and VLM accuracy in G3).
    const texts = await page.evaluate(([vw, vh]) => {
      const out = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const t = n.textContent.replace(/\s+/g, " ").trim();
        const el = n.parentElement;
        if (!t || !el) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
        const range = document.createRange(); range.selectNodeContents(n);
        const r = range.getBoundingClientRect();
        if (r.width < 1 || r.height < 1 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
        out.push({ text: t, box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] });
      }
      return out;
    }, [w, h]);
    fs.writeFileSync(path.join(outDir, `${bp}.text.json`), JSON.stringify(texts, null, 1));
    const file = path.join(outDir, `${bp}.png`);
    await page.screenshot({ path: file, fullPage: false });
    meta.breakpoints[bp] = { width: w, height: h, media_replaced: replaced };
    console.log(`${slug} ${bp} ${w}x${h} media_replaced=${replaced}`);
    await ctx.close();
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2));
