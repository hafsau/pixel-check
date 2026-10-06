/** @type {import('tailwindcss').Config} */
// All colours, radii and fonts come from CSS variables in src/styles/tokens.css.
const c = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: c('bg'),
        surface: c('surface'),
        'surface-2': c('surface-2'),
        line: c('line'),
        ink: c('ink'),
        'ink-muted': c('ink-muted'),
        'ink-faint': c('ink-faint'),
        accent: c('accent'),
        'accent-ink': c('accent-ink'),
        'accent-strong': c('accent-strong'),
        'accent-2': c('accent-2'),
        good: c('good'),
        ok: c('ok'),
        warn: c('warn'),
        bad: c('bad'),
        'bp-mobile': c('bp-mobile'),
        'bp-tablet': c('bp-tablet'),
        'bp-desktop': c('bp-desktop'),
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
        pixel: 'var(--font-pixel)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        DEFAULT: 'var(--radius-md)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        pill: 'var(--radius-pill)',
      },
      letterSpacing: {
        display: 'var(--tracking-display)',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        lift: 'var(--shadow-lift)',
      },
      maxWidth: {
        content: 'var(--content-max)',
      },
      spacing: {
        gutter: 'var(--space-gutter)',
        section: 'var(--space-section)',
      },
      transitionTimingFunction: {
        DEFAULT: 'var(--ease)',
      },
      transitionDuration: {
        DEFAULT: 'var(--dur)',
      },
    },
  },
  plugins: [],
};
