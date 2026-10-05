import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { rmSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * public/runs/ currently holds dev bundles with third-party screenshots — they must never ship.
 * Production builds drop dist/runs unless PC_INCLUDE_RUNS=1 (set it once the bundles are
 * replaced with original benchmark designs).
 */
function dropRunsFromBuild(): Plugin {
  return {
    name: 'pc-drop-runs',
    apply: 'build',
    closeBundle() {
      if (process.env.PC_INCLUDE_RUNS === '1') return;
      rmSync(resolve(__dirname, 'dist/runs'), { recursive: true, force: true });
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
