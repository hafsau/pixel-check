// URL guards shared by capture.mjs and check_page.mjs (live mode from a URL, check mode): public http(s) only —
// every resolved address must be public (no localhost / private / link-local / reserved), redirects followed by
// hand and each hop checked, sub-requests blocked by the page route; sensitive-page scan (sign-in, payment, wallet).
import dns from "node:dns/promises";
import net from "node:net";

export function privateIp(ip) {
  const v = net.isIP(ip);
  if (v === 4) {
    const [a, b] = ip.split(".").map(Number);
    return a === 0 || a === 10 || a === 127 || a >= 224 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127) || (a === 192 && b === 0) || (a === 198 && (b === 18 || b === 19));
  }
  if (v === 6) {
    const x = ip.toLowerCase();
    if (x === "::" || x === "::1" || /^f[cd]/.test(x) || /^fe[89ab]/.test(x) || /^ff/.test(x)) return true;
    const m = x.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
    return m ? privateIp(m[1]) : false;
  }
  return true;
}

/** startUrl: the page asked for (file: fixtures are allowed only when it is one — dev tests). */
export function makeGuard(startUrl) {
  const blocked = new Set();
  async function allowed(u) {
    let x;
    try { x = new URL(u); } catch { return false; }
    if (x.protocol === "data:" || x.protocol === "blob:" || x.protocol === "about:") return true;
    if (x.protocol === "file:") return startUrl.startsWith("file:");          // dev fixtures only
    if (x.protocol !== "http:" && x.protocol !== "https:") return false;
    const host = x.hostname.replace(/^\[|\]$/g, "").toLowerCase();
    if (host === "localhost" || host.endsWith(".localhost")) return false;
    if (net.isIP(host)) return !privateIp(host);
    try {
      const addrs = await dns.lookup(host, { all: true });
      return addrs.every((a) => !privateIp(a.address));
    } catch { return true; }                                             // unresolvable: the request fails anyway
  }
  async function preflight(start) {
    const hops = [start];
    let cur = start;
    for (let i = 0; i < 6; i++) {
      if (!(await allowed(cur))) { blocked.add(cur); throw new Error(`blocked: ${cur} is not a public address`); }
      if (!/^https?:/.test(cur)) return hops;
      let r;
      try { r = await fetch(cur, { method: "GET", redirect: "manual", signal: AbortSignal.timeout(15000) }); }
      catch { return hops; }
      const loc = r.status >= 300 && r.status < 400 && r.headers.get("location");
      if (!loc) return hops;
      cur = new URL(loc, cur).href;
      hops.push(cur);
    }
    throw new Error("blocked: too many redirects");
  }
  /** Block every non-public sub-request of a browser context (recorded in `blocked`). */
  async function route(ctx) {
    await ctx.route("**/*", async (r) => {
      const u = r.request().url();
      if (await allowed(u)) return r.continue();
      blocked.add(u);
      return r.abort("blockedbyclient");
    });
  }
  return { allowed, preflight, route, blocked };
}

export function sensitiveScan() {
  // runs in each frame, before media are replaced: forms in the document and in open shadow roots
  const roots = [document];
  for (let i = 0; i < roots.length; i++)
    for (const el of roots[i].querySelectorAll("*")) if (el.shadowRoot) roots.push(el.shadowRoot);
  const q = (sel) => roots.reduce((n, r) => n + r.querySelectorAll(sel).length, 0);
  // innerText keeps block boundaries ("Sign in" + "Next" must not read as "Sign inNext")
  const text = roots.map((r) => (r.body ? r.body.innerText : r.textContent) || "").join(" ");
  const named = (rx) => roots.reduce((n, r) => n + [...r.querySelectorAll("input, textarea, select")].filter((e) =>
    rx.test(`${e.name || ""} ${e.id || ""} ${e.getAttribute("autocomplete") || ""} ${e.getAttribute("aria-label") || ""}`)).length, 0);
  const password = q('input[type=password], [autocomplete~="current-password"], [autocomplete~="new-password"], ' +
    '[autocomplete~="one-time-code"], input[name*="otp" i]');
  const payment = q('[autocomplete^="cc-"], iframe[src*="stripe" i], iframe[src*="braintree" i], iframe[src*="adyen" i], ' +
    'iframe[name*="card" i]') + named(/\b(card.?number|cardnumber|cvc|cvv|iban|routing|sort.?code|account.?number)\b/i);
  const ident = q('input[type=email], [autocomplete~="username"], [autocomplete~="email"]') + named(/\b(user(name)?|login|identifier)\b/i);
  const signin = ident && /\b(sign|log)\s?in\b|\bcontinue with\b|\bforgot (your )?password\b/i.test(text) ? ident : 0;
  const crypto = /seed phrase|recovery phrase|secret recovery|connect (your )?wallet|private key/i.test(text) ? 1 : 0;
  return { password, payment, signin, crypto };
}

