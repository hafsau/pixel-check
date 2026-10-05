/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Live API origin, e.g. https://api.pixel-check.dev. Empty = same origin (dev: proxied to localhost:8000). */
  readonly VITE_API_BASE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
