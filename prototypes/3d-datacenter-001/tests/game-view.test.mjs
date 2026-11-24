import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {focusRequest,sceneRequest,syncFacility,serverOfRack,primaryRack,termsLine,engineTotals,storyGoal,freeGoal,STAGE_LABEL} from '../src/game-view.js';
import {createFacility,readings} from '../src/model.js';
import {activePaths,focusPath} from '../src/network-data.js';
import {createWorldStore} from '../src/world-store.js';

// Real snapshots produced by the unmodified Python engine (python -m engine.tests.make_fixtures).
const S=JSON.parse(readFileSync(new URL('./fixtures/snapshots.json',import.meta.url),'utf8'));

test('fixtures come from the Python engine contract (api v1, GameSession)',()=>{
  for(const [k,s]of Object.entries(S)){assert.equal(s.api,1,k);assert.equal(s.engine,'python:session.GameSession');assert.ok(Array.isArray(s.requests)&&Array.isArray(s.servers),k);}
  assert.deepEqual(S.tutorial_new.servers.map(s=>[s.key,s.rack,s.gpu,s.power]),[['A','A-01',4,4],['B','B-01',3,2],['C','C-01',2,3],['D','D-01',1,1]]);
});
test('scene request follows the engine stage; the pin rack comes from the chosen or running allocation',()=>{
  assert.deepEqual(sceneRequest(null),{id:'—',customerId:'',rackId:null,phase:'idle',progress:0,stage:'idle'});
  assert.equal(sceneRequest(S.tutorial_new).rackId,null,'no plan chosen yet: nothing to point at');
  assert.equal(sceneRequest(S.tutorial_selected).rackId,'A-01');assert.equal(sceneRequest(S.tutorial_selected).phase,'new');
  assert.equal(sceneRequest(S.tutorial_running).phase,'running');
  assert.equal(sceneRequest(S.tutorial_hw_fault).phase,'fault');assert.equal(sceneRequest(S.tutorial_hw_repair).phase,'repairing');
  assert.equal(sceneRequest(S.tutorial_done).phase,'completed');assert.equal(sceneRequest(S.tutorial_done).progress,100);
  assert.equal(primaryRack(focusRequest(S.tutorial_running)),'A-01');
});
test('engine server health is mirrored on racks A-01..D-01 only; decoration racks never change',()=>{
  const ENGINE=['A-01','B-01','C-01','D-01'],f=createFacility(),decor=structuredClone(f.assets.filter(a=>!ENGINE.includes(a.id)));
  syncFacility(f,S.tutorial_hw_fault);const a=f.assets.find(x=>x.id==='A-01');assert.equal(a.state,'fault');assert.equal(a.fault,'hardware');assert.equal(readings(a).online,0);
  syncFacility(f,S.tutorial_hw_repair);assert.equal(a.state,'repairing');
  syncFacility(f,S.tutorial_done);assert.equal(a.state,'normal');assert.equal(a.fault,null);
  assert.deepEqual(f.assets.filter(x=>!ENGINE.includes(x.id)),decor);
  assert.equal(serverOfRack('C-01'),'C');assert.equal(serverOfRack('C-02'),null);assert.equal(serverOfRack('__proto__'),null);
});
test('world paths: lit only for open engine requests; a finished job turns its path off',()=>{
  assert.deepEqual(activePaths({game:S.tutorial_new}).map(p=>[p.code,p.tone]),[['SG','incoming']]);
  assert.equal(focusPath({game:S.tutorial_hw_fault}).aidc,'fault');assert.equal(focusPath({game:S.tutorial_hw_fault}).segments.sea,'ok');
  assert.deepEqual(activePaths({game:S.tutorial_done}),[]);
});
test('panel text uses the engine terms and totals (GPU 10 / power 10), not decoration numbers',()=>{
  assert.match(termsLine(focusRequest(S.tutorial_new)),/고성능 모드 · GPU 7 · 전력 7 · 네트워크 5 · 기한 D1 12:00/);
  assert.equal(engineTotals(S.tutorial_running).gpu,'7/10');assert.equal(engineTotals(S.tutorial_done).gpu,'0/10');
  assert.equal(storyGoal(S.story_new).title,'선배 브리핑');assert.match(storyGoal(S.story_new).label,/제1장 · 업무 1\/3/);
  assert.equal(freeGoal(S.free_new).title,'자유 운영');assert.equal(freeGoal(S.story_new),null);
  for(const r of Object.values(S).flatMap(s=>s.requests))assert.ok(STAGE_LABEL[r.stage],r.stage);
});
test('store keeps a private copy of the snapshot; view selection never changes game data',()=>{
  const store=createWorldStore();assert.equal(store.state.navigation.country,null,'no country pre-selected');
  const snap=structuredClone(S.tutorial_selected);store.setGame(snap);snap.requests[0].progress=99;assert.equal(store.state.game.requests[0].progress,0);
  const before=JSON.stringify(store.state.game);store.selectCountry('JP');store.selectRack('B-04');store.navigate('world');store.setNocView('overview');
  assert.equal(JSON.stringify(store.state.game),before);
});
test('a network incident never tints the server building as a hardware fault (review finding)',()=>{
  const g=stage=>({focus:1,requests:[{id:1,stage,progress:30,company:'x',allocation:[],selection:null}]});
  assert.equal(sceneRequest(g('net_fault')).phase,'degraded');assert.equal(sceneRequest(g('recovering')).phase,'recovering');
  assert.equal(sceneRequest(g('hw_fault')).phase,'fault');assert.equal(sceneRequest(g('hw_repair')).phase,'repairing');assert.equal(sceneRequest(g('migration')).phase,'repairing');
});
