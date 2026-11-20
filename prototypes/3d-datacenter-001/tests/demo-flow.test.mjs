import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createWorldStore,FIXTURE} from '../src/world-store.js';
import {nextDemoStep} from '../src/demo-actions.js';

function prepare(){const s=createWorldStore();s.act('review');s.navigate('noc');s.act('accept');s.navigate('hall');s.selectRack('D-06');return s;}
test('complete deterministic SG flow, immutable identity/conditions and isolated rack effects',()=>{
  const store=prepare(),others=structuredClone(store.state.facility.assets.filter(a=>a.id!=='D-06'));
  for(const [action,phase,progress]of [['start','running',25],['advance','fault',40],['repair','repairing',40],['repair-complete','awaiting',40],['verify','recovered',60],['finish','completed',100]]){
    assert.equal(store.act(action).ok,true);assert.equal(store.state.request.phase,phase);assert.equal(store.state.request.progress,progress);
    assert.deepEqual(store.state.request.terms,FIXTURE.terms);for(const key of ['id','customerId','rackId','buildingId','facilityId'])assert.equal(store.state.request[key],FIXTURE[key]);
    const domain=store.domainSnapshot();for(const place of ['noc','world','campus','hall'])store.navigate(place);assert.deepEqual(store.domainSnapshot(),domain);
    assert.deepEqual(store.state.facility.assets.filter(a=>a.id!=='D-06'),others);
  }
  assert.equal(store.act('report').ok,false);store.navigate('noc');assert.equal(store.act('report').ok,true);assert.equal(store.state.request.steps,9);assert.equal(store.state.request.history.length,9);assert.equal(nextDemoStep(store.state),null);
  const a=store.state.facility.assets.find(a=>a.id==='D-06');assert.equal(a.state,'verified');assert.equal(store.state.facility.elapsed,6);
});
test('wrong stage, wrong location, wrong country or wrong rack cannot advance domain',()=>{
  const s=createWorldStore();
  for(const action of ['accept','start','advance','repair','repair-complete','verify','finish','report','__proto__','constructor',undefined]){const before=s.domainSnapshot();assert.equal(s.act(action).ok,false);assert.deepEqual(s.domainSnapshot(),before);}
  s.navigate('world');s.selectCountry('JP');let before=s.domainSnapshot();assert.equal(s.act('review').ok,false);assert.deepEqual(s.domainSnapshot(),before);
  s.navigate('campus');assert.equal(s.act('review').ok,false);assert.deepEqual(s.domainSnapshot(),before);
  s.navigate('world');s.selectCountry('SG');assert.equal(s.act('review').ok,true);before=s.domainSnapshot();assert.equal(s.act('accept').ok,false);assert.deepEqual(s.domainSnapshot(),before);
  s.navigate('noc');s.act('accept');s.navigate('hall');before=s.domainSnapshot();assert.equal(s.act('start').ok,false);assert.deepEqual(s.domainSnapshot(),before);
});
test('repair state stays pending under repeated navigation; duplicate action refused',()=>{
  const s=prepare();s.act('start');s.act('advance');s.act('repair');const before=s.domainSnapshot();
  for(let i=0;i<50;i++)for(const route of ['world','noc','campus','hall'])s.navigate(route);
  assert.deepEqual(s.domainSnapshot(),before);assert.equal(s.state.facility.elapsed,0);assert.equal(s.state.request.phase,'repairing');
  assert.equal(s.act('repair').ok,false);assert.deepEqual(s.domainSnapshot(),before);
});
test('review works from my desk without visiting the world map',()=>{const s=createWorldStore();assert.equal(s.state.navigation.route,'noc');assert.equal(s.act('review').ok,true);assert.equal(s.act('accept').ok,true);assert.equal(s.state.request.phase,'accepted');});
test('two fresh sessions produce identical results',()=>{
  function play(){const s=prepare();for(const action of ['start','advance','repair','repair-complete','verify','finish'])s.act(action);s.navigate('noc');s.act('report');return s.domainSnapshot();}
  assert.deepEqual(play(),play());
});
