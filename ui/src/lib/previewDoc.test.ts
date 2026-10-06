import { describe, expect, it } from 'vitest';
import { buildPreviewDoc, rewriteAssetSrcs } from './previewDoc';

const H = 'b'.repeat(64);
const url = (rel: string) => `http://localhost:5173/runs/r1/${rel}`;

describe('rewriteAssetSrcs', () => {
  it('rewrites exact src="/assets/<64hex>.<ext>" to the bundle asset URL', () => {
    const code = `<img data-pc="3" src="/assets/${H}.png" alt="Team photo" className="w-full block object-cover" />`;
    expect(rewriteAssetSrcs(code, url)).toBe(`<img data-pc="3" src="http://localhost:5173/runs/r1/assets/${H}.png" alt="Team photo" className="w-full block object-cover" />`);
  });
  it('handles single quotes and every allowed extension, many per file', () => {
    const code = ['png', 'jpg', 'gif', 'webp', 'avif', 'svg'].map((e) => `<img src='/assets/${H}.${e}' />`).join('\n');
    const out = rewriteAssetSrcs(code, url);
    for (const e of ['png', 'jpg', 'gif', 'webp', 'avif', 'svg']) expect(out).toContain(`src='http://localhost:5173/runs/r1/assets/${H}.${e}'`);
    expect(out).not.toContain(`'/assets/`);
  });
  it('leaves every other string untouched', () => {
    const untouched = [
      `<p>See /assets/${H}.png for details</p>`, // not a src attribute
      `const s = "/assets/${H}.png";`, // plain string
      `<img src="/assets/${H.slice(2)}.png" />`, // short hash
      `<img src="/assets/${H}.jpeg" />`, // other extension
      `<img src="/assets/${H}.png?x=1" />`, // query
      `<img src="/assets/${H}.png#a" />`,
      `<img src="https://cdn.test/assets/${H}.png" />`, // absolute
      `<img src="/static/assets/${H}.png" />`,
      `<img src="./assets/${H}.png" />`,
      `<img src="/assets/${H.toUpperCase()}.png" />`,
      `<img src="/assets/${H}.png' />`, // mismatched quotes
      `<img data-src="/assets/${H}.png" />`, // other attribute ending in src
      `<div data-pc="1" aria-hidden="true" className="w-full bg-[#d4d4d8]" />`,
    ].join('\n');
    expect(rewriteAssetSrcs(untouched, url)).toBe(untouched);
  });
  it('does not rewrite to a URL that would break out of the attribute', () => {
    const code = `<img src="/assets/${H}.png" />`;
    expect(rewriteAssetSrcs(code, () => 'x" onload="alert(1)')).toBe(code);
    expect(rewriteAssetSrcs(code, () => '')).toBe(code);
  });
});

describe('buildPreviewDoc', () => {
  const code = `export default function App() {\n  return <img src="/assets/${H}.png" alt="" />;\n}\n`;
  it('without assetUrl the document is unchanged (runs without owned images)', () => {
    expect(buildPreviewDoc(code)).toBe(buildPreviewDoc(code, {}));
    expect(buildPreviewDoc(code)).toContain(`/assets/${H}.png`);
    expect(buildPreviewDoc(code)).not.toContain('localhost:5173');
  });
  it('with assetUrl the embedded source points at the bundle assets', () => {
    const doc = buildPreviewDoc(code, { assetUrl: url });
    expect(doc).toContain(`http://localhost:5173/runs/r1/assets/${H}.png`);
    expect(doc).not.toContain(`\\"/assets/${H}.png`);
  });
});
