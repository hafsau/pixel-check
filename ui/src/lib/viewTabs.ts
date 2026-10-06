// The run page's top-level view: Replay · Preview · Code, mirrored in the URL hash (#preview / #code).
export type RunTab = 'replay' | 'preview' | 'code';

export const RUN_TABS: { key: RunTab; label: string }[] = [
  { key: 'replay', label: 'Replay' },
  { key: 'preview', label: 'Preview' },
  { key: 'code', label: 'Code' },
];

export function tabFromHash(hash: string): RunTab {
  const h = hash.replace(/^#/, '').toLowerCase();
  return h === 'preview' || h === 'code' ? h : 'replay';
}

export function hashForTab(tab: RunTab): string {
  return tab === 'replay' ? '' : `#${tab}`;
}
