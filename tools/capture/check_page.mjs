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
if (!url) { console.error("usage: node check_page.mjs <url> --out DIR"); process.exit(2); }

// motion off and no caret / scrollbars — but the page's own fonts stay (unlike our renders, nothing is normalised)
const STILL_CSS = `*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}
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

const guard = makeGuard(url);
let preHops = null;
if (BLOCK_PRIVATE) {
  try { preHops = await guard.preflight(url); }
  catch (e) { console.error(String(e.message || e)); process.exit(3); }
}
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ args: R.CHROMIUM_ARGS });
const result = { breakpoints: {}, between: {}, runtime_errors: [], mode: "check" };
const meta = { url, sensitive: { password: 0, payment: 0, signin: 0, crypto: 0 }, finals: {}, ips: [], pages: [] };

async function open(w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  if (BLOCK_PRIVATE) await guard.route(ctx);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => result.runtime_errors.length < 20 && result.runtime_errors.push(String(e.message).slice(0, 300)));
  await page.addInitScript(() => { window.__pcRoot = "body"; });
  const resp = await page.goto(url, { waitUntil: "load", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.addStyleTag({ content: STILL_CSS });
  await page.evaluate(() => document.fonts.ready);
  await settle(page, maxWait);
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
    const { dom, health, fontsOk } = await R.captureFrame(page, out, bp);
    result.breakpoints[bp] = { width: w, height: h, elements: dom.length, fonts_ok: fontsOk, ...health };
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
fs.writeFileSync(path.join(out, "checks.json"), JSON.stringify(result, null, 2));
fs.writeFileSync(path.join(out, "meta.json"), JSON.stringify({
  url, sensitive: meta.sensitive, page: meta.pages[0] || {}, pages: meta.pages,
  navigation: { final_url: finals[0] || url, final_urls: finals, hops: preHops || [url], server_ip: meta.ips[0] || null,
                server_ips: uniq(meta.ips), blocked: [...guard.blocked] },
}, null, 2));
console.log(`check ${url} ok`);
