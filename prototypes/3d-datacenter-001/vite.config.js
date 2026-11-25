import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
// Phase 6: the global content catalog is ONE file shared with the Python engine (aidc/global_ops). Only that file
// is added to what the dev server may read; nothing else outside this prototype is served.
const catalogFile = fileURLToPath(new URL('../../aidc/global_ops/catalog_v1.json', import.meta.url));
// The Python engine adapter (engine/server.py) listens on loopback only; the browser talks to it same-origin via /api.
const engine = `http://127.0.0.1:${process.env.SRS3D_ENGINE_PORT || 8765}`;
const proxy = { '/api': { target: engine, changeOrigin: false } };
export default defineConfig({
  base: './',
  // QA runs a second dev server with its own dependency cache (SRS3D_VITE_CACHE) so it never invalidates a running one.
  cacheDir: process.env.SRS3D_VITE_CACHE || 'node_modules/.vite',
  server: { host: '127.0.0.1', port: 5173, strictPort: true, fs: { strict: true, allow: [root, catalogFile] }, proxy },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  build: { rollupOptions: { input: { main: root + 'index.html', lab: root + 'lab.html' }, output: { manualChunks: { three: ['three'] } } } },
});
