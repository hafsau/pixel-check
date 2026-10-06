import { useState } from 'react';
import { projectFiles, projectZipName, type ProjectMeta } from '../lib/project';
import { zipStore } from '../lib/zip';
import { downloadBlob } from '../lib/download';
import { IconDownload } from './Icons';

/** Primary action: zip App.jsx into a runnable Vite + React + Tailwind project, in the browser (no upload). */
export function DownloadProject({ code, meta, className = '' }: { code: string; meta: ProjectMeta; className?: string }) {
  const [done, setDone] = useState(false);
  const go = () => {
    const zip = zipStore(projectFiles(code, meta).map((f) => ({ path: f.path, data: f.content })));
    downloadBlob(zip as BlobPart, projectZipName(meta.id), 'application/zip');
    setDone(true);
    window.setTimeout(() => setDone(false), 2000);
  };
  return (
    <button type="button" className={`btn-primary ${className}`} onClick={go} aria-describedby="dl-project-note">
      <IconDownload /> Download project (.zip)
      <span id="dl-project-note" className="sr-only">
        A Vite + React + Tailwind project with this App.jsx, built in your browser. Run npm install, then npm run dev.
      </span>
      <span className="sr-only" aria-live="polite">
        {done ? 'Download started.' : ''}
      </span>
    </button>
  );
}

/** Project metadata for a static run (replay or live). */
export function runProjectMeta(run: { id: string; title: string; page?: string; created: number; result: { match: number; per_bp: Record<string, number | undefined> }; breakpoints?: { name: string; width: number }[] }, sourceHost?: string | null, bps?: { name: string; width: number }[]): ProjectMeta {
  const list = bps ?? run.breakpoints ?? [];
  return {
    id: run.id,
    title: run.title.replace(/\s*\((dev capture)\)\s*$/, ''),
    source: sourceHost ? `a capture of ${sourceHost}` : `three design frames${run.page ? ` (${run.page})` : ''}`,
    match: run.result.match,
    scores: list.map((b) => ({ name: b.name, width: b.width, score: run.result.per_bp[b.name] })),
    created: run.created,
  };
}
