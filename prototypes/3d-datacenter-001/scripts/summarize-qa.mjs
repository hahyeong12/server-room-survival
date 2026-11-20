import { readFile, writeFile } from 'node:fs/promises';

const report = JSON.parse(await readFile('qa/browser-qa.json', 'utf8'));
const range = values => {
  const x = values.filter(Number.isFinite);
  return x.length ? { min: Math.min(...x), max: Math.max(...x), mean: x.reduce((a,b) => a+b,0) / x.length, samples: x.length } : null;
};
const perf = report.performance.map(p => ({ label: p.label,
  fps: range(p.samples.map(s => s.fps)), p95FrameMs: range(p.samples.map(s => s.p95FrameMs)), gpuMs: range(p.samples.map(s => s.gpuMs)),
  heapMiB: range(p.samples.map(s => s.heap?.used / 1048576)),
  geometries: [...new Set(p.samples.map(s => s.renderer.geometries))], textures: [...new Set(p.samples.map(s => s.renderer.textures))],
  calls: range(p.samples.map(s => s.renderer.calls)) }));
const gpuRows = report.gpu.filter(g => g.csv).map(g => ({ label: g.label, cols: g.csv.split(',').map(x => x.trim()) }));
const sampled = gpuRows.filter(g => g.label === 'sampling');
const sums = report.memory.filter(m => Array.isArray(m.processes)).map(m => ({ time: m.time,
  workingSetMiB: m.processes.reduce((s,p) => s+p.WorkingSet64,0) / 1048576,
  privateMiB: m.processes.reduce((s,p) => s+p.PrivateMemorySize64,0) / 1048576 }));
const summary = {
  browser: report.browserVersion, mode: report.mode, renderer: report.initial?.renderer,
  checks: { passed: report.checks.filter(x => x.pass).length, failed: report.checks.filter(x => !x.pass).length, total: report.checks.length },
  failure: report.failure || null, runtimeErrors: report.errors, consoleErrors: report.consoleErrors, networkFailures: report.networkFailures,
  performance: perf, gpu: { scope: 'system-wide NVIDIA-SMI samples', baseline: gpuRows.find(x => x.label === 'baseline-before-browser'),
    utilizationPercent: range(sampled.map(x => Number(x.cols[2]))), vramMiB: range(sampled.map(x => Number(x.cols[4]))),
    temperatureC: range(sampled.map(x => Number(x.cols[6]))), afterClose: gpuRows.find(x => x.label === 'after-browser-close') },
  ownedBrowserMemory: { scope: 'QA Chrome tree; sums may double-count shared pages in working sets', workingSetMiB: range(sums.map(x=>x.workingSetMiB)), privateMiB: range(sums.map(x=>x.privateMiB)) },
  screenshots: report.screenshots,
};
await writeFile('qa/metrics-summary.json', JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
