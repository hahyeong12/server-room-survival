// Real-UI helpers for the Phase 6 (Issue #7) global-shift browser QA. Every state change is a real click / key on
// the menu, the senior's talk box, the monitor tabs, the inbox filter, the plan cards, the 3D canvas (racks, world
// cities), the rack card's start button or the time buttons. window.worldQA is read-only.
import assert from 'node:assert/strict';
import {settle,snap} from './qa-lib.mjs';

export const S = page => snap(page);
export const G = async page => (await S(page)).game;
export async function click(page, sel) { await page.locator(sel).first().click(); await settle(page); }
export async function places(page, route) { await click(page, `#places [data-route=${route}]`); await page.waitForTimeout(1100); }
export async function toastText(page) { return page.evaluate(() => { const t = document.querySelector('#toast'); return t.hidden ? '' : t.textContent; }); }
export async function canvasClick(page, kind, id) {
  const p = await page.evaluate(([k, i]) => k === 'rack' ? worldQA.projectAsset(i) : worldQA.projectWorld(i), [kind, id]);
  assert.ok(p?.visible, `${kind} ${id} is on screen`);
  await page.mouse.click(p.x, p.y); await settle(page, 300); return p;
}
// The senior's shift briefing: [다음] only turns pages; [근무 시작] is the engine's briefing confirmation.
export async function briefing(page) {
  await page.waitForSelector('#talk:not([hidden])');
  let pages = 1;
  while (await page.locator('#talk:not([hidden]) #talk-next').count()) {
    const before = (await G(page)).global.briefed; await click(page, '#talk-next'); pages++;
    assert.equal((await G(page)).global.briefed, before, 'turning a page does not start the shift');
  }
  await click(page, '#talk:not([hidden]) #coach-start');
  assert.equal((await G(page)).global.briefed, true);
  return pages;
}
// A site's request in the CURRENT shift (each shift has one request per city).
export async function rid(page, site) {
  const g = await G(page), ids = g.global.kind === 'shift' ? g.global.requestIds : g.requests.map(r => r.id);
  const r = g.requests.find(x => x.code === site && ids.includes(x.id)); assert.ok(r, `request from ${site}`); return r.id;
}
export async function req(page, id) { return (await G(page)).requests.find(r => r.id === id); }
export async function tab(page, id) {
  await drainJobs(page);   // a finished/rejected request opens an informational screen first
  if ((await S(page)).state.navigation.route !== 'noc') await places(page, 'noc');
  if (await page.locator('[data-noc-view=desk]:not(.active)').count()) await click(page, '#noc-tools [data-noc-view=desk]');
  await click(page, `[data-ws-tab=${id}]`);
}
export async function selectRow(page, id) {
  await tab(page, 'inbox');
  if (!await page.locator(`[data-request-row="${id}"]`).count()) await click(page, '[data-filter=all]');
  await click(page, `[data-request-row="${id}"]`);
}
export async function read(page, id) { await selectRow(page, id); await click(page, `[data-read-request="${id}"]`); }
export async function planTab(page, id) { await selectRow(page, id); await tab(page, 'plan'); await page.waitForSelector('[data-plan-list]'); }
export async function choose(page, id, mode, index = 0) {
  await planTab(page, id); await page.waitForSelector(`[data-plan-option="${mode}:${index}"]`);
  await click(page, `[data-plan-option="${mode}:${index}"]`);
  const r = await req(page, id); assert.equal(r.selection?.mode, mode, 'plan chosen (no resources yet)'); return r.selection;
}
export async function startHall(page, id) {
  const r = await req(page, id), rack = r.selection.slices[0].rack;
  await places(page, 'hall'); await click(page, '[data-camera=overview]'); await page.waitForTimeout(1300);
  await canvasClick(page, 'rack', rack);
  if ((await S(page)).state.facility.selectedId !== rack) { await page.selectOption('#equipment-select', rack); await settle(page); }
  await click(page, `[data-start-job="${rack}"]`);
  const after = await req(page, id); assert.ok(after.allocation.length, `request #${id} started on the engine`); return after;
}
export async function start(page, id, mode) { await read(page, id); await choose(page, id, mode); return startHall(page, id); }
// Customer negotiation on the plan card: propose the economy alternative, then read the customer's reply.
export async function negotiate(page, id) {
  await read(page, id); await planTab(page, id);
  await click(page, `[data-propose="${id}"]`); await page.waitForSelector(`[data-check-reply="${id}"]`);
  await click(page, `[data-check-reply="${id}"]`);
  return (await req(page, id)).proposal;
}
export async function wait(page, id) { await read(page, id); await click(page, `[data-wait="${id}"]`); assert.equal((await req(page, id)).status, 'waiting'); }
export async function reject(page, id, reason) {
  await read(page, id); await page.fill(`[data-reject-reason="${id}"]`, reason); await settle(page, 100); await click(page, `[data-reject="${id}"]`);
  assert.equal((await req(page, id)).status, 'rejected');
}
// Close per-request "job done" screens (they are informational); a shift result screen is left open.
export async function drainJobs(page) {
  for (let i = 0; i < 6; i++) {
    const open = (await S(page)).screens.open;
    if (open !== 'job-done') return open;
    await click(page, '#screen-dialog[open] [data-next=stay]'); await page.waitForTimeout(120);
  }
  return (await S(page)).screens.open;
}
export async function advance(page, minutes = 10) { await click(page, `[data-advance="${minutes}"]`); return drainJobs(page); }
