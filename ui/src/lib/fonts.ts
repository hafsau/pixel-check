// The font catalogue (mirror of sandbox/fonts/catalog.json — a test keeps them equal): 16 open-licence families, all
// on Google Fonts. The in-app preview and the downloaded project load the ones the code names (font-['Family_Name']).

export interface FontEntry {
  slug: string;
  weights: number[];
  mono: boolean;
}

export const FONT_CATALOG: Record<string, FontEntry> = {
  "Lato": {
    "slug": "lato",
    "weights": [
      300,
      400,
      700,
      900
    ],
    "mono": false
  },
  "Roboto": {
    "slug": "roboto",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "Open Sans": {
    "slug": "open-sans",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800
    ],
    "mono": false
  },
  "Poppins": {
    "slug": "poppins",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "Montserrat": {
    "slug": "montserrat",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "DM Sans": {
    "slug": "dm-sans",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "Source Sans 3": {
    "slug": "source-sans-3",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "Space Grotesk": {
    "slug": "space-grotesk",
    "weights": [
      300,
      400,
      500,
      600,
      700
    ],
    "mono": false
  },
  "Manrope": {
    "slug": "manrope",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800
    ],
    "mono": false
  },
  "Nunito Sans": {
    "slug": "nunito-sans",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "Work Sans": {
    "slug": "work-sans",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800,
      900
    ],
    "mono": false
  },
  "Plus Jakarta Sans": {
    "slug": "plus-jakarta-sans",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800
    ],
    "mono": false
  },
  "IBM Plex Sans": {
    "slug": "ibm-plex-sans",
    "weights": [
      300,
      400,
      500,
      600,
      700
    ],
    "mono": false
  },
  "IBM Plex Mono": {
    "slug": "ibm-plex-mono",
    "weights": [
      300,
      400,
      500,
      600,
      700
    ],
    "mono": true
  },
  "JetBrains Mono": {
    "slug": "jetbrains-mono",
    "weights": [
      300,
      400,
      500,
      600,
      700,
      800
    ],
    "mono": true
  },
  "Inter": {
    "slug": "inter",
    "weights": [
      400,
      500,
      600,
      700
    ],
    "mono": false
  }
};

const BASE = ['family=Inter:wght@400;500;600;700', 'family=IBM+Plex+Mono:wght@400;500'];

/** Catalogue families the code names with font-['Family_Name'] (any breakpoint prefix), sorted; Inter / Plex Mono
 *  are always loaded and not listed. */
export function fontFamiliesIn(code: string): string[] {
  const out = new Set<string>();
  for (const m of code.matchAll(/font-\[['"]?([A-Za-z0-9_ ]+?)['"]?\]/g)) {
    const name = m[1].replace(/_/g, ' ');
    if (FONT_CATALOG[name] && name !== 'Inter' && name !== 'IBM Plex Mono') out.add(name);
  }
  return [...out].sort();
}

/** One Google Fonts stylesheet for Inter + IBM Plex Mono and the families the code names, with their weights. */
export function googleFontsUrl(code: string): string {
  const extra = fontFamiliesIn(code).map((f) => `family=${f.replace(/ /g, '+')}:wght@${FONT_CATALOG[f].weights.join(';')}`);
  return `https://fonts.googleapis.com/css2?${[...BASE, ...extra].join('&')}&display=swap`;
}
