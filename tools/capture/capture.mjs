// Dev-only: capture an existing page at the 3 Pixel-Check breakpoints, normalised
// so the sandbox can fairly reproduce it (Inter/Plex fonts forced, media → solid blocks,
// animations off). Output is git-ignored; never commit, publish or report these.
//
// Usage: node capture.mjs <slug> <url> [--wait ms] [--hide "<css selectors>"] [--out dir] [--fonts dir] [--oracle]
//   --out    output root (default benchmarks-dev/)
//   --fonts  directory holding inter-latin-<w>-normal.woff2 etc. (default: @fontsource in node_modules; the sandbox
//            runtime image has them in /opt/pc/fonts)
//   --oracle also dump <bp>.oracle.json (exact text lines + computed styles + painted boxes from the live DOM) and
//            <bp>.notext.png (text made transparent) — the oracle spec for error attribution (tools/oracle_spec.py)
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : null; };
const OUT_ROOT = path.resolve(arg("--out") || path.resolve(HERE, "../../benchmarks-dev"));
const FONT_DIR = arg("--fonts");
const ORACLE = process.argv.includes("--oracle");
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
  fs.readFileSync(FONT_DIR ? path.join(FONT_DIR, file) : path.join(HERE, "node_modules/@fontsource", pkg, "files", file)).toString("base64");
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

// Oracle: what the frame shows, from the DOM (runs in the page). Text: one item per text node (or input placeholder),
// per-line rects, computed font size / weight / colour / letter-spacing / underline, a role from the element.
// Boxes: elements that paint (background different from what is beneath, a border, or a shadow), clipped to the
// viewport; one-sided borders become thin rules.
function oracleDom([vw, vh]) {
  // any CSS colour (rgb, oklch, lab, color(...) — Tailwind v4 uses oklch) → sRGB via a 1×1 canvas
  const cv = document.createElement("canvas"); cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true });
  const rgb = (c) => { if (!c || c === "transparent") return null;
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = "#000"; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = cx.getImageData(0, 0, 1, 1).data; return a ? { r, g, b, a: a / 255 } : null; };
  const hex = (c) => "#" + [c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  const visible = (el) => { for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
    const cs = getComputedStyle(a); if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.05) return false; } return true; };
  const beneath = (el) => { for (let a = el.parentElement; a; a = a.parentElement) {
    const c = rgb(getComputedStyle(a).backgroundColor); if (c && c.a > 0.5) return hex(c); } return "#ffffff"; };
  // what the eye sees: colour alpha × ancestor opacities, blended over the background beneath
  const opac = (el) => { let o = 1; for (let a = el; a && a !== document.documentElement; a = a.parentElement) o *= Number(getComputedStyle(a).opacity); return o; };
  const seen = (c, el, under) => { const a = c.a * opac(el); if (a >= 0.99) return c;
    const u = rgb(under) || { r: 255, g: 255, b: 255 }; return { r: c.r * a + u.r * (1 - a), g: c.g * a + u.g * (1 - a), b: c.b * a + u.b * (1 - a), a: 1 }; };
  const clip = (r) => { const x0 = Math.max(0, r.left), y0 = Math.max(0, r.top), x1 = Math.min(vw, r.right), y1 = Math.min(vh, r.bottom);
    return x1 - x0 >= 1 && y1 - y0 >= 1 ? [Math.round(x0), Math.round(y0), Math.round(x1 - x0), Math.round(y1 - y0)] : null; };
  // stable DOM path (same HTML at every breakpoint) — ground truth for cross-frame matching, evaluation only
  const dpath = (el) => { const parts = []; for (let a = el; a && a !== document.body; a = a.parentElement) {
    const sib = a.parentElement ? [...a.parentElement.children].indexOf(a) : 0; parts.push(`${a.tagName.toLowerCase()}:${sib}`); }
    return parts.reverse().join("/"); };
  const role = (el) => {
    const tag = (t) => el.closest(t);
    if (el.closest("button,[role=button],input[type=submit]")) return "button";
    if (/^H[1-3]$/.test(el.tagName) || el.closest("h1,h2,h3")) return "heading";
    if (el.closest("h4,h5,h6")) return "subheading";
    if (el.closest("a")) return el.closest("nav,header") ? "nav" : "link";
    if (el.closest("label")) return "label";
    return "body";
  };
  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const raw = n.textContent.replace(/\s+/g, " ").trim(); const el = n.parentElement;
    if (!raw || !el || !visible(el)) continue;
    const tt = getComputedStyle(el).textTransform;   // the eye (and OCR) sees the transformed string
    const t = tt === "uppercase" ? raw.toUpperCase() : tt === "lowercase" ? raw.toLowerCase()
      : tt === "capitalize" ? raw.replace(/\b\w/g, (m) => m.toUpperCase()) : raw;
    const range = document.createRange(); range.selectNodeContents(n);
    const lines = [...range.getClientRects()].map(clip).filter(Boolean);
    if (!lines.length) continue;
    const cs = getComputedStyle(el); const c0 = rgb(cs.color);
    if (!c0 || c0.a < 0.05) continue;
    const c = seen(c0, el, beneath(el.parentElement ? el : el));
    texts.push({ text: t, lines, line_height_px: parseFloat(cs.lineHeight) || null, size_px: parseFloat(cs.fontSize), weight: Number(cs.fontWeight) || 400, color: hex(c),
      letter_spacing_px: cs.letterSpacing === "normal" ? 0 : parseFloat(cs.letterSpacing) || 0,
      underline: (cs.textDecorationLine || "").includes("underline"), role: role(el), tag: el.tagName.toLowerCase(),
      align: cs.textAlign, path: dpath(el) + "#" + [...el.childNodes].indexOf(n) });
  }
  for (const el of document.querySelectorAll("input,textarea")) {
    if (!visible(el) || el.value || !el.placeholder) continue;
    const r = clip(el.getBoundingClientRect()); if (!r) continue;
    const ps = getComputedStyle(el, "::placeholder"); const cs = getComputedStyle(el); const c = rgb(ps.color) || rgb(cs.color);
    texts.push({ text: el.placeholder.replace(/\s+/g, " ").trim(), lines: [r], size_px: parseFloat(cs.fontSize),
      weight: Number(cs.fontWeight) || 400, color: c ? hex(c) : "#757575", letter_spacing_px: 0, underline: false,
      role: "input-placeholder", tag: el.tagName.toLowerCase(), placeholder: true, path: dpath(el) });
  }
  const blocks = [];
  for (const el of document.body.querySelectorAll("*")) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el); const R = el.getBoundingClientRect(); const box = clip(R);
    if (!box) continue;
    const bg = rgb(cs.backgroundColor); const under = beneath(el);
    const fill = bg && bg.a * opac(el) > 0.15 ? hex(seen(bg, el, under)) : null;
    // a translucent border (Tailwind black/10 on white) is visible: judge it by its blend over what is beneath
    const side = (s) => { const w = parseFloat(cs[`border${s}Width`]); const c0 = rgb(cs[`border${s}Color`]);
      if (!(w >= 0.5 && cs[`border${s}Style`] !== "none" && c0 && c0.a > 0.02)) return null;
      const c = seen(c0, el, fill || under); const u = rgb(fill || under) || { r: 255, g: 255, b: 255 };
      return Math.abs(c.r - u.r) + Math.abs(c.g - u.g) + Math.abs(c.b - u.b) >= 12 ? { w, c: hex(c) } : null; };
    const sides = { Top: side("Top"), Right: side("Right"), Bottom: side("Bottom"), Left: side("Left") };
    // a Tailwind ring is a box-shadow with 0 offset, 0 blur and a spread: it looks (and measures) like a border
    // (Tailwind stacks several layers, the first ones transparent 0-size placeholders: check each layer)
    const layers = (cs.boxShadow || "none") === "none" ? [] : cs.boxShadow.split(/,(?![^(]*\))/);
    let ringC = null;
    for (const L of layers) {
      const col = (L.match(/(rgba?\([^)]*\)|oklch\([^)]*\)|lab\([^)]*\)|color\([^)]*\)|#[0-9a-f]{3,8})/i) || [null])[0];
      const lens = [...L.replace(col || "", "").matchAll(/(-?\d+(?:\.\d+)?)px/g)].map((m) => parseFloat(m[1]));
      const c = rgb(col || cs.color);
      if (lens.length >= 4 && lens[0] === 0 && lens[1] === 0 && lens[2] === 0 && lens[3] >= 0.5 && c && c.a > 0.3) { ringC = c; break; }
    }
    // a bordered box cut by the viewport edge is still a bordered box (not three loose rules)
    const cut = { Top: R.top < 0.5, Right: R.right > vw - 0.5, Bottom: R.bottom > vh - 0.5, Left: R.left < 0.5 };
    const nSides = Object.values(sides).filter(Boolean).length;
    const all = nSides >= 2 && Object.keys(sides).every((k) => sides[k] || cut[k]) ? (sides.Top || sides.Left || sides.Right || sides.Bottom)
      : ringC && ringC.a > 0.3 ? { w: 1, c: hex(ringC) } : null;
    const shadow = cs.boxShadow && cs.boxShadow !== "none" && !ringC;
    const paintsFill = fill && fill !== under;
    if (paintsFill || all || shadow) {
      blocks.push({ box, fill: paintsFill || all || shadow ? fill : null, border: all ? all.c : null,
        radius: Math.round(parseFloat(cs.borderTopLeftRadius) || 0), shadow: !!shadow, tag: el.tagName.toLowerCase(), path: dpath(el) });
    }
    if (!all) for (const [s, v] of Object.entries(sides)) {
      if (!v) continue;
      const r = s === "Top" ? [R.left, R.top, R.width, v.w] : s === "Bottom" ? [R.left, R.bottom - v.w, R.width, v.w]
        : s === "Left" ? [R.left, R.top, v.w, R.height] : [R.right - v.w, R.top, v.w, R.height];
      const rb = clip({ left: r[0], top: r[1], right: r[0] + r[2], bottom: r[1] + r[3] });
      if (rb && (rb[2] >= 8 || rb[3] >= 8)) blocks.push({ box: rb, fill: v.c, rule: true, tag: el.tagName.toLowerCase(), path: dpath(el) + "|" + s });
    }
  }
  const pageBg = rgb(getComputedStyle(document.body).backgroundColor);
  const htmlBg = rgb(getComputedStyle(document.documentElement).backgroundColor);
  return { texts, blocks, background: pageBg && pageBg.a > 0.5 ? hex(pageBg) : htmlBg && htmlBg.a > 0.5 ? hex(htmlBg) : "#ffffff" };
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
    if (ORACLE) {
      const dom = await page.evaluate(oracleDom, [w, h]);
      fs.writeFileSync(path.join(outDir, `${bp}.oracle.json`), JSON.stringify(dom));
      await page.addStyleTag({ content: "*,*::before,*::after{color:transparent!important;-webkit-text-fill-color:transparent!important;" +
        "text-shadow:none!important;text-decoration-color:transparent!important}::placeholder{color:transparent!important}" });
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(outDir, `${bp}.notext.png`), fullPage: false });
    }
    meta.breakpoints[bp] = { width: w, height: h, media_replaced: replaced };
    console.log(`${slug} ${bp} ${w}x${h} media_replaced=${replaced}`);
    await ctx.close();
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2));
