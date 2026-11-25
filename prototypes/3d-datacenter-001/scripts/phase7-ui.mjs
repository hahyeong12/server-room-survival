// Real-UI helpers for the Phase 7 (Issue #8) incident-response browser QA. Every state change is a real click / key /
// select on the menu, talk box, monitor tabs, incident card, facility interiors (campus double-click is replaced by the
// card's own [이동] buttons and the places bar), the 3D racks and the time buttons. window.worldQA is read-only.
import assert from 'node:assert/strict';
import {settle} from './qa-lib.mjs';
import {S,G,click,places,canvasClick,tab,read,choose,startHall,drainJobs} from './phase6-ui.mjs';

export {S,G,click,places,tab,read,choose,startHall,drainJobs};
export const inc = async (page, id) => (await G(page)).incident.records.find(r => r.id === id);
export const incs = async page => (await G(page)).incident.records;
export async function talkThrough(page) {
  await page.waitForSelector('#talk:not([hidden])');
  let pages = 1;
  while (await page.locator('#talk:not([hidden]) #talk-next').count()) { await click(page, '#talk-next'); pages++; }
  await click(page, '#talk:not([hidden]) #coach-start');
  assert.equal((await G(page)).global.briefed, true);
  return pages;
}
// Close informational job/incident screens; returns what remains open.
export async function drain(page) {
  for (let i = 0; i < 8; i++) {
    const open = (await S(page)).screens.open;
    if (open !== 'job-done') return open;
    await click(page, '#screen-dialog[open] [data-next=stay]'); await page.waitForTimeout(100);
  }
  return (await S(page)).screens.open;
}
export async function advance(page, minutes = 10) { await click(page, `[data-advance="${minutes}"]`); return drain(page); }
export async function incidentTab(page, id) {
  await drain(page);
  if ((await S(page)).state.navigation.route !== 'noc') await places(page, 'noc');
  if (await page.locator('[data-noc-view=desk]:not(.active)').count()) await click(page, '#noc-tools [data-noc-view=desk]');
  await click(page, '[data-ws-tab=incident]');
  if (id && await page.locator(`[data-incident-select="${id}"]:not(.active)`).count()) await click(page, `[data-incident-select="${id}"]`);
  if (id) await page.waitForSelector(`.inc-card[data-incident="${id}"]`);
}
// Start a request from the inbox with a chosen plan (mode + option index) through the hall rack.
export async function startJob(page, rid, mode, index = 0) { await read(page, rid); await choose(page, rid, mode, index); return startHall(page, rid); }
// Advance 10 minutes at a time until the predicate holds on the engine snapshot (read-only), max n steps.
export async function until(page, pred, n = 20, minutes = 10) {
  for (let i = 0; i < n; i++) { if (await pred(await G(page))) return true; await advance(page, minutes); }
  return pred(await G(page));
}
// Record one probe: go to its place with the card's own button, then press the on-site [관측] button.
export async function observe(page, id, probe) {
  await incidentTab(page, id);
  const away = page.locator(`.inc-card [data-probe-away="${probe}"]`);
  if (await away.count()) {
    await away.first().click(); await settle(page, 300); await page.waitForTimeout(900);
    // On site: the facility card (room) or the rack card (hall) shows the recordable probes for this incident.
    if ((await S(page)).state.navigation.route === 'hall') {
      // Look at the job's rack in the 3D hall (the rack card carries the hall's on-site evidence panel).
      await click(page, '[data-camera=overview]'); await page.waitForTimeout(900);
      const rec = await inc(page, id), rack = ({ A: 'A-01', B: 'B-01', C: 'C-01', D: 'D-01' })[(rec.scope?.jobs?.[0]?.servers ?? ['A'])[0]];
      const p = await page.evaluate(r => worldQA.projectAsset(r), rack);
      if (p?.visible) { await page.mouse.click(p.x, p.y); await settle(page, 300); }
    }
    const before = (await inc(page, id)).evidence.length;
    await click(page, `[data-site-evidence] .inc-site-row:has-text("${id}") [data-probe="${probe}"]`);
    assert.equal((await inc(page, id)).evidence.length, before + 1, `${id} ${probe} recorded on site`);
    return (await inc(page, id)).evidence.at(-1);
  }
  const before = (await inc(page, id)).evidence.length;
  await click(page, `.inc-card[data-incident="${id}"] [data-probe="${probe}"]`);
  assert.equal((await inc(page, id)).evidence.length, before + 1, `${id} ${probe} recorded at the monitor`);
  return (await inc(page, id)).evidence.at(-1);
}
export async function hypothesis(page, id, cause) {
  await incidentTab(page, id);
  await page.selectOption(`[data-cause-select="${id}"]`, cause); await settle(page, 100);
  await click(page, `[data-hypothesis="${id}"]`);
  return (await inc(page, id)).hypotheses.at(-1);
}
export async function act(page, id, action, rid) {
  await incidentTab(page, id);
  if (rid !== undefined && await page.locator(`[data-incident-rid="${id}"]`).count()) { await page.selectOption(`[data-incident-rid="${id}"]`, String(rid)); await settle(page, 100); }
  const before = (await inc(page, id)).actions.length;
  await click(page, `.inc-card[data-incident="${id}"] [data-incident-action="${action}"]`);
  const r = await inc(page, id);
  return r.actions.length > before ? r.actions.at(-1) : null;
}
export async function ack(page, id) { await incidentTab(page, id); await click(page, `[data-incident-ack="${id}"]`); return inc(page, id); }
export async function notify(page, id) { await incidentTab(page, id); await click(page, `[data-incident-notify="${id}"]`); return (await inc(page, id)).notified; }
export async function verify(page, id) { await incidentTab(page, id); await click(page, `[data-incident-verify="${id}"]`); return inc(page, id); }
export async function report(page, id) { await incidentTab(page, id); await click(page, `[data-incident-report="${id}"]`); return inc(page, id); }
