import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
// The Python engine adapter (engine/server.py) listens on loopback only; the browser talks to it same-origin via /api.
const engine = `http://127.0.0.1:${process.env.SRS3D_ENGINE_PORT || 8765}`;
const proxy = { '/api': { target: engine, changeOrigin: false } };
export default defineConfig({
  base: './',
  server: { host: '127.0.0.1', port: 5173, strictPort: true, fs: { strict: true, allow: [root] }, proxy },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  build: { rollupOptions: { input: { main: root + 'index.html', lab: root + 'lab.html' }, output: { manualChunks: { three: ['three'] } } } },
});
