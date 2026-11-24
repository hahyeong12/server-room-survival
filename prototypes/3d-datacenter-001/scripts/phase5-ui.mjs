// Real-UI helpers for the Phase 5 (Issue #6) browser QA. Every state change goes through a real click / key on the
// 3D canvas, the monitor tabs, the rack card, the time buttons, the senior dialogue or a result screen.
// window.worldQA is read-only (snapshot of the engine state the page already received); no API call changes state.
import assert from 'node:assert/strict';
import {settle,snap} from './qa-lib.mjs';

export const S = page => snap(page);
export const story = async page => (await S(page)).game?.story;
export const req = async (page, rid) => (await S(page)).game.requests.find(r => r.id === rid);
// Like a player: a senior's talk box that is open is read first (it can sit over the monitor), then the click.
export async function click(page, sel) {
  if (!sel.includes('talk') && !sel.includes('screen-dialog') && await page.locator('#talk:not([hidden])').count()) await readAllTalk(page);
  await page.locator(sel).first().click(); await settle(page);
}
export async function places(page, route) { await click(page, `#places [data-route=${route}]`); await page.waitForTimeout(1100); }
export async function canvasClick(page, kind, id, { dbl = false } = {}) {
  const p = await page.evaluate(([k, i]) => k === 'rack' ? worldQA.projectAsset(i) : worldQA.projectWorld(i), [kind, id]);
  assert.ok(p?.visible, `${kind} ${id} is on screen`);
  if (dbl) await page.mouse.dblclick(p.x, p.y); else await page.mouse.click(p.x, p.y);
  await settle(page, 300); return p;
}
export async function toastText(page) { return page.evaluate(() => { const t = document.querySelector('#toast'); return t.hidden ? '' : t.textContent; }); }
export async function screenOpen(page) { return (await S(page)).screens.open; }

// The senior's pages: [다음] turns pages (changes nothing), the last button is the engine action / read record.
export async function readTalk(page, { expectEvent } = {}) {
  let n = 0;
  while (await page.locator('#talk:not([hidden]) [data-talk-done]').count() === 0 && await page.locator('#talk:not([hidden]) #talk-next').count()) {
    const before = (await S(page)).game.story.uiStep; await click(page, '#talk-next'); n++;
    assert.equal((await S(page)).game.story.uiStep, before, 'turning a page never advances the chapter');
  }
  const done = page.locator('#talk:not([hidden]) [data-talk-done]');
  if (!await done.count()) return null;
  const event = await done.getAttribute('data-talk-done');
  if (expectEvent) assert.equal(event, expectEvent);
  await done.click(); await settle(page, 300);
  return { event, pages: n + 1 };
}
export async function readAllTalk(page) { const seen = []; for (let i = 0; i < 4; i++) { const t = await readTalk(page); if (!t) break; seen.push(t.event); } return seen; }

export async function closeScreen(page, next = 'stay') { await page.waitForSelector(`#screen-dialog[open] [data-next=${next}]`); await click(page, `#screen-dialog[open] [data-next=${next}]`); }
// Close any senior card / job-done screen that is open (continue / stay), returning their kinds.
export async function drainScreens(page) {
  const kinds = [];
  for (let i = 0; i < 5; i++) {
    const open = await page.evaluate(() => document.querySelector('#screen-dialog').open);
    if (!open) break;
    const kind = await screenOpen(page); kinds.push(kind);
    if (['chapter-clear', 'chapter-failed', 'graduation'].includes(kind)) break;
    const sel = await page.locator('#screen-dialog[open] [data-next=continue]').count() ? 'continue' : 'stay';
    await click(page, `#screen-dialog[open] [data-next=${sel}]`); await page.waitForTimeout(150);
  }
  return kinds;
}

export async function tab(page, id) {
  if ((await S(page)).state.navigation.route !== 'noc') await places(page, 'noc');
  await click(page, `[data-ws-tab=${id}]`);
}
export async function readRequest(page, rid) {
  await tab(page, 'inbox'); await click(page, `[data-request-row="${rid}"]`); await click(page, '[data-read-request]');
}
export async function choosePlan(page, rid, mode, index = 0) {
  await tab(page, 'inbox'); await click(page, `[data-request-row="${rid}"]`);
  await tab(page, 'plan'); await page.waitForSelector(`[data-plan-option="${mode}:${index}"]`);
  await click(page, `[data-plan-option="${mode}:${index}"]`);
  const r = await req(page, rid); assert.equal(r.selection?.mode, mode, 'plan chosen (no resources yet)'); return r.selection;
}
// Start in the server hall: pick the plan's rack on the 3D canvas, press the rack card's start button.
export async function startInHall(page, rid) {
  await drainScreens(page); await readAllTalk(page);
  const r = await req(page, rid), rack = r.selection.slices[0].rack;
  await places(page, 'hall'); await click(page, '[data-camera=overview]'); await page.waitForTimeout(1300);
  await canvasClick(page, 'rack', rack);
  if ((await S(page)).state.facility.selectedId !== rack) { await page.selectOption('#equipment-select', rack); await settle(page); }
  await click(page, `[data-start-job="${rack}"]`);
  const after = await req(page, rid); assert.ok(after.allocation.length, `request #${rid} started on the engine`); return after;
}
export async function job(page, rid, mode, index = 0) { await drainScreens(page); await readAllTalk(page); await readRequest(page, rid); await choosePlan(page, rid, mode, index); return startInHall(page, rid); }
export async function advance(page, minutes = 10) { await click(page, `[data-advance="${minutes}"]`); }
export async function advanceUntil(page, test, { minutes = 10, limit = 40, onEach } = {}) {
  for (let i = 0; i < limit; i++) { if (await test(await S(page))) return true; await advance(page, minutes); if (onEach) await onEach(); }
  assert.ok(await test(await S(page)), 'virtual time reached the expected state'); return true;
}
export async function diagnose(page, rid) { await tab(page, 'inbox'); await click(page, `[data-request-row="${rid}"]`); await tab(page, 'diagnosis'); await page.waitForSelector('[data-responses]'); }
