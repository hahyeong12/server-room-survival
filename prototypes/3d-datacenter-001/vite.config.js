import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
export default defineConfig({
  base: './',
  server: { host: '127.0.0.1', port: 5173, strictPort: true, fs: { strict: true, allow: [root] } },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true },
  build: { rollupOptions: { input: { main: root + 'index.html', lab: root + 'lab.html' }, output: { manualChunks: { three: ['three'] } } } },
});
