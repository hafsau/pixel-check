import { describe, expect, it } from 'vitest';
import { entryHref, normalizeIndex, splitIndex, pageLabel, splitTitle } from './bundle';

describe('normalizeIndex', () => {
  it('treats entries without a type as static runs (Oct 1 exporter)', () => {
    const [e] = normalizeIndex([{ id: 'netflix-signin_scaf2-120344', title: 'Sign-in', match: 80.45, per_bp: { mobile: 80.45 }, created: 1 }]);
    expect(e.type).toBe('static');
  });

  it('drops entries without an id or with an unknown type, and non-objects', () => {
    const out = normalizeIndex([null, 3, { title: 'x' }, { id: 'a', type: 'video', created: 1 }, { id: 'b', type: 'group', title: 'g', created: 2 }]);
    expect(out.map((e) => e.id)).toEqual(['b']);
  });

  it('sorts newest first', () => {
    const out = normalizeIndex([
      { id: 'old', type: 'static', created: 1, match: 1, per_bp: {}, title: '' },
      { id: 'new', type: 'interaction', created: 5, title: '', variants: [] },
    ]);
    expect(out.map((e) => e.id)).toEqual(['new', 'old']);
  });

  it('fills safe defaults for missing arrays / maps', () => {
    const [ix] = normalizeIndex([{ id: 'ix', type: 'interaction', created: 1, title: 't' }]);
    expect(ix.type === 'interaction' && ix.variants).toEqual([]);
    expect(ix.type === 'interaction' && ix.bps).toEqual([]);
    const [st] = normalizeIndex([{ id: 's', created: 1, title: 't' }]);
    expect(st.type === 'static' && st.per_bp).toEqual({});
  });

  it('returns [] for a non-array index', () => {
    expect(normalizeIndex({ runs: [] } as unknown)).toEqual([]);
  });
});

describe('splitIndex', () => {
  it('groups entries by bundle type, keeping order', () => {
    const s = splitIndex(
      normalizeIndex([
        { id: 'a', type: 'static', created: 3, title: '', match: 1, per_bp: {} },
        { id: 'b', type: 'interaction', created: 2, title: '' },
        { id: 'c', type: 'static', created: 1, title: '', match: 1, per_bp: {} },
        { id: 'd', type: 'group', created: 0, title: '' },
      ]),
    );
    expect(s.static.map((e) => e.id)).toEqual(['a', 'c']);
    expect(s.interaction.map((e) => e.id)).toEqual(['b']);
    expect(s.group.map((e) => e.id)).toEqual(['d']);
  });
});

describe('entryHref', () => {
  it('routes each bundle type to its view and encodes the id', () => {
    expect(entryHref({ type: 'static', id: 'a b' })).toBe('/run/a%20b');
    expect(entryHref({ type: 'interaction', id: 'ix-lambda-menu' })).toBe('/interaction/ix-lambda-menu');
    expect(entryHref({ type: 'group', id: 'grp-x' })).toBe('/group/grp-x');
  });
});

describe('pageLabel', () => {
  it('turns a page slug into a readable label', () => {
    expect(pageLabel('netflix-signin')).toBe('netflix-signin');
    expect(pageLabel(undefined)).toBe('');
  });
});

describe('splitTitle', () => {
  it('moves a trailing "(dev capture)" note out of the title', () => {
    expect(splitTitle('Sign-up page (dev capture)')).toEqual({ title: 'Sign-up page', note: 'dev capture' });
  });
  it('leaves titles without a note alone', () => {
    expect(splitTitle('Pricing')).toEqual({ title: 'Pricing', note: null });
  });
  it('only treats the final parenthetical as a note', () => {
    expect(splitTitle('A (b) c')).toEqual({ title: 'A (b) c', note: null });
  });
});
