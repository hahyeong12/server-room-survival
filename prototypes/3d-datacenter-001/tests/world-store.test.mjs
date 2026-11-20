import { test } from 'node:test';
import assert from 'node:assert/strict';
import {createWorldStore,breadcrumbs,FIXTURE} from '../src/world-store.js';

test('four levels, complete breadcrumb and upper navigation without domain changes',()=>{
  const store=createWorldStore(), before=store.domainSnapshot();
  for(let n=0;n<10;n++) for(const route of ['world','noc','campus','hall']) assert.equal(store.navigate(route),true);
  assert.deepEqual(breadcrumbs('hall').map(x=>x.id),['world','noc','campus','hall']);
  assert.equal(store.back(),true);assert.equal(store.state.navigation.route,'campus');store.back();store.back();assert.equal(store.back(),false);
  assert.deepEqual(store.domainSnapshot(),before);
});
test('invalid route/country/facility/rack IDs including object prototypes are rejected atomically',()=>{
  const store=createWorldStore(),before=store.snapshot();
  for(const id of ['invalid','__proto__','constructor','toString',null,undefined]){
    assert.equal(store.navigate(id),false); assert.equal(store.selectCountry(id),false);assert.equal(store.selectFacility(id),false);assert.equal(store.selectRack(id),false);
  } assert.deepEqual(store.snapshot(),before); assert.deepEqual(breadcrumbs('unknown'),[]);
});
test('selection is view-only and fixture conditions are deeply immutable',()=>{
  const store=createWorldStore(),before=store.domainSnapshot();
  store.selectCountry('JP');store.selectFacility('COOLING');store.selectRack('A-02');
  assert.deepEqual(store.domainSnapshot(),before);assert.equal(store.state.facility.selectedId,'A-02');
  assert.throws(()=>{FIXTURE.terms.gpu=900;},TypeError);
  const copy=store.snapshot();copy.request.terms.gpu=900;assert.equal(store.state.request.terms.gpu,8);
});
