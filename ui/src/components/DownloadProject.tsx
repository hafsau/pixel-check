import { useState } from 'react';
import { fetchAssetBytes, projectEntries, projectZipName, type ImagesMode, type ProjectMeta } from '../lib/project';
import { zipStore } from '../lib/zip';
import { downloadBlob } from '../lib/download';
import { IconDownload } from './Icons';

/** Owned sites: the delivered code, its asset list and how to resolve a bundle path to a URL. */
export interface OwnedCode {
  code: string;
  assets: string[];
  asset: (rel: string) => string;
}

/** Primary action: zip App.jsx into a runnable Vite + React + Tailwind project, in the browser (no upload).
 * With `owned`, the zip carries the delivered code and the site's images (public/assets/), or the scored code if they fail. */
export function DownloadProject({ code, meta, owned, className = '' }: { code: string; meta: ProjectMeta; owned?: OwnedCode | null; className?: string }) {
  const [state, setState] = useState<'idle' | 'busy' | ImagesMode>('idle');
  const go = async () => {
    if (state === 'busy') return;
    setState('busy');
    const { entries, images } = await projectEntries({
      scored: code,
      delivered: owned?.code ?? null,
      assets: owned?.assets ?? [],
      meta,
      fetchAsset: (rel) => fetchAssetBytes(new URL(owned!.asset(rel), window.location.href).href),
    });
    downloadBlob(zipStore(entries) as BlobPart, projectZipName(meta.id), 'application/zip');
    setState(images);
    window.setTimeout(() => setState('idle'), images === 'fallback' ? 6000 : 2000);
  };
  return (
    <span className={`inline-flex flex-col items-end gap-1 ${className}`}>
      <button type="button" className="btn-primary" onClick={go} aria-busy={state === 'busy'} aria-describedby="dl-project-note">
        <IconDownload /> Download project (.zip)
        <span id="dl-project-note" className="sr-only">
          A Vite + React + Tailwind project with this App.jsx, built in your browser. Run npm install, then npm run dev.
        </span>
      </button>
      <span className={state === 'fallback' ? 'text-[11px] text-ink-muted' : 'sr-only'} aria-live="polite">
        {state === 'fallback' ? 'Images could not be downloaded: zipped the code as scored.' : state === 'own' || state === 'placeholder' ? 'Download started.' : ''}
      </span>
    </span>
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
