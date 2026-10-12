import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, existsSync, readFileSync } from 'node:fs';
import { extname, resolve } from 'node:path';
import { devIndex, publishedFile, shipRuns } from './scripts/publishedRuns';

/**
 * public/runs/ holds dev bundles with third-party screenshots — they must never ship. Production builds replace
 * dist/runs with ui/published/ (bundles published with tools/publish_run.py: owned sites / original designs).
 * PC_INCLUDE_RUNS=1 keeps the dev bundles for local previews only.
 */
function dropRunsFromBuild(): Plugin {
  return {
    name: 'pc-ship-runs',
    apply: 'build',
    closeBundle() {
      shipRuns(resolve(__dirname, 'dist'), resolve(__dirname, 'published'), process.env.PC_INCLUDE_RUNS === '1');
    },
  };
}

const TYPES: Record<string, string> = { '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png',
  '.svg': 'image/svg+xml', '.jsx': 'text/plain; charset=utf-8', '.jpg': 'image/jpeg', '.gif': 'image/gif', '.avif': 'image/avif' };

/** npm run dev shows what production shows: the published runs, plus the dev replays marked `dev` (hidden until
 *  "Show dev runs" is on). Published bundles are served from ui/published/; the rest falls through to public/runs. */
function publishedInDev(): Plugin {
  const published = resolve(__dirname, 'published');
  const readJson = (p: string) => (existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : []);
  return {
    name: 'pc-published-in-dev',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url ?? '';
        if (url.split('?')[0] === '/runs/index.json') {
          const idx = devIndex(readJson(resolve(published, 'index.json')), readJson(resolve(__dirname, 'public/runs/index.json')));
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify(idx));
          return;
        }
        const file = publishedFile(published, url);
        if (!file) return next();
        res.setHeader('Content-Type', TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream');
        res.setHeader('X-Content-Type-Options', 'nosniff');
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), dropRunsFromBuild(), publishedInDev()],
  server: {
    port: 5173,
    // npm run dev against a local `uvicorn orchestrator.api:app --port 8000` (live mode); override with PC_API_PROXY
    proxy: { '/api': { target: process.env.PC_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
  },
});
