// Shared QA helpers: start an isolated stack (Python engine with a temporary save folder + its own Vite on
// another port and cache), launch installed Chrome, and wait for engine round trips. No user saves are touched.
import {spawn} from 'node:child_process';
import {existsSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

export const ROOT = fileURLToPath(new URL('..', import.meta.url));
export const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
export function python() {
  if (process.env.SRS_PYTHON) return process.env.SRS_PYTHON;
  const conda = 'C:/Users/hahye/anaconda3/python.exe';
  return existsSync(conda) ? conda : 'python';
}
async function waitFor(url, ms = 30000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { try { const r = await fetch(url); if (r.ok) return await r.json(); } catch { /* not up yet */ } await new Promise(r => setTimeout(r, 300)); }
  throw new Error(`timeout waiting for ${url}`);
}
export function tempSaveDir() { return mkdtempSync(join(tmpdir(), 'srs3d-qa-')); }
export async function startStack({ enginePort = 8775, vitePort = 5175, log = () => {}, saveDir = tempSaveDir() } = {}) {
  const procs = [];
  const spawnEngine = () => spawn(python(), ['-m', 'engine.server', '--port', String(enginePort), '--save-dir', saveDir], { cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  let engine = spawnEngine();
  const vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'],
    { cwd: ROOT, env: { ...process.env, SRS3D_ENGINE_PORT: String(enginePort), SRS3D_VITE_CACHE: '.qa-saves/vite-cache' } });
  for (const [name, p] of [['engine', engine], ['vite', vite]]) { procs.push(p); p.stdout.on('data', d => log(`[${name}] ${d}`)); p.stderr.on('data', d => log(`[${name}!] ${d}`)); }
  const url = `http://127.0.0.1:${vitePort}/`;
  try { await waitFor(`http://127.0.0.1:${enginePort}/api/health`); await waitFor(`${url}api/health`); }
  catch (e) { for (const p of procs) p.kill(); throw e; }
  return { url, saveDir, get engine() { return engine; },
    // Phase 5: stop the Python engine process (saves stay on disk) and start a fresh one on the same save folder.
    async restartEngine() {
      const old = engine; const gone = new Promise(r => old.once('exit', r)); old.kill(); await gone;
      engine = spawnEngine(); procs.push(engine); engine.stdout.on('data', d => log(`[engine] ${d}`)); engine.stderr.on('data', d => log(`[engine!] ${d}`));
      await waitFor(`http://127.0.0.1:${enginePort}/api/health`);
    },
    async stop() { for (const p of procs) p.kill(); await new Promise(r => setTimeout(r, 800)); try { rmSync(saveDir, { recursive: true, force: true }); } catch { /* locked files: left in temp */ } } };
}
export async function settle(page, ms = 250) { await page.evaluate(() => window.worldQA.idle()); await page.waitForTimeout(ms); }
export const snap = page => page.evaluate(() => window.worldQA.snapshot());
