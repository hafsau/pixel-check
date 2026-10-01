// Pixel-Check renderer. Runs inside the Token Factory Sandbox (network off).
//
//   node render.mjs [--in /work/App.jsx] [--out /work/out] [--emit]   render one App.jsx
//   node render.mjs --selftest                                         build-time check
//
// Outputs in --out:
//   {mobile,tablet,desktop}.png   exact viewport, deviceScaleFactor 1
//   {bp}.dom.json                 visible text elements: text, box, font, colours, classes
//   checks.json                   in-between widths: horizontal overflow + text overlaps
//   build.log                     esbuild / tailwind / runtime errors
// --emit prints one JSON bundle (PNGs base64) to stdout so the orchestrator needs one call.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";
import postcss from "postcss";
import tailwindcss from "tailwindcss";
import { chromium } from "playwright";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const BREAKPOINTS = { mobile: [390, 844], tablet: [768, 1024], desktop: [1280, 800] };
export const BETWEEN_WIDTHS = [600, 1024, 1440];
const NOTEXT_CSS = `*,*::before,*::after{color:transparent!important;-webkit-text-fill-color:transparent!important;
text-shadow:none!important;text-decoration-color:transparent!important;-webkit-background-clip:border-box!important;
background-clip:border-box!important}*::placeholder{color:transparent!important;-webkit-text-fill-color:transparent!important}`;
const CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--font-render-hinting=none"];

const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : dflt;
};

function fontCss() {
  const face = (family, file, weight) => {
    const b64 = fs.readFileSync(path.join(HERE, "fonts", file)).toString("base64");
    return `@font-face{font-family:'${family}';font-style:normal;font-weight:${weight};font-display:block;` +
      `src:url(data:font/woff2;base64,${b64}) format('woff2');}`;
  };
  return [400, 500, 600, 700].map((w) => face("Inter", `inter-latin-${w}-normal.woff2`, w)).join("") +
    [400, 500].map((w) => face("IBM Plex Mono", `ibm-plex-mono-latin-${w}-normal.woff2`, w)).join("");
}

// Determinism: no motion, no caret, no scrollbars, no smoothing differences.
const DETERMINISM_CSS = `*,*::before,*::after{animation:none!important;transition:none!important;
caret-color:transparent!important}html{scrollbar-width:none}::-webkit-scrollbar{display:none}
body{margin:0;font-family:'Inter',sans-serif;-webkit-font-smoothing:antialiased}`;

async function build(appPath, log) {
  const src = fs.readFileSync(appPath, "utf8");
  const entry = `import React from "react";import {createRoot} from "react-dom/client";` +
    `import App from ${JSON.stringify(appPath)};createRoot(document.getElementById("root")).render(React.createElement(App));`;
  const js = await esbuild.build({
    stdin: { contents: entry, loader: "jsx", resolveDir: HERE },
    bundle: true, write: false, format: "iife", minify: true, jsx: "automatic",
    loader: { ".jsx": "jsx", ".js": "jsx" }, nodePaths: [path.join(HERE, "node_modules")],
    define: { "process.env.NODE_ENV": '"production"' }, logLevel: "silent",
  });
  const twConfig = {
    content: [{ raw: src, extension: "jsx" }],
    theme: { extend: { fontFamily: { sans: ["Inter", "sans-serif"], mono: ["IBM Plex Mono", "monospace"] } } },
  };
  const tw = await postcss([tailwindcss(twConfig)])
    .process("@tailwind base;@tailwind components;@tailwind utilities;", { from: undefined });
  for (const w of js.warnings) log.push(`esbuild warning: ${w.text}`);
  return `<!doctype html><html><head><meta charset="utf-8">` +
    `<style>${fontCss()}${tw.css}${DETERMINISM_CSS}</style></head>` +
    `<body><div id="root"></div><script>${js.outputFiles[0].text}</script></body></html>`;
}

// Runs in the page: can a human see this element's own text? (red-team: 1 px / transparent /
// opacity-0.01 / off-screen text used to earn text credit and to dilute the integrity check)
function inkInfo(el, cs, r, vw, vh) {
  let op = 1;
  for (let a = el; a && a.nodeType === 1; a = a.parentElement) op *= Number(getComputedStyle(a).opacity);
  const m = cs.color.match(/rgba?\(([^)]+)\)/);
  const alpha = m && m[1].split(",").length === 4 ? Number(m[1].split(",")[3]) : 1;
  const fs = parseFloat(cs.fontSize);
  const clipped = cs.clip && cs.clip !== "auto" && /rect\(0(px)?,? ?0(px)?/.test(cs.clip);
  const inked = r.width >= 2 && r.height >= 2 && fs >= 6 && alpha * op >= 0.1 && !clipped &&
    cs.visibility !== "hidden" && cs.display !== "none";
  const onscreen = r.right > 0 && r.bottom > 0 && r.left < vw && r.top < vh;
  return { inked, onscreen, font_px: fs, alpha: +(alpha * op).toFixed(3) };
}

// Runs in the page: every visible element that owns a text node.
function extractDom() {
  const out = [];
  const vis = /(^|\s)((sm|md|lg|xl|2xl):)?(hidden|block|flex|grid|inline|inline-block|inline-flex|contents)(?=\s|$)/g;
  const all = [...document.querySelectorAll("#root *")];
  all.forEach((el, idx) => {
    let own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join("").trim();
    // form controls show text that is not a text node (red-team r2 #4: placeholders earned no credit)
    if (!own && ["INPUT", "TEXTAREA"].includes(el.tagName)) own = (el.value || el.placeholder || "").trim();
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (!own || r.width === 0 || r.height === 0 || cs.visibility === "hidden" || Number(cs.opacity) === 0) return;
    const ink = window.__inkInfo(el, cs, r, innerWidth, innerHeight);
    out.push({ idx, pc: el.closest("[data-pc]")?.getAttribute("data-pc") ?? null, inked: ink.inked, onscreen: ink.onscreen, alpha: ink.alpha,
      tag: el.tagName.toLowerCase(), text: own.slice(0, 200),
      box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      font_size: cs.fontSize, font_weight: cs.fontWeight, font_family: cs.fontFamily.split(",")[0].replace(/['"]/g, ""),
      color: cs.color, background: cs.backgroundColor,
      visibility_classes: (el.className?.baseVal ?? el.className ?? "").match(vis)?.map((s) => s.trim()) ?? [],
    });
  });
  return out;
}

// Runs in the page: layout health at widths we don't have designs for.
function layoutHealth() {
  const doc = document.documentElement;
  const overflow_px = Math.max(0, doc.scrollWidth - doc.clientWidth);
  const boxes = [];
  for (const el of document.querySelectorAll("#root *")) {
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const r = el.getBoundingClientRect();
    if (own && r.width > 0 && r.height > 0) boxes.push({ r, el });
  }
  let overlaps = 0;
  const examples = [];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    const ix = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
    const iy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (ix > 2 && iy > 2) {
      overlaps++;
      if (examples.length < 5) examples.push([a.el.textContent.trim().slice(0, 40), b.el.textContent.trim().slice(0, 40)]);
    }
  }
  return { overflow_px, text_overlaps: overlaps, examples };
}

// Runs in the page: every element in document order with its visibility, own text and position.
// The DOM tree is identical at every width (JS width detection is banned by lint.mjs), so the
// index identifies the same node across breakpoints.
function integrityDump() {
  const all = [...document.querySelectorAll("#root *")];
  const index = new Map(all.map((el, i) => [el, i]));
  return all.map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const ink = window.__inkInfo(el, cs, r, innerWidth, innerHeight);
    const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join("").replace(/\s+/g, " ").trim().toLowerCase();
    const visible = r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && Number(cs.opacity) > 0;
    return { v: visible, t: own, i: ink.inked, p: cs.position === "absolute" || cs.position === "fixed",
      b: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      par: index.has(el.parentElement) ? index.get(el.parentElement) : -1,
      ga: cs.gridRowStart !== "auto" && cs.gridColumnStart !== "auto" ? `${cs.gridRowStart}/${cs.gridColumnStart}` : "",
      inl: cs.display === "inline", pc: el.getAttribute("data-pc"),
      mt: Math.round(parseFloat(cs.marginTop) || 0), fs: Math.round(parseFloat(cs.fontSize) || 0),
      pl: Math.round(parseFloat(cs.paddingLeft) || 0), pr: Math.round(parseFloat(cs.paddingRight) || 0) };
  });
}

// Fake responsive = the same text living in separate nodes that are never visible together
// (one layout per breakpoint, toggled with hidden/md:block). Positioned = absolute/fixed share.
export function integrity(dumps) {
  const bps = Object.keys(dumps);
  const n = Math.min(...bps.map((b) => dumps[b].length));
  const sameTree = bps.every((b) => dumps[b].length === n);
  const positioned_ratio = {};
  for (const b of bps) {
    const vis = dumps[b].filter((e) => e.v);
    positioned_ratio[b] = vis.length ? +(vis.filter((e) => e.p).length / vis.length).toFixed(3) : 0;
  }
  const byText = new Map();
  const invisible = new Set();
  for (let i = 0; i < n; i++) {
    const t = dumps[bps[0]][i].t;
    if (!t) continue;
    // laid out (has a box) somewhere but never readable = hidden text (sr-only, transparent, 1 px…)
    if (bps.some((b) => dumps[b][i].v) && !bps.some((b) => dumps[b][i].v && dumps[b][i].i)) invisible.add(t);
    const vset = bps.filter((b) => dumps[b][i].v && dumps[b][i].i);
    if (!vset.length) continue;
    if (!byText.has(t)) byText.set(t, []);
    byText.get(t).push(vset);
  }
  const dup = [];
  for (const [t, sets] of byText) {
    let disjoint = false;
    for (let a = 0; a < sets.length && !disjoint; a++)
      for (let c = a + 1; c < sets.length && !disjoint; c++)
        disjoint = !sets[a].some((x) => sets[c].includes(x));
    if (disjoint) dup.push(t);
  }
  return {
    same_tree: sameTree, positioned_ratio,
    duplicated_layout_ratio: byText.size ? +(dup.length / byText.size).toFixed(3) : 0,
    duplicated_count: dup.filter((t) => t.length >= 4).length,
    duplicated_examples: dup.slice(0, 8), distinct_texts: byText.size,
    invisible_text_count: invisible.size, invisible_examples: [...invisible].slice(0, 8),
  };
}

async function renderHtml(html, outDir) {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ args: CHROMIUM_ARGS });
  const result = { breakpoints: {}, between: {}, runtime_errors: [] };
  const dumps = {};
  try {
    const open = async (w, h) => {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: "reduce" });
      const page = await ctx.newPage();
      page.on("pageerror", (e) => result.runtime_errors.push(String(e.message).slice(0, 500)));
      await page.setContent(html, { waitUntil: "load" });
      await page.addScriptTag({ content: `window.__inkInfo = ${inkInfo.toString()};` });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      });
      return { ctx, page };
    };
    for (const [bp, [w, h]] of Object.entries(BREAKPOINTS)) {
      const { ctx, page } = await open(w, h);
      await page.screenshot({ path: path.join(outDir, `${bp}.png`), fullPage: false });
      const dom = await page.evaluate(extractDom);
      fs.writeFileSync(path.join(outDir, `${bp}.dom.json`), JSON.stringify(dom));
      const health = await page.evaluate(layoutHealth);
      const fontsOk = await page.evaluate(() => document.fonts.check("16px Inter"));
      dumps[bp] = await page.evaluate(integrityDump);
      fs.writeFileSync(path.join(outDir, `${bp}.nodes.json`), JSON.stringify(dumps[bp]));
      // Same page with every glyph transparent: text is readable only where these pixels differ from the
      // real screenshot (catches occlusion, clip-path, filters, zero-height, same-colour text, blend modes).
      await page.addStyleTag({ content: NOTEXT_CSS });
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      await page.screenshot({ path: path.join(outDir, `${bp}.notext.png`), fullPage: false });
      // Third pass: each text element painted its own colour, so every visible glyph pixel can be
      // attributed to exactly one element (text hidden under a labelled button can't borrow its pixels).
      const codes = await page.evaluate((idxs) => {
        const all = [...document.querySelectorAll("#root *")];
        const rules = [], out = {};
        idxs.forEach((i, k) => {
          // golden-angle hues, full saturation, alternating lightness → distinct, far from grey backgrounds
          const hh = ((k * 137.508) % 360) / 60, l = k % 2 ? 0.42 : 0.58, ch = (1 - Math.abs(2 * l - 1));
          const xx = ch * (1 - Math.abs((hh % 2) - 1)), m = l - ch / 2;
          const [r1, g1, b1] = hh < 1 ? [ch, xx, 0] : hh < 2 ? [xx, ch, 0] : hh < 3 ? [0, ch, xx] : hh < 4 ? [0, xx, ch] : hh < 5 ? [xx, 0, ch] : [ch, 0, xx];
          const c = `rgb(${Math.round((r1 + m) * 255)}, ${Math.round((g1 + m) * 255)}, ${Math.round((b1 + m) * 255)})`;
          all[i].setAttribute("data-pcc", String(i));
          rules.push(`[data-pcc="${i}"],[data-pcc="${i}"]::placeholder{color:${c}!important;-webkit-text-fill-color:${c}!important}`);
          out[i] = c;
        });
        const st = document.createElement("style"); st.textContent = rules.join("\n"); document.head.appendChild(st);
        return out;
      }, dom.map((e) => e.idx));
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      await page.screenshot({ path: path.join(outDir, `${bp}.coded.png`), fullPage: false });
      for (const e of dom) e.code = codes[e.idx];
      fs.writeFileSync(path.join(outDir, `${bp}.dom.json`), JSON.stringify(dom));
      result.breakpoints[bp] = { width: w, height: h, elements: dom.length, fonts_ok: fontsOk, ...health };
      await ctx.close();
    }
    for (const w of BETWEEN_WIDTHS) {
      const { ctx, page } = await open(w, 900);
      result.between[w] = await page.evaluate(layoutHealth);
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
  result.integrity = integrity(dumps);
  fs.writeFileSync(path.join(outDir, "checks.json"), JSON.stringify(result, null, 2));
  return result;
}

export async function render(appPath, outDir) {
  const log = [];
  let html;
  try {
    html = await build(appPath, log);
  } catch (e) {
    const msg = e.errors ? e.errors.map((x) => `${x.location?.line ?? "?"}:${x.location?.column ?? "?"} ${x.text}`).join("\n") : String(e);
    log.push(`BUILD FAILED\n${msg}`);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "build.log"), log.join("\n"));
    return { ok: false, build_log: log.join("\n") };
  }
  const result = await renderHtml(html, outDir);
  for (const e of result.runtime_errors) log.push(`runtime error: ${e}`);
  fs.writeFileSync(path.join(outDir, "build.log"), log.join("\n"));
  return { ok: result.runtime_errors.length === 0, build_log: log.join("\n"), ...result };
}

function emit(outDir, result) {
  const pngs = {}, dom = {};
  for (const bp of Object.keys(BREAKPOINTS)) {
    const p = path.join(outDir, `${bp}.png`);
    if (fs.existsSync(p)) {
      pngs[bp] = fs.readFileSync(p).toString("base64");
      dom[bp] = JSON.parse(fs.readFileSync(path.join(outDir, `${bp}.dom.json`), "utf8"));
    }
  }
  process.stdout.write(JSON.stringify({ result, pngs, dom }));
}

async function selftest() {
  const out = "/tmp/pc-selftest";
  const r = await render(path.join(HERE, "selftest", "App.jsx"), out);
  const fail = (m) => { console.error(`SELFTEST FAIL: ${m}`); process.exit(1); };
  if (!r.ok) fail(`render not ok: ${r.build_log}`);
  const { createHash } = await import("node:crypto");
  const hashes = {};
  for (const [bp, [w, h]] of Object.entries(BREAKPOINTS)) {
    const buf = fs.readFileSync(path.join(out, `${bp}.png`));
    const pw = buf.readUInt32BE(16), ph = buf.readUInt32BE(20);
    if (pw !== w || ph !== h) fail(`${bp} is ${pw}x${ph}, want ${w}x${h}`);
    if (!r.breakpoints[bp].fonts_ok) fail(`${bp}: Inter not loaded`);
    hashes[bp] = createHash("sha256").update(buf).digest("hex");
  }
  // Determinism: second render must be byte-identical.
  await render(path.join(HERE, "selftest", "App.jsx"), out + "-2");
  for (const bp of Object.keys(BREAKPOINTS)) {
    const h2 = createHash("sha256").update(fs.readFileSync(path.join(out + "-2", `${bp}.png`))).digest("hex");
    if (h2 !== hashes[bp]) fail(`${bp}: non-deterministic render`);
  }
  // Build errors must be reported, not thrown.
  fs.writeFileSync("/tmp/pc-broken.jsx", "export default function App(){ return <div>unclosed }");
  const bad = await render("/tmp/pc-broken.jsx", "/tmp/pc-broken");
  if (bad.ok || !bad.build_log.includes("BUILD FAILED")) fail("broken JSX not reported");
  console.log("SELFTEST OK", JSON.stringify(hashes));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv.includes("--selftest")) {
    await selftest();
  } else {
    const outDir = arg("--out", "/work/out");
    const result = await render(arg("--in", "/work/App.jsx"), outDir);
    if (process.argv.includes("--emit")) emit(outDir, result);
    else console.log(JSON.stringify(result, null, 2));
    process.exit(result.ok ? 0 : 2);
  }
}
