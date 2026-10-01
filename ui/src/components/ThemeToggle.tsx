import { useTheme } from '../lib/theme';
import { IconMoon, IconSun } from './Icons';

export function ThemeToggle() {
  const [theme, toggle] = useTheme();
  const dark = theme === 'dark';
  return (
    <button type="button" className="btn-icon btn-ghost" onClick={toggle} aria-pressed={dark} aria-label="Dark theme">
      {dark ? <IconSun /> : <IconMoon />}
    </button>
  );
}
