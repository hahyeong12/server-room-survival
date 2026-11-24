// One command for local play: starts the Python engine adapter and the Vite dev server together (loopback only).
// Python: SRS_PYTHON env, else `python` (Windows: `py -3` fallback). No packages are installed.
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const cwd = fileURLToPath(new URL('..', import.meta.url));
function findPython() {
  const candidates = [process.env.SRS_PYTHON, 'python', process.platform === 'win32' ? 'py' : 'python3'].filter(Boolean);
  for (const exe of candidates) {
    const args = exe === 'py' ? ['-3', '--version'] : ['--version'];
    const r = spawnSync(exe, args, { encoding: 'utf8' });
    if (r.status === 0 && /Python 3\.(1[0-9]|[2-9][0-9])/.test(r.stdout + r.stderr)) return exe === 'py' ? [exe, ['-3']] : [exe, []];
  }
  return null;
}
const python = findPython();
if (!python) { console.error('Python 3.10+ 를 찾지 못했습니다. SRS_PYTHON 환경 변수에 python.exe 경로를 지정하세요.'); process.exit(1); }
const children = [];
const run = (cmd, args, name) => { const c = spawn(cmd, args, { cwd, stdio: 'inherit', shell: process.platform === 'win32' && cmd.endsWith('.cmd') }); c.on('exit', code => { console.log(`[${name}] 종료 (${code})`); stop(); }); children.push(c); };
function stop() { for (const c of children) if (c.exitCode === null) c.kill(); }
process.on('SIGINT', () => { stop(); process.exit(0); });
run(python[0], [...python[1], '-m', 'engine.server'], 'engine');
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'dev'], 'vite');
