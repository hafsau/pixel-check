// Builds the iframe document that renders a generated App.jsx in the browser.
// React 18 UMD + Babel standalone from cdnjs, Tailwind Play CDN, Inter from Google Fonts.

export const PREVIEW_CDN = {
  react: 'https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js',
  reactDom: 'https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js',
  babel: 'https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.26.4/babel.min.js',
  tailwind: 'https://cdn.tailwindcss.com',
  fonts: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap',
};

/** Turn an ES module component (`export default function App()`) into a plain script + its component name. */
export function toRunnable(src: string): { code: string; component: string } {
  // `import React, { useState as uS } from 'react'` → `const { useState: uS } = React;` — other imports are dropped.
  let code = src
    .replace(/^\s*import\s+([^;]*?)\s+from\s*['"]([^'"]+)['"];?\s*$/gm, (_m, what: string, from: string) => {
      const named = what.match(/\{([^}]*)\}/);
      if (from !== 'react' || !named) return '';
      const parts = named[1]
        .split(',')
        .map((p) => p.trim())
        .filter(Boolean)
        .map((p) => p.replace(/\s+as\s+/, ': '));
      return `const { ${parts.join(', ')} } = React;`;
    })
    .replace(/^\s*import\s*['"][^'"]+['"];?\s*$/gm, '');
  let component = 'App';
  const fn = code.match(/export\s+default\s+function\s*([A-Za-z_$][\w$]*)?\s*\(/);
  if (fn) {
    component = fn[1] || 'App';
    code = code.replace(/export\s+default\s+function\s*([A-Za-z_$][\w$]*)?\s*\(/, `function ${component}(`);
  } else {
    const id = code.match(/export\s+default\s+([A-Za-z_$][\w$]*)\s*;?/);
    if (id) {
      component = id[1];
      code = code.replace(id[0], '');
    }
  }
  code = code.replace(/^\s*export\s+(?=(const|let|var|function|class)\b)/gm, '');
  return { code, component };
}

/** JSON that is safe to embed inside a <script> element. */
function scriptSafeJson(v: unknown): string {
  return JSON.stringify(v)
    .replace(/</g, '\\u003c')
    .replace(new RegExp(String.fromCharCode(0x2028), 'g'), '\\u2028')
    .replace(new RegExp(String.fromCharCode(0x2029), 'g'), '\\u2029');
}

/** `src="/assets/<64 hex>.<ext>"` exactly (either quote) — the owned-site images in a delivered App.jsx. */
const ASSET_SRC = /(?<![\w-])src=(["'])\/(assets\/[0-9a-f]{64}\.(?:png|jpg|gif|webp|avif|svg))\1/g;

/** Point the delivered code's `/assets/…` images at the bundle's files (replay folder or live API). Nothing else changes. */
export function rewriteAssetSrcs(code: string, assetUrl: (rel: string) => string): string {
  return code.replace(ASSET_SRC, (m, q: string, rel: string) => {
    const url = assetUrl(rel);
    return url && !/["'<>\s\\]/.test(url) ? `src=${q}${url}${q}` : m;
  });
}

export function buildPreviewDoc(source: string, opts: { assetUrl?: (rel: string) => string } = {}): string {
  const { code, component } = toRunnable(opts.assetUrl ? rewriteAssetSrcs(source, opts.assetUrl) : source);
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="${PREVIEW_CDN.fonts}" />
<script src="${PREVIEW_CDN.tailwind}"></script>
<script>tailwind.config = { theme: { extend: { fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'] } } } };</script>
<script src="${PREVIEW_CDN.react}"></script>
<script src="${PREVIEW_CDN.reactDom}"></script>
<script src="${PREVIEW_CDN.babel}"></script>
<style>html,body{margin:0;font-family:Inter,ui-sans-serif,system-ui,sans-serif}#pc-error{font:12px/1.5 'IBM Plex Mono',monospace;color:#b42318;background:#fff4f2;padding:12px;white-space:pre-wrap;margin:0}</style>
</head>
<body>
<div id="root"></div>
<script id="pc-src" type="application/json">${scriptSafeJson(code)}</script>
<script>
(function () {
  function fail(msg) {
    var pre = document.getElementById('pc-error') || document.createElement('pre');
    pre.id = 'pc-error';
    pre.textContent = 'Preview error: ' + msg;
    document.body.prepend(pre);
  }
  window.addEventListener('error', function (e) { fail(e.message); });
  try {
    var src = JSON.parse(document.getElementById('pc-src').textContent);
    var out = Babel.transform(src + '\\nwindow.__PC_APP__ = ${component};', { presets: ['react'] }).code;
    var React = window.React; // eslint-disable-line no-unused-vars
    (new Function('React', out))(window.React);
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(window.__PC_APP__));
  } catch (err) { fail(err && err.message ? err.message : String(err)); }
})();
</script>
</body>
</html>`;
}
