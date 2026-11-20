import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createWorldStore} from '../src/world-store.js';
import {COOLING,OPS_ACTIONS,coolingView,powerView,networkView,hallView,hallInlet} from '../src/facility-ops.js';

const requestOnly=s=>structuredClone({request:s.state.request,facility:s.state.facility});
test('auxiliary cooling ON -> OFF -> ON -> WARN -> ON with consistent label, icon, readings, trend and power load',()=>{
  const s=createWorldStore(),before=requestOnly(s);
  const expect=mode=>{const v=coolingView(s.state);assert.equal(v.mode,mode);assert.equal(v.label,COOLING[mode].label);assert.equal(v.icon,COOLING[mode].icon);assert.equal(v.flow,COOLING[mode].flow);
    assert.equal(v.hallInlet,hallInlet(s.state));assert.equal(v.trend.at(-1),v.hallInlet);assert.equal(v.trend.length,12);assert.equal(powerView(s.state).coolingLoadKW,COOLING[mode].loadKW);assert.equal(hallView(s.state).inlet,v.hallInlet);};
  expect('on');
  for(const [action,mode]of [['cooling-off','off'],['cooling-on','on'],['cooling-warn','warn'],['cooling-reset','on']]){assert.equal(s.ops(action).ok,true);expect(mode);}
  assert.deepEqual(COOLING.on.label,'켜짐');assert.equal(COOLING.off.label,'꺼짐');assert.equal(COOLING.warn.label,'경고');
  assert.ok(coolingView({...s.state,ops:{...s.state.ops,cooling:{mode:'warn',trend:Array(12).fill(2.4)}}}).hallInlet>coolingView(s.state).hallInlet);
  assert.deepEqual(requestOnly(s),before,'cooling never changes the request, racks or time');
  assert.equal(s.state.ops.log.length,4);
});
test('invalid or out-of-state facility actions are refused without changing state',()=>{
  const s=createWorldStore();
  for(const a of ['cooling-on','cooling-reset','__proto__','constructor','toString',undefined,null,42,'drop-table']){const before=s.domainSnapshot();assert.equal(s.ops(a).ok,false);assert.deepEqual(s.domainSnapshot(),before);}
  s.ops('cooling-off');for(const a of ['cooling-off','cooling-warn','cooling-reset']){const before=s.domainSnapshot();assert.equal(s.ops(a).ok,false);assert.deepEqual(s.domainSnapshot(),before);}
  assert.ok(OPS_ACTIONS.length===7&&Object.isFrozen(OPS_ACTIONS)&&Object.isFrozen(COOLING.on));
});
test('network cause lookup follows the shared request state; checks record the phase they saw',()=>{
  const s=createWorldStore();s.ops('network-lookup');assert.equal(s.state.ops.checks.network.title,'활성 네트워크 장애 없음');assert.equal(networkView(s.state).uplink,'정상');
  s.act('review');s.act('accept');s.navigate('hall');s.selectRack('D-06');s.act('start');s.act('advance');
  assert.equal(networkView(s.state).down,true);assert.equal(networkView(s.state).links.find(l=>l.id==='SG').status,'처리량 0');
  s.ops('network-lookup');const c=s.state.ops.checks.network;assert.match(c.title,/D-06 ToR 업링크 단절/);assert.equal(c.phase,'fault');assert.equal(c.target,'hall');
  s.ops('ups-test');s.ops('power-check');assert.equal(s.state.ops.checks.ups.title,'UPS 자가진단 정상');assert.match(s.state.ops.checks.power.detail,/IT 부하/);
  assert.equal(s.state.request.phase,'fault');assert.equal(s.state.request.steps,4);
});
test('facility actions and navigation never advance the request or demo time',()=>{
  const s=createWorldStore(),r=structuredClone(s.state.request),elapsed=s.state.facility.elapsed;
  for(let i=0;i<20;i++){for(const route of ['world','campus','noc','hall'])s.navigate(route);s.ops('network-lookup');s.ops('ups-test');}
  assert.deepEqual(s.state.request,r);assert.equal(s.state.facility.elapsed,elapsed);
});
