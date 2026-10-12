// Check mode (Phase 3): measure ANY deployed page the way the scorer measures our own renders — as it really looks
// (its own fonts and images; animations stopped), behind the same URL guards as live mode.
//
//   node check_page.mjs <url> --out DIR [--wait ms] [--block-private]
//
// DIR: {mobile,tablet,desktop}.{png,dom.json,notext.png,coded.png,nodes.json} (render.mjs captureFrame), checks.json
// (design sizes + layout health at 360/375/500/1024/1600), meta.json (navigation, page identity, sensitive fields).
// In the sandbox it runs from /opt/pc next to render.mjs; locally PC_RENDER points at sandbox/render.mjs.
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { makeGuard, sensitiveScan } from "./guard.mjs";

const R = await import(process.env.PC_RENDER || new URL("./render.mjs", import.meta.url).href);
const arg = (n, d) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : d; };
const url = process.argv[2];
const out = arg("--out", "/work/out");
const maxWait = Number(arg("--wait", "2000"));
const BLOCK_PRIVATE = process.argv.includes("--block-private");
if (arg("--sizes")) R.setSizes(JSON.parse(fs.readFileSync(arg("--sizes"), "utf8")));     // a run's own frame sizes
if (!url) { console.error("usage: node check_page.mjs <url> --out DIR"); process.exit(2); }

// motion to its end state and no caret / scrollbars — the page's own fonts stay (nothing is normalised)
const STILL_CSS = `*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;animation-iteration-count:1!important;transition:none!important;caret-color:transparent!important}
html{scrollbar-width:none}::-webkit-scrollbar{display:none}`;

async function settle(page, max) {        // no DOM change / new resource for 500 ms, at most `max`
  await page.evaluate(async ([quiet, m]) => {
    let last = performance.now();
    const bump = () => { last = performance.now(); };
    const mo = new MutationObserver(bump);
    mo.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
    const t0 = performance.now();
    while (performance.now() - t0 < m && performance.now() - last < quiet) await new Promise((r) => setTimeout(r, 50));
    mo.disconnect();
  }, [Math.min(500, max), max]);
}

// warnings, not verdicts (council, Oct 8): signs that a build imitates the frames instead of laying them out
function warningsScan([name, widths]) {
  const vw = innerWidth, vh = innerHeight, out = [];
  let cover = 0;
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    const pic = /^(IMG|PICTURE|CANVAS|VIDEO|OBJECT|EMBED|IFRAME)$/.test(el.tagName) || /url\(/.test(cs.backgroundImage);
    if (!pic || cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    const a = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
    cover = Math.max(cover, a / (vw * vh));
  }
  if (cover > 0.3) out.push(`${name}: a picture covers ${Math.round(cover * 100)} % of the screen — the build may be a screenshot`);
  // a width window ≤ 2 px wide at a measured width — also built from nested @media rules (red team, Oct 12)
  const walk = (rules, mn, mx) => {
    for (const rule of rules || []) {
      let lo = mn, hi = mx;
      const q = rule.conditionText || (rule.media && rule.media.mediaText) || "";
      if (q) {
        const ex = q.match(/\(\s*width\s*:\s*(\d+)px\s*\)/);
        const a = q.match(/min-width\s*:\s*(\d+)px/), b = q.match(/max-width\s*:\s*(\d+)px/);
        if (ex) { lo = Math.max(lo, Number(ex[1])); hi = Math.min(hi, Number(ex[1])); }
        if (a) lo = Math.max(lo, Number(a[1]));
        if (b) hi = Math.min(hi, Number(b[1]));
        if (hi - lo <= 2 && widths.some((w) => w >= lo - 2 && w <= hi + 2))
          out.push(`a media query targets exactly ${lo} px — layouts tuned to the measured widths`);
      }
      let inner = null;
      try { inner = rule.cssRules; } catch (e) { inner = null; }
      if (inner) walk(inner, lo, hi);
    }
  };
  for (const sh of document.styleSheets) {
    let rules;
    try { rules = sh.cssRules; } catch (e) { continue; }       // cross-origin sheets
    walk(rules, 0, Infinity);
  }
  return out;
}

const guard = makeGuard(url);
let preHops = null;
if (BLOCK_PRIVATE) {
  try { preHops = await guard.preflight(url); }
  catch (e) { console.error(String(e.message || e)); process.exit(3); }
}
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ args: R.CHROMIUM_ARGS });
const result = { breakpoints: {}, between: {}, runtime_errors: [], mode: "check" };
const warnings = [];
const meta = { url, sensitive: { password: 0, payment: 0, signin: 0, crypto: 0 }, finals: {}, ips: [], pages: [] };

async function open(w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: "reduce", serviceWorkers: "block" });
  if (BLOCK_PRIVATE) await guard.route(ctx);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => result.runtime_errors.length < 20 && result.runtime_errors.push(String(e.message).slice(0, 300)));
  await page.addInitScript(() => { window.__pcRoot = "body"; });
  const resp = await page.goto(url, { waitUntil: "load", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  // looping motion (marquees) is marked before it is stopped: its clipping is design, not overflow (render.mjs)
  await page.evaluate(() => { for (const a of document.getAnimations()) {
    const t = a.effect && a.effect.target;
    if (t && t.setAttribute && a.effect.getTiming().iterations === Infinity) t.setAttribute("data-pc-motion", "");
  } });
  await page.addStyleTag({ content: STILL_CSS });
  await page.evaluate(() => document.fonts.ready);
  await settle(page, maxWait);
  // fade-ins end visible (an animation frozen at its start state hid an honest page's text — council, Oct 8)
  await page.evaluate(() => { for (const a of document.getAnimations()) { try { a.finish(); } catch (e) { /* infinite */ } } });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.addScriptTag({ content: `window.__inkInfo = ${R.inkInfo.toString()};` });
  const addr = resp ? await resp.serverAddr().catch(() => null) : null;
  if (addr) meta.ips.push(addr.ipAddress);
  return { ctx, page };
}

try {
  await Promise.all(Object.entries(R.BREAKPOINTS).map(async ([bp, [w, h]]) => {
    const { ctx, page } = await open(w, h);
    for (const f of page.frames()) {
      const s = await f.evaluate(sensitiveScan).catch(() => null);
      if (s) for (const k of Object.keys(s)) meta.sensitive[k] = Math.max(meta.sensitive[k], s[k]);
    }
    meta.finals[bp] = page.url();
    meta.pages.push(await page.evaluate(() => ({ title: document.title || "",
      site_name: (document.querySelector('meta[property="og:site_name"]') || {}).content || "" })));
    const measured = [...new Set([360, 375, 390, 500, 768, 1024, 1280, 1600, ...R.BETWEEN_WIDTHS,
      ...Object.values(R.BREAKPOINTS).map(([fw]) => fw)])];
    const warn = await page.evaluate(warningsScan, [bp, measured]);
    const { dom, health, fontsOk, dump } = await R.captureFrame(page, out, bp);
    result.breakpoints[bp] = { width: w, height: h, elements: dom.length, fonts_ok: fontsOk, ...health };
    const texts = (dump || []).filter((e) => e.v && e.t);
    const positioned = texts.length ? texts.filter((e) => e.p).length / texts.length : 0;
    if (positioned > 0.3) warn.push(`${bp}: ${Math.round(positioned * 100)} % of the text is absolutely positioned — pinned, not laid out`);
    warnings.push(...warn);
    await ctx.close();
  }));
  for (const w of R.BETWEEN_WIDTHS) {
    const { ctx, page } = await open(w, w < 768 ? 844 : w < 1280 ? 1024 : 900);
    result.between[w] = { ...(await page.evaluate(R.layoutHealth)), ...(await page.evaluate(R.fluidity)) };
    await ctx.close();
  }
} finally {
  await browser.close();
}
const uniq = (xs) => [...new Set(xs.filter(Boolean))];
const finals = uniq(Object.keys(R.BREAKPOINTS).map((bp) => meta.finals[bp]));
result.warnings = [...new Set(warnings)];
result.sizes = R.BREAKPOINTS;
fs.writeFileSync(path.join(out, "checks.json"), JSON.stringify(result, null, 2));
fs.writeFileSync(path.join(out, "meta.json"), JSON.stringify({
  url, sensitive: meta.sensitive, page: meta.pages[0] || {}, pages: meta.pages,
  navigation: { final_url: finals[0] || url, final_urls: finals, hops: preHops || [url], server_ip: meta.ips[0] || null,
                server_ips: uniq(meta.ips), blocked: [...guard.blocked] },
}, null, 2));
console.log(`check ${url} ok`);
