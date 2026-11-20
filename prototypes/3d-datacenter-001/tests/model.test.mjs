import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createFacility, selected, selectAsset, injectFault, startRepair, advance, verify, readings, totals } from '../src/model.js';

test('24 racks and four utility assets, deterministic memory-only initial state', () => {
  const f = createFacility();
  assert.equal(f.assets.length, 28); assert.equal(totals(f).gpu, 192);
  assert.deepEqual(f, createFacility());
  assert.equal(selectAsset(f, 'not-an-asset'), false); assert.equal(selected(f).id, 'A-01');
});
for (const kind of ['network', 'power', 'cooling']) test(`${kind}: fault → repair → explicit verification; other assets preserved`, () => {
  const f = createFacility(), baseline = structuredClone(f.assets.slice(1));
  assert.equal(verify(f), false); assert.equal(startRepair(f), false);
  assert.equal(injectFault(f, kind), true); assert.equal(injectFault(f, kind), false);
  const a = selected(f), r = readings(a);
  if (kind === 'network') { assert.equal(r.network, 0); assert.ok(r.power > 0); }
  if (kind === 'power') { assert.equal(r.power, 0); assert.equal(totals(f).gpu, 184); }
  if (kind === 'cooling') { assert.ok(r.temp > 35); assert.ok(r.network > 0); }
  assert.equal(verify(f), false); assert.equal(startRepair(f), true);
  advance(f, 5.9); assert.equal(a.state, 'repairing'); assert.equal(verify(f), false);
  advance(f, .11); assert.equal(a.state, 'awaiting'); assert.equal(totals(f).awaiting, 1);
  advance(f, 100); assert.equal(a.state, 'awaiting');
  assert.equal(verify(f), true); assert.equal(a.state, 'verified'); assert.equal(verify(f), false);
  assert.deepEqual(readings(a), { ...a.base, online: 8 });
  assert.deepEqual(f.assets.slice(1), baseline);
});
test('independent simultaneous incidents survive selection changes', () => {
  const f = createFacility(); injectFault(f, 'network'); startRepair(f);
  selectAsset(f, 'B-02'); injectFault(f, 'cooling');
  advance(f, 7);
  assert.equal(selected(f).state, 'fault'); assert.equal(f.assets[0].state, 'awaiting');
  assert.equal(totals(f).faults, 1); assert.equal(totals(f).awaiting, 1);
  selectAsset(f, 'A-01'); verify(f); assert.equal(f.assets[7].state, 'fault');
});
test('invalid input cannot mutate state or move time backwards', () => {
  const f = createFacility(), initial = structuredClone(f);
  advance(f, NaN); advance(f, -1); advance(f, Infinity);
  assert.equal(injectFault(f, 'unknown'), false); assert.deepEqual(f, initial);
});
