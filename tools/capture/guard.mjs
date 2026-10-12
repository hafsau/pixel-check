// URL guards shared by capture.mjs and check_page.mjs (live mode from a URL, check mode): public http(s) only —
// every resolved address must be public (no localhost / private / link-local / reserved), redirects followed by
// hand and each hop checked, sub-requests blocked by the page route; sensitive-page scan (sign-in, payment, wallet).
import dns from "node:dns/promises";
import net from "node:net";

/** IPv6 text → 16 bytes (embedded dotted IPv4 and zone ids handled), or null when it does not parse. */
function v6bytes(s) {
  let x = String(s).toLowerCase().replace(/^\[|\]$/g, "").split("%")[0];
  const m = x.match(/^(.*:)(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (m) {
    const p = m.slice(2).map(Number);
    if (p.some((v) => v > 255)) return null;
    x = m[1] + ((p[0] << 8) | p[1]).toString(16) + ":" + ((p[2] << 8) | p[3]).toString(16);
  }
  const dbl = x.split("::");
  if (dbl.length > 2) return null;
  const hs = dbl[0] ? dbl[0].split(":") : [];
  const rs = dbl.length === 2 && dbl[1] ? dbl[1].split(":") : [];
  const fill = dbl.length === 2 ? 8 - hs.length - rs.length : 0;
  if (fill < 0) return null;
  const groups = [...hs, ...Array(fill).fill("0"), ...rs];
  if (groups.length !== 8 || groups.some((g) => !/^[0-9a-f]{1,4}$/.test(g))) return null;
  return groups.flatMap((g) => { const v = parseInt(g, 16); return [v >> 8, v & 255]; });
}

export function privateIp(ip) {
  const v = net.isIP(String(ip).replace(/^\[|\]$/g, "").split("%")[0]);
  if (v === 4) {
    const [a, b] = ip.split(".").map(Number);
    return a === 0 || a === 10 || a === 127 || a >= 224 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127) || (a === 192 && b === 0) || (a === 198 && (b === 18 || b === 19));
  }
  if (v === 6) {
    const b = v6bytes(ip);
    if (!b) return true;
    const zero = (from, to) => b.slice(from, to).every((x) => x === 0);
    const v4 = (i) => privateIp(b.slice(i, i + 4).join("."));
    if (zero(0, 15) && b[15] <= 1) return true;                                   // :: and ::1
    if (b[0] === 0xfe && (b[1] & 0xc0) === 0x80) return true;                     // fe80::/10 link-local
    if (b[0] === 0xfe && (b[1] & 0xc0) === 0xc0) return true;                     // fec0::/10 site-local
    if ((b[0] & 0xfe) === 0xfc) return true;                                      // fc00::/7 unique local
    if (b[0] === 0xff) return true;                                               // multicast
    if (b[0] === 0x01 && zero(1, 8)) return true;                                 // 100::/64 discard
    if (b[0] === 0x20 && b[1] === 0x01 && zero(2, 4)) return true;                // 2001::/32 Teredo (hides an IPv4)
    if (b[0] === 0x20 && b[1] === 0x01 && b[2] === 0x0d && b[3] === 0xb8) return true;   // 2001:db8::/32 documentation
    if (zero(0, 10) && b[10] === 0xff && b[11] === 0xff) return v4(12);           // ::ffff:a.b.c.d (mapped)
    if (zero(0, 12)) return v4(12);                                               // ::a.b.c.d (compatible)
    if (b[0] === 0 && b[1] === 0x64 && b[2] === 0xff && b[3] === 0x9b && zero(4, 12)) return v4(12);   // 64:ff9b::/96 NAT64
    if (b[0] === 0x20 && b[1] === 0x02) return v4(2);                             // 2002::/16 6to4
    return false;
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
  /** Block every non-public sub-request of a browser context, WebSockets included (recorded in `blocked`). */
  async function route(ctx) {
    await ctx.route("**/*", async (r) => {
      const u = r.request().url();
      if (await allowed(u)) return r.continue();
      blocked.add(u);
      return r.abort("blockedbyclient");
    });
    await ctx.routeWebSocket(/.*/, async (ws) => {
      const u = ws.url();
      if (await allowed(u.replace(/^ws/, "http"))) return ws.connectToServer();
      blocked.add(u);
      return ws.close();
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

