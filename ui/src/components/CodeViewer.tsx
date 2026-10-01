import { useState } from 'react';
import { IconCheck, IconCopy, IconDownload } from './Icons';

/** Read-only code view with line numbers, copy and download. */
export function CodeViewer({ code, filename = 'App.jsx' }: { code: string; filename?: string }) {
  const [copied, setCopied] = useState(false);
  const lines = code.replace(/\n$/, '').split('\n');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([code], { type: 'text/javascript' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="overflow-hidden rounded-md border border-line">
      <div className="flex items-center justify-between gap-2 border-b border-line bg-surface-2 px-3 py-1.5">
        <span className="font-mono text-xs text-ink-muted">
          {filename} · {lines.length} lines
        </span>
        <div className="flex items-center gap-1">
          <button type="button" className="btn-ghost min-h-[30px] px-2 text-xs" onClick={copy}>
            {copied ? <IconCheck /> : <IconCopy />}
            <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <button type="button" className="btn-ghost min-h-[30px] px-2 text-xs" onClick={download}>
            <IconDownload /> Download
          </button>
        </div>
      </div>
      <pre className="max-h-[32rem] overflow-auto bg-surface p-0 text-[12px] leading-[1.6]" tabIndex={0} aria-label={`${filename} source`}>
        <code className="grid grid-cols-[auto_1fr]">
          {lines.map((l, i) => (
            <span key={i} className="contents">
              <span className="select-none border-r border-line px-3 text-right text-ink-faint num" aria-hidden="true">
                {i + 1}
              </span>
              <span className="whitespace-pre px-3">{l || ' '}</span>
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}
