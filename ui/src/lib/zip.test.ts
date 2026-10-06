import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { crc32, zipStore } from './zip';

const enc = new TextEncoder();

function writeTmp(bytes: Uint8Array): string {
  const dir = mkdtempSync(join(tmpdir(), 'pc-zip-'));
  const f = join(dir, 'test.zip');
  writeFileSync(f, bytes);
  return f;
}

describe('crc32', () => {
  it('matches the standard check value', () => {
    expect(crc32(enc.encode('123456789'))).toBe(0xcbf43926);
  });
  it('is 0 for empty input and unsigned', () => {
    expect(crc32(new Uint8Array())).toBe(0);
    expect(crc32(enc.encode('The quick brown fox jumps over the lazy dog'))).toBe(0x414fa339);
  });
});

describe('zipStore (STORE, no compression)', () => {
  const files = [
    { path: 'package.json', data: '{"name":"x"}\n' },
    { path: 'src/App.jsx', data: 'export default function App() {\n  return <p>héllo — ✓</p>;\n}\n' },
    { path: 'README.md', data: enc.encode('# Readme\n') },
  ];
  const zip = zipStore(files, new Date(2026, 9, 5, 14, 30, 10));

  it('starts with a local header and ends with the end-of-central-directory record', () => {
    expect([...zip.slice(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]);
    const eocd = zip.slice(zip.length - 22);
    expect([...eocd.slice(0, 4)]).toEqual([0x50, 0x4b, 0x05, 0x06]);
    expect(eocd[10] | (eocd[11] << 8)).toBe(3); // total entries
  });

  it('round-trips through unzip: names, sizes and bytes (incl. UTF-8)', () => {
    const f = writeTmp(zip);
    const list = execFileSync('unzip', ['-l', f]).toString();
    for (const x of files) expect(list).toContain(x.path);
    for (const x of files) {
      const out = execFileSync('unzip', ['-p', f, x.path]);
      const want = typeof x.data === 'string' ? Buffer.from(x.data, 'utf8') : Buffer.from(x.data);
      expect(out.equals(want)).toBe(true);
    }
    // -t verifies every CRC
    expect(execFileSync('unzip', ['-t', f]).toString()).toMatch(/No errors detected/);
  });

  it('stores the modification date', () => {
    const list = execFileSync('unzip', ['-l', writeTmp(zip)]).toString();
    expect(list).toMatch(/10-05-2026 14:30/);
  });

  it('handles an empty archive', () => {
    const z = zipStore([]);
    expect(z.length).toBe(22);
  });
});
