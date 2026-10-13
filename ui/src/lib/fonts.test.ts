// The web app's preview and the downloaded project load the fonts the code names (Oct 12: a catalogue of 16 open
// families — all on Google Fonts — instead of Inter only). Written before the code (TDD).
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { FONT_CATALOG, fontFamiliesIn, googleFontsUrl } from './fonts';

describe('fonts', () => {
  it('mirrors the renderer catalogue exactly', () => {
    const sandbox = JSON.parse(readFileSync(new URL('../../../sandbox/fonts/catalog.json', import.meta.url), 'utf8'));
    expect(FONT_CATALOG).toEqual(sandbox);
  });

  it('finds the families the code names', () => {
    const code = `<main className="font-['Lato'] p-4"><p className="md:font-['JetBrains_Mono'] font-['Nope']">x</p></main>`;
    expect(fontFamiliesIn(code)).toEqual(['JetBrains Mono', 'Lato']);
  });

  it('builds one Google Fonts link with the right weights, Inter and Plex always included', () => {
    const url = googleFontsUrl(`<main className="font-['Lato']"><p className="font-['Space_Grotesk']">x</p></main>`);
    expect(url).toContain('family=Inter:wght@400;500;600;700');
    expect(url).toContain('family=IBM+Plex+Mono:wght@');
    expect(url).toContain('family=Lato:wght@300;400;700;900');
    expect(url).toContain('family=Space+Grotesk:wght@300;400;500;600;700');
    expect(url.endsWith('&display=swap')).toBe(true);
    expect(googleFontsUrl('<main className="p-4">x</main>')).toBe(
      'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap',
    );
  });
});
