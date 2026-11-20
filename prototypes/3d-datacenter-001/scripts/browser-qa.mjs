import { chromium } from 'playwright-core';
import { mkdir, writeFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const exec = promisify(execFile), out = resolve('qa'); await mkdir(out, { recursive: true });
const smoke = process.argv.includes('--smoke'), headless = process.argv.includes('--headless');
const urlArg = process.argv.find(arg => arg.startsWith('--url='));
const url = urlArg ? urlArg.slice('--url='.length) : 'http://127.0.0.1:5173';
const reportName = smoke ? (urlArg ? 'production-smoke.json' : 'smoke.json') : 'browser-qa.json';
const report = { mode: headless ? 'Chrome headless' : 'Chrome headed / isolated temporary profile', startedAt: new Date().toISOString(),
  url, checks: [], errors: [], consoleErrors: [], networkFailures: [], performance: [], gpu: [], memory: [], screenshots: [] };
let browser, page, monitoring = false, monitorPromise;
async function gpu(label) {
  try {
    const r = await exec('nvidia-smi', ['--query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw','--format=csv,noheader,nounits'], { windowsHide: true });
    report.gpu.push({ label, csv: r.stdout.trim(), scope: 'whole GPU, includes all other applications' });
  } catch(e) { report.gpu.push({ label, error: e.message }); }
}
async function shot(name) { await page.screenshot({ path: resolve(out, name), fullPage: true }); report.screenshots.push(name); }
async function check(name, fn) {
  try { await fn(); report.checks.push({ name, pass: true }); }
  catch (e) { report.checks.push({ name, pass: false, error: e.message }); throw e; }
}
const snapshot = () => page.evaluate(() => window.prototypeQA.snapshot());
async function waitState(state, id) { await page.waitForFunction(({ state, id }) => { const f = window.prototypeQA.snapshot().facility; return f.assets.find(a => a.id === (id || f.selectedId)).state === state; }, { state, id }); }
async function perf(label, seconds = 8) {
  const samples = [];
  for (let n = 0; n < seconds; n++) { await page.waitForTimeout(1000); samples.push(await snapshot()); }
  const valid = samples.filter(x => x.stats.fps > 0);
  report.performance.push({ label, samples: valid.map(x => ({ ...x.stats, heap: x.heap, renderer: x.renderer })) });
  await gpu(label);
}
try {
  await gpu('baseline-before-browser');
  browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless,
    args: ['--window-size=1920,1080', '--no-first-run', '--no-default-browser-check'], timeout: 30000 });
  report.browserVersion = browser.version();
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page = await context.newPage();
  page.on('pageerror', e => report.errors.push(e.stack || e.message));
  page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(m.text()); });
  page.on('requestfailed', r => report.networkFailures.push({ url: r.url(), failure: r.failure() }));
  const pageCDP = await context.newCDPSession(page), browserCDP = await browser.newBrowserCDPSession();
  await pageCDP.send('Performance.enable');
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.prototypeQA !== undefined, { timeout: 45000 });
  await page.waitForTimeout(7000);
  report.initial = await snapshot();
  report.systemGPU = (await browserCDP.send('SystemInfo.getInfo')).gpu;
  report.screen = await page.evaluate(() => ({ screen: { width: screen.width, height: screen.height }, innerWidth, innerHeight, devicePixelRatio, visibility: document.visibilityState }));
  await check('RTX 5070 hardware WebGL renderer', async () => assert.match(report.initial.renderer.renderer, /RTX 5070/));
  await check('initial scene: 24 racks, four utility devices, normal state', async () => {
    assert.equal(report.initial.facility.assets.length, 28); assert.equal(report.initial.facility.assets.filter(a => a.kind === 'rack').length, 24);
    assert.ok(report.initial.facility.assets.every(a => a.state === 'normal')); assert.equal(await page.locator('#fatal').isVisible(), false);
  });
  if (smoke) await check('smoke: no runtime errors, console errors or failed requests', async () => {
    assert.deepEqual(report.errors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.networkFailures, []);
  });
  await shot(urlArg ? '13-production-overview.png' : '01-overview-normal.png');
  if (!smoke) {
    monitoring = true;
    monitorPromise = (async () => {
      while (monitoring) {
        await gpu('sampling');
        try {
          const processes = (await browserCDP.send('SystemInfo.getProcessInfo')).processInfo;
          const pids = processes.map(p => p.id).filter(Number.isInteger);
          const mem = await exec('powershell.exe', ['-NoProfile', '-Command', `Get-Process -Id ${pids.join(',')} -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,WorkingSet64,PrivateMemorySize64 | ConvertTo-Json -Compress`], { windowsHide: true });
          report.memory.push({ time: new Date().toISOString(), processes: JSON.parse(mem.stdout), scope: 'owned QA Chrome process tree, working set / private bytes' });
        } catch (e) { report.memory.push({ error: e.message }); }
        await new Promise(r => setTimeout(r, 1500));
      }
    })();
    await perf('normal-overview', 10);
    await check('raycast selection with real canvas mouse input', async () => {
      const p = await page.evaluate(() => window.prototypeQA.projectAsset('D-06'));
      await page.mouse.click(p.x, p.y);
      assert.equal((await snapshot()).facility.selectedId, 'D-06');
      assert.equal(await page.locator('#asset-name').innerText(), 'RACK D-06');
    });
    await check('orbit / wheel zoom / right drag pan / keyboard move / focus', async () => {
      const canvas = page.locator('#viewport canvas'), rect = await canvas.boundingBox(), before = (await snapshot()).renderer;
      await page.mouse.move(rect.x + rect.width * .6, rect.y + rect.height * .6); await page.mouse.down();
      await page.mouse.move(rect.x + rect.width * .6 + 110, rect.y + rect.height * .6 - 30, { steps: 12 }); await page.mouse.up(); await page.waitForTimeout(800);
      assert.notDeepEqual((await snapshot()).renderer.camera, before.camera);
      const beforeZoom = (await snapshot()).renderer; await page.mouse.wheel(0, -250); await page.waitForTimeout(800); assert.notDeepEqual((await snapshot()).renderer.camera, beforeZoom.camera);
      const beforePan = (await snapshot()).renderer; await page.mouse.down({ button: 'right' }); await page.mouse.move(rect.x + rect.width * .6 + 160, rect.y + rect.height * .6 - 10, { steps: 10 }); await page.mouse.up({ button: 'right' }); await page.waitForTimeout(500); assert.notDeepEqual((await snapshot()).renderer.target, beforePan.target);
      await canvas.focus(); const beforeKey = (await snapshot()).renderer; await page.keyboard.down('w'); await page.waitForTimeout(500); await page.keyboard.up('w'); assert.notDeepEqual((await snapshot()).renderer.target, beforeKey.target);
      await page.keyboard.press('f'); await page.waitForTimeout(1500); assert.ok(Math.abs((await snapshot()).renderer.target[0] - (-2.1)) < 1);
    });
    for (const v of ['hall','control','aisle','overview']) {
      await page.locator(`[data-view="${v}"]`).click(); await page.waitForTimeout(1800);
      await shot(({ hall: '02-server-hall.png', control: '03-control-room.png', aisle: '04-cold-aisle.png', overview: '05-overview-selected.png' })[v]);
    }
    await check('layer toggles affect scene; restored after test', async () => {
      for (const name of ['network','cooling','power']) {
        await page.locator(`[data-layer="${name}"]`).click(); assert.equal((await snapshot()).renderer.layers[name], false);
        await page.locator(`[data-layer="${name}"]`).click(); assert.equal((await snapshot()).renderer.layers[name], true);
      }
    });
    for (const [index, kind] of ['network','power','cooling'].entries()) {
      await check(`${kind}: UI fault / repair / explicit post-check; consistent visuals and telemetry`, async () => {
        const id = ['D-06','D-05','D-04'][index];
        await page.locator('#equipment-select').selectOption(id); await page.locator('#fault-kind').selectOption(kind);
        const before = await snapshot(), others = before.facility.assets.filter(a => a.id !== id);
        await page.locator('#inject-fault').click(); await waitState('fault'); await page.waitForTimeout(400);
        assert.match(await page.locator('#status-title').innerText(), /장애/); assert.equal(await page.locator('#verify').isEnabled(), false);
        const fault = await snapshot(); assert.notEqual(fault.visuals[id].color, before.visuals[id].color);
        assert.deepEqual(fault.facility.assets.filter(a => a.id !== id), others);
        if (kind === 'network') { assert.equal(fault.visuals[id].networkFlow, false); assert.match(await page.locator('#network-value').innerText(), /^0/); }
        if (kind === 'power') assert.match(await page.locator('#power-value').innerText(), /^0.0/);
        if (kind === 'cooling') assert.match(await page.locator('#temp-value').innerText(), /38.6/);
        await shot(`06-${kind}-fault.png`); if (kind === 'network') await perf('network-fault', 6);
        await page.locator('#start-repair').click(); await waitState('repairing');
        await page.waitForTimeout(1200); await shot(`07-${kind}-repairing.png`);
        await waitState('awaiting'); assert.equal(await page.locator('#verify').isEnabled(), true); await shot(`08-${kind}-awaiting.png`);
        await page.waitForTimeout(1000); assert.equal((await snapshot()).facility.assets.find(a => a.id === id).state, 'awaiting');
        await page.locator('#verify').click(); await waitState('verified'); await shot(`09-${kind}-verified.png`);
      });
    }
    await check('utility equipment selection and independent state change', async () => {
      await page.locator('#equipment-select').selectOption('UPS-01'); assert.match(await page.locator('#asset-kind').innerText(), /POWER/);
      await page.locator('#fault-kind').selectOption('power'); await page.locator('#inject-fault').click(); await waitState('fault');
      await page.locator('#start-repair').click(); await waitState('awaiting'); await page.locator('#verify').click(); await waitState('verified');
      await page.locator('#equipment-select').selectOption('CRAC-01'); assert.match(await page.locator('#asset-kind').innerText(), /COOLING/);
      await page.locator('#equipment-select').selectOption('NET-01'); assert.match(await page.locator('#asset-kind').innerText(), /NETWORK/);
      await page.locator('[data-asset="A-01"]').click(); assert.equal((await snapshot()).facility.selectedId, 'A-01');
    });
    await perf('after-four-repair-cycles', 8);
    await check('geometry and textures stay bounded after state cycles', async () => {
      const s = await snapshot(); assert.equal(s.renderer.geometries, report.initial.renderer.geometries); assert.equal(s.renderer.textures, report.initial.renderer.textures);
    });
    for (const size of [{width:1440,height:900},{width:1280,height:800},{width:720,height:900}]) {
      await page.setViewportSize(size); await page.waitForTimeout(1200);
      await check(`layout ${size.width}x${size.height} no horizontal overflow or canvas zero size`, async () => {
        const l = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: innerWidth, canvas: document.querySelector('#viewport canvas').getBoundingClientRect().width }));
        assert.ok(l.scroll <= l.width + 1); assert.ok(l.canvas > 300);
      });
      await shot(`10-layout-${size.width}.png`);
    }
    await page.setViewportSize({width:1920,height:1080}); await page.waitForTimeout(1800);
    await page.locator('#perf-toggle').click(); await shot('11-performance.png'); await page.locator('#perf-toggle').click();
    await check('reload resets only memory demo; no persistence or external requests', async () => {
      await page.reload({ waitUntil: 'networkidle' }); await page.waitForFunction(() => !!window.prototypeQA); await page.waitForTimeout(3500);
      assert.ok((await snapshot()).facility.assets.every(a => a.state === 'normal'));
      const storage = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })); assert.deepEqual(storage, {local:0,session:0});
    });
    report.final = await snapshot();
    report.cdpMetrics = await pageCDP.send('Performance.getMetrics');
    await check('no browser runtime / console errors / failed requests', async () => {
      assert.deepEqual(report.errors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.networkFailures, []);
    });
    await shot('12-final-overview.png');
  }
} catch (e) { report.failure = e.stack || e.message; process.exitCode = 1; }
finally {
  monitoring = false; if (monitorPromise) await monitorPromise;
  if (browser) await browser.close(); await gpu('after-browser-close');
  report.finishedAt = new Date().toISOString();
  await writeFile(resolve(out, reportName), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ checks: report.checks, failure: report.failure, renderer: report.initial?.renderer, errors: report.errors, consoleErrors: report.consoleErrors, screenshots: report.screenshots }, null, 2));
}
