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
//   --wait   the most to wait for the layout to settle (no DOM change / new resource for 500 ms); sizes run in parallel
//   --assets also save the page's own images (assets/<sha256>.<ext>, checked by signature; inline SVG icons sanitised)
//            and assets.json with every occurrence's box per size — for owned sites only (the live API decides)
//   --real   also save <bp>.real.png: the page as it looks (own fonts and media), loaders / cookie bars hidden
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";
import { makeGuard, sensitiveScan } from "./guard.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : null; };
const OUT_ROOT = path.resolve(arg("--out") || path.resolve(HERE, "../../benchmarks-dev"));
const FONT_DIR = arg("--fonts");
const ORACLE = process.argv.includes("--oracle");
// state frames (interactions): --state <name> --click "<css selector>" [--bps mobile,tablet] — after the base page is
// normalised, click the trigger and capture <bp>.<name>.{png,text.json,oracle.json,notext.png}; the trigger's box
// (before the click) is stored in meta-<name>.json so the pipeline can find it in the base frame
const STATE = arg("--state");
const CLICK = arg("--click");
const ONLY = (arg("--bps") || "").split(",").filter(Boolean);
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
    // large graphics inside an aria-hidden wrapper (waves, section dividers, backdrops); icons stay blocks
    const r = n.getBoundingClientRect();
    if (n.parentElement?.closest('[aria-hidden="true"]') &&
        (r.width >= innerWidth * 0.5 || r.width * r.height >= innerWidth * innerHeight * 0.05)) return true;
    for (let a = n; a && a !== document.body; a = a.parentElement) {
      const p = getComputedStyle(a).position;
      if ((p === "absolute" || p === "fixed") && !a.innerText?.trim()) return true;
    }
    return false;
  };
  for (const n of nodes) {
    const r = n.getBoundingClientRect();
    const cs = getComputedStyle(n);
    // not rendered now (e.g. inside a closed disclosure): left alone — the pass after a state click replaces it at
    // its real size (a display:none placeholder would stay hidden when the content opens)
    if (r.width === 0 || r.height === 0) continue;
    if (decorative(n)) { n.style.setProperty("visibility", "hidden", "important"); continue; }
    const d = document.createElement("div");
    d.dataset.pcMedia = "1";
    d.style.cssText = `display:${cs.display === "inline" ? "inline-block" : cs.display};` +
      `width:${r.width}px;height:${r.height}px;background:#d4d4d8;` +
      `border-radius:${cs.borderRadius};flex-shrink:0;margin:${cs.margin};vertical-align:middle;` +
      (cs.position !== "static" ? `position:${cs.position};top:${cs.top};left:${cs.left};right:${cs.right};bottom:${cs.bottom};` : "");
    n.replaceWith(d);
  }
  return nodes.length;
}

// Owned-site images (--assets): every visible <img> (its current source) and inline <svg> icon, with its box in page
// coordinates. SVGs are serialised with currentColor resolved; the bytes of <img>s come from the page's own responses.
function collectAssets() {
  const out = [];
  for (const n of document.querySelectorAll("img, svg")) {
    if (n.tagName.toLowerCase() === "svg" && n.parentElement?.closest("svg")) continue;
    const r = n.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    const box = [r.x + scrollX, r.y + scrollY, r.width, r.height].map(Math.round);
    if (n.tagName.toLowerCase() === "img") { out.push({ kind: "img", src: n.currentSrc || n.src, box, alt: (n.alt || "").trim().slice(0, 200) }); continue; }
    const c = n.cloneNode(true);
    const color = getComputedStyle(n).color;
    c.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    c.setAttribute("width", String(Math.round(r.width)));
    c.setAttribute("height", String(Math.round(r.height)));
    c.removeAttribute("class"); c.removeAttribute("style");
    for (const e of [c, ...c.querySelectorAll("*")])
      for (const a of [...e.attributes]) if (/currentcolor/i.test(a.value)) e.setAttribute(a.name, a.value.replace(/currentcolor/gi, color));
    if (!c.getAttribute("fill") && !/fill=/.test(c.innerHTML)) c.setAttribute("fill", color);
    out.push({ kind: "svg", markup: c.outerHTML, box });
  }
  return out;
}

const SIG = [["png", (b) => b.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))],
             ["jpg", (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff],
             ["gif", (b) => b.subarray(0, 4).toString("latin1") === "GIF8"],
             ["webp", (b) => b.subarray(0, 4).toString("latin1") === "RIFF" && b.subarray(8, 12).toString("latin1") === "WEBP"],
             ["avif", (b) => b.subarray(4, 12).toString("latin1") === "ftypavif"]];
const sniff = (b) => (SIG.find(([, ok]) => b.length > 12 && ok(b)) || [null])[0];
const UNSAFE_SVG = /<script|<foreignobject|<iframe|<use[^>]+href\s*=\s*["'](?!#)|\son\w+\s*=|(?:xlink:)?href\s*=\s*["']\s*(?:javascript|data|https?):/i;
const ASSET_MAX = 5e6, ASSET_COUNT = 60;
const assets = new Map();                 // hash → {hash, ext, kind, boxes: {bp: [[x, y, w, h], …]}}
function addAsset(bp, ext, kind, bytes, box, alt = "") {
  const hash = crypto.createHash("sha256").update(bytes).digest("hex");
  if (!assets.has(hash)) {
    if (assets.size >= ASSET_COUNT) return;
    fs.mkdirSync(path.join(outDir, "assets"), { recursive: true });
    fs.writeFileSync(path.join(outDir, "assets", `${hash}.${ext}`), bytes);
    assets.set(hash, { hash, ext, kind, bytes: bytes.length, alt: "", boxes: {} });
  }
  if (alt && !assets.get(hash).alt) assets.get(hash).alt = alt;
  (assets.get(hash).boxes[bp] ||= []).push(box);
}

// Full-screen loaders (fixed, topmost over most of the viewport, ≤ 3 words) and cookie / consent bars are hidden:
// they are not the page. A fixed background layer stays (content paints above it, so it is not topmost).
function hideOverlays() {
  const vw = innerWidth, vh = innerHeight;
  const pts = [[0.5, 0.5], [0.2, 0.2], [0.8, 0.2], [0.2, 0.8], [0.8, 0.8]].map(([x, y]) => [x * vw, y * vh]);
  let hidden = 0;
  for (const el of [...document.body.querySelectorAll("*")]) {
    const cs = getComputedStyle(el);
    if (cs.position !== "fixed" || cs.display === "none") continue;
    const r = el.getBoundingClientRect();
    const area = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
    const text = (el.innerText || "").trim();
    const words = text ? text.split(/\s+/).length : 0;
    const top = pts.filter(([x, y]) => { const h = document.elementFromPoint(x, y); return h && el.contains(h); }).length;
    const loader = area >= 0.6 * vw * vh && top >= 4 && words <= 3;
    const consent = area < 0.6 * vw * vh &&
      /\b(we use cookies|this (site|website) uses cookies|accept (all )?cookies|cookie (settings|preferences)|consent)\b/i.test(text);
    if (loader || consent) { el.style.setProperty("display", "none", "important"); hidden++; }
  }
  return hidden;
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
  // visible = not clipped away by an overflow:hidden ancestor (collapsed submenus) and not under an OPAQUE layer at
  // every sample point (an open menu over the hero). A transparent layer on top (a label over its input, a stretched
  // link over a card) does not hide anything.
  const clippedOut = (el, r) => {
    const cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2;
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.overflow === "visible" && cs.overflowX === "visible" && cs.overflowY === "visible") continue;
      const b = a.getBoundingClientRect();
      if (cx < b.left - 1 || cx > b.right + 1 || cy < b.top - 1 || cy > b.bottom + 1) return true;
    }
    return false;
  };
  const coveredAt = (el, x, y) => {
    const hit = document.elementFromPoint(x, y);
    if (!hit || hit === el || el.contains(hit)) return false;
    for (let a = hit; a && !a.contains(el); a = a.parentElement) {
      const c = rgb(getComputedStyle(a).backgroundColor);
      if ((c && c.a > 0.5) || a.dataset.pcMedia) return true;
    }
    return false;
  };
  const onTop = (el, r) => !clippedOut(el, r) &&
    [[0.5, 0.5], [0.2, 0.5], [0.8, 0.5]].some(([fx, fy]) => !coveredAt(el, r[0] + r[2] * fx, r[1] + r[3] * fy));
  // colour codes for the "is it painted?" passes (oracle_spec checks each element's colour in its box)
  let nCode = 0;
  const code = (el, attr) => {
    if (!el.dataset[attr]) {
      const i = ++nCode, hh = ((i * 137.508) % 360) / 60, l = i % 2 ? 0.42 : 0.58, ch = 1 - Math.abs(2 * l - 1);
      const xx = ch * (1 - Math.abs((hh % 2) - 1)), m = l - ch / 2;
      const [r1, g1, b1] = hh < 1 ? [ch, xx, 0] : hh < 2 ? [xx, ch, 0] : hh < 3 ? [0, ch, xx] : hh < 4 ? [0, xx, ch] : hh < 5 ? [xx, 0, ch] : [ch, 0, xx];
      el.dataset[attr] = "#" + [r1 + m, g1 + m, b1 + m].map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("");
    }
    return el.dataset[attr];
  };
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
    const lines = [...range.getClientRects()].map(clip).filter(Boolean).filter((r) => onTop(el, r));
    if (!lines.length) continue;
    const cs = getComputedStyle(el); const c0 = rgb(cs.color);
    if (!c0 || c0.a < 0.05) continue;
    const c = seen(c0, el, beneath(el.parentElement ? el : el));
    texts.push({ text: t, lines, line_height_px: parseFloat(cs.lineHeight) || null, size_px: parseFloat(cs.fontSize), weight: Number(cs.fontWeight) || 400, color: hex(c),
      letter_spacing_px: cs.letterSpacing === "normal" ? 0 : parseFloat(cs.letterSpacing) || 0,
      underline: (cs.textDecorationLine || "").includes("underline"), role: role(el), tag: el.tagName.toLowerCase(),
      align: cs.textAlign, path: dpath(el) + "#" + [...el.childNodes].indexOf(n), code: code(el, "pct") });
  }
  for (const el of document.querySelectorAll("input,textarea")) {
    if (!visible(el) || el.value || !el.placeholder) continue;
    const r = clip(el.getBoundingClientRect()); if (!r || !onTop(el, r)) continue;
    const ps = getComputedStyle(el, "::placeholder"); const cs = getComputedStyle(el); const c = rgb(ps.color) || rgb(cs.color);
    texts.push({ text: el.placeholder.replace(/\s+/g, " ").trim(), lines: [r], size_px: parseFloat(cs.fontSize),
      weight: Number(cs.fontWeight) || 400, color: c ? hex(c) : "#757575", letter_spacing_px: 0, underline: false,
      role: "input-placeholder", tag: el.tagName.toLowerCase(), placeholder: true, path: dpath(el), code: code(el, "pct") });
  }
  const blocks = [];
  for (const el of document.body.querySelectorAll("*")) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el); const R = el.getBoundingClientRect(); const box = clip(R);
    if (!box) continue;
    // a box under an opaque layer everywhere we look (page content under an open menu) is not in the frame
    const covered = clippedOut(el, box) || [[0.5, 0.5], [0.1, 0.1], [0.9, 0.1], [0.1, 0.9], [0.9, 0.9]]
      .every(([fx, fy]) => coveredAt(el, box[0] + box[2] * fx, box[1] + box[3] * fy));
    if (covered) continue;
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
        radius: Math.round(parseFloat(cs.borderTopLeftRadius) || 0), shadow: !!shadow, tag: el.tagName.toLowerCase(), path: dpath(el),
        code: code(el, "pcb") });
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

// live mode (--block-private): never reach localhost / private / link-local / reserved addresses — checked for the
// redirect chain before the browser goes (preflight) and for every request the page makes (route + DNS lookup)
const BLOCK_PRIVATE = process.argv.includes("--block-private");
const ASSETS = process.argv.includes("--assets");  // also save the page's own images → assets/ + assets.json
const REAL = process.argv.includes("--real");     // also save {bp}.real.png: the page as it looks (own fonts, media)
const guard = makeGuard(url);
const { preflight, blocked } = guard;

const outDir = path.join(OUT_ROOT, slug);
fs.mkdirSync(outDir, { recursive: true });
let preHops = null;
if (BLOCK_PRIVATE) {
  try { preHops = await preflight(url); }
  catch (e) { console.error(String(e.message || e)); process.exit(3); }
}
// "layout settled": no DOM change and no new resource for QUIET_MS, at most maxMs (the old fixed wait, now a cap)
const QUIET_MS = 500;
async function settle(page, maxMs) {
  await page.evaluate(async ([quiet, max]) => {
    let last = performance.now();
    const bump = () => { last = performance.now(); };
    const mo = new MutationObserver(bump);
    mo.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
    let po = null;
    try { po = new PerformanceObserver(bump); po.observe({ type: "resource" }); } catch (e) { /* not supported */ }
    const t0 = performance.now();
    while (performance.now() - t0 < max && performance.now() - last < quiet)
      await new Promise((r) => setTimeout(r, 50));
    mo.disconnect();
    if (po) po.disconnect();
  }, [Math.min(QUIET_MS, maxMs), maxMs]);
}

const browser = await chromium.launch();
const meta = { slug, url, captured_at: new Date().toISOString(), dev_only: true, breakpoints: {},
               sensitive: { password: 0, payment: 0, signin: 0, crypto: 0 } };
const navs = {};                         // per size: where it went (a page may redirect at one width only)
try {
  // the three sizes in parallel, one browser context each
  await Promise.all(Object.entries(BPS).filter(([bp]) => !ONLY.length || ONLY.includes(bp)).map(async ([bp, [w, h]]) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    if (BLOCK_PRIVATE) await guard.route(ctx);
    const bodies = new Map(), pending = [];
    if (ASSETS) page.on("response", (resp) => {
      if (resp.request().resourceType() !== "image") return;
      pending.push(resp.body().then((b) => { if (b.length <= ASSET_MAX) bodies.set(resp.url(), b); }).catch(() => {}));
    });
    // "networkidle" never comes on some pages (lambda.ai: background requests) — load, then idle if it comes
    const resp = await page.goto(url, { waitUntil: "load", timeout: 60000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    {                                    // where the capture really went (checked again by the live API)
      const chain = [];
      for (let r = resp && resp.request(); r; r = r.redirectedFrom()) chain.unshift(r.url());
      const addr = resp ? await resp.serverAddr().catch(() => null) : null;
      navs[bp] = { finals: [page.url()], hops: preHops || (chain.length ? chain : [url]),
                   server_ip: addr ? addr.ipAddress : null,
                   page: await page.evaluate(() => ({ title: document.title || "",
                     site_name: (document.querySelector('meta[property="og:site_name"]') || {}).content || "" })) };
    }
    for (const f of page.frames()) {     // before media are replaced (an iframe becomes a grey block)
      const s2 = await f.evaluate(sensitiveScan).catch(() => null);
      if (s2) for (const k of Object.keys(s2)) meta.sensitive[k] = Math.max(meta.sensitive[k], s2[k]);
    }
    await settle(page, extraWait);
    const overlays = await page.evaluate(hideOverlays);
    if (REAL) await page.screenshot({ path: path.join(outDir, `${bp}${STATE ? `.${STATE}` : ""}.real.png`), fullPage: false });
    await page.addStyleTag({ content: NORMALISE_CSS + (hideCss ? `${hideCss}{display:none!important}` : "") });
    await page.evaluate(() => document.fonts.ready);
    await settle(page, Math.min(extraWait, 1000));     // the normalised fonts re-flow the page
    if (ASSETS) {
      const found = await page.evaluate(collectAssets);
      await Promise.all(pending);
      for (const a of found) {
        if (a.kind === "img") {
          const b = bodies.get(a.src);
          const ext = b && sniff(b);
          if (ext) addAsset(bp, ext, "img", b, a.box, a.alt);
        } else if (a.markup.length <= 100000 && !UNSAFE_SVG.test(a.markup)) {
          addAsset(bp, "svg", "svg", Buffer.from(a.markup, "utf8"), a.box);
        }
      }
    }
    const replaced = await page.evaluate(replaceMedia);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    const suffix = STATE ? `.${STATE}` : "";
    if (STATE) {
      const el = page.locator(CLICK).first();
      const tb = await el.boundingBox();
      meta.trigger = meta.trigger || {};
      meta.trigger[bp] = { selector: CLICK, box: tb && [Math.round(tb.x), Math.round(tb.y), Math.round(tb.width), Math.round(tb.height)] };
      await el.click();
      await page.waitForTimeout(700);
      // media revealed or re-rendered by the click gets the same treatment as the base frame's
      await page.evaluate(replaceMedia);
      await page.waitForTimeout(100);
    }
    // Ground-truth visible text inside the viewport (for scorer tests and VLM accuracy in G3).
    const texts = await page.evaluate(([vw, vh]) => {
      const out = [];
      // split-text animations wrap each letter in its own element: ≥ 3 children of ≤ 2 characters and no text of
      // the parent's own = ONE word on screen (the target string is the word, its box the letters' union)
      const split = new Set();
      for (const e of document.body.querySelectorAll("*")) {
        const kids = [...e.children];
        if (kids.length < 3 || [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())) continue;
        const lens = kids.map((k) => k.textContent.trim().length);
        if (lens.every((l) => l <= 2) && lens.filter((l) => l > 0).length >= 3 && kids.every((k) => !k.children.length))
          split.add(e);
      }
      const inSplit = (el) => el && split.has(el.parentElement);
      for (const e of split) {
        const cs = getComputedStyle(e);
        if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
        const boxes = [...e.children].map((k) => k.getBoundingClientRect()).filter((r) => r.width >= 1 && r.height >= 1 &&
          r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw);
        if (!boxes.length) continue;
        // letters joined as seen: a space only where the gap between letters looks like one (> 0.15 em)
        const fs = parseFloat(cs.fontSize) || 16;
        let raw = "", prev = null;
        for (const k of e.children) {
          const r = k.getBoundingClientRect(), ch = k.textContent.trim();
          if (!ch) { continue; }
          if (prev && r.left - prev.right > 0.15 * fs) raw += " ";
          raw += ch;
          prev = r;
        }
        const t = cs.textTransform === "uppercase" ? raw.toUpperCase() : cs.textTransform === "lowercase" ? raw.toLowerCase() : raw;
        const x0 = Math.min(...boxes.map((r) => r.left)), y0 = Math.min(...boxes.map((r) => r.top));
        const x1 = Math.max(...boxes.map((r) => r.right)), y1 = Math.max(...boxes.map((r) => r.bottom));
        out.push({ text: t, box: [Math.round(x0), Math.round(y0), Math.round(x1 - x0), Math.round(y1 - y0)] });
      }
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const raw = n.textContent.replace(/\s+/g, " ").trim();
        const el = n.parentElement;
        if (!raw || !el || inSplit(el)) continue;
        const cs = getComputedStyle(el);
        // ground truth = what is on screen: CSS text-transform applied (as in the oracle dump)
        const t = cs.textTransform === "uppercase" ? raw.toUpperCase() : cs.textTransform === "lowercase" ? raw.toLowerCase()
          : cs.textTransform === "capitalize" ? raw.replace(/\b\w/g, (m) => m.toUpperCase()) : raw;
        if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
        const range = document.createRange(); range.selectNodeContents(n);
        const r = range.getBoundingClientRect();
        if (r.width < 1 || r.height < 1 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
        out.push({ text: t, box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] });
      }
      return out;
    }, [w, h]);
    fs.writeFileSync(path.join(outDir, `${bp}${suffix}.text.json`), JSON.stringify(texts, null, 1));
    const file = path.join(outDir, `${bp}${suffix}.png`);
    await page.screenshot({ path: file, fullPage: false });
    navs[bp].finals.push(page.url());    // a late script may have navigated after the first record
    if (ORACLE) {
      const dom = await page.evaluate(oracleDom, [w, h]);
      fs.writeFileSync(path.join(outDir, `${bp}${suffix}.oracle.json`), JSON.stringify(dom));
      await page.addStyleTag({ content: "*,*::before,*::after{color:transparent!important;-webkit-text-fill-color:transparent!important;" +
        "text-shadow:none!important;text-decoration-color:transparent!important}::placeholder{color:transparent!important}" });
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(outDir, `${bp}${suffix}.notext.png`), fullPage: false });
      // painted-or-not passes: each text element in its own colour (everything else transparent text), then each
      // block in its own background colour — an element counts only where its colour actually reaches the screen
      // (closed <details>, opacity tricks, overlays, clipping: all handled the same way)
      const css = await page.evaluate(() => {
        const t = [...document.querySelectorAll("[data-pct]")].map((e) =>
          `[data-pct="${e.dataset.pct}"],[data-pct="${e.dataset.pct}"]::placeholder{color:${e.dataset.pct}!important;-webkit-text-fill-color:${e.dataset.pct}!important;text-decoration-color:transparent!important}`);
        const b = [...document.querySelectorAll("[data-pcb]")].map((e) =>
          `[data-pcb="${e.dataset.pcb}"]{background-color:${e.dataset.pcb}!important;border-color:${e.dataset.pcb}!important;box-shadow:none!important}`);
        return { t: t.join("\n"), b: b.join("\n") };
      });
      const tStyle = await page.addStyleTag({ content: css.t });
      await page.waitForTimeout(100);
      await page.screenshot({ path: path.join(outDir, `${bp}${suffix}.tcoded.png`), fullPage: false });
      await tStyle.evaluate((n) => n.remove());
      await page.addStyleTag({ content: css.b });
      await page.waitForTimeout(100);
      await page.screenshot({ path: path.join(outDir, `${bp}${suffix}.bcoded.png`), fullPage: false });
    }
    meta.breakpoints[bp] = { width: w, height: h, media_replaced: replaced, overlays_hidden: overlays };

    console.log(`${slug} ${bp} ${w}x${h} media_replaced=${replaced}`);
    await ctx.close();
  }));
} finally {
  await browser.close();
}
const order = Object.keys(BPS).filter((bp) => navs[bp]);
if (order.length) {
  const uniq = (xs) => [...new Set(xs.filter((x) => x))];
  const first = navs[order[0]];
  meta.navigation = { final_url: first.finals[first.finals.length - 1],
                      final_urls: uniq(order.flatMap((bp) => navs[bp].finals)),
                      hops: uniq(order.flatMap((bp) => navs[bp].hops)),
                      server_ip: first.server_ip, server_ips: uniq(order.map((bp) => navs[bp].server_ip)),
                      blocked: [...blocked] };
  meta.page = first.page;
  meta.pages = order.map((bp) => navs[bp].page);
}
fs.writeFileSync(path.join(outDir, STATE ? `meta-${STATE}.json` : "meta.json"), JSON.stringify(meta, null, 2));
if (ASSETS) fs.writeFileSync(path.join(outDir, "assets.json"), JSON.stringify({ assets: [...assets.values()] }, null, 1));
