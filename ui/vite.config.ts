import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
import { shipRuns } from './scripts/publishedRuns';

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

export default defineConfig({
  plugins: [react(), dropRunsFromBuild()],
  server: {
    port: 5173,
    // npm run dev against a local `uvicorn orchestrator.api:app --port 8000` (live mode); override with PC_API_PROXY
    proxy: { '/api': { target: process.env.PC_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
  },
});
