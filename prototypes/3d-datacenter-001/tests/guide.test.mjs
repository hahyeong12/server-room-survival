import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createWorldStore,breadcrumbs,ROOMS} from '../src/world-store.js';
import {GOALS,goalOf,nextAction,feedbackFor,misclickHint} from '../src/guide.js';

// Follow only the guide's single next action: the whole SG demo must finish in 5 goals.
function perform(s,a){
  if(a.kind==='navigate')return s.navigate(a.target);
  if(a.kind==='select-country')return s.selectCountry(a.target);
  if(a.kind==='select-rack')return s.selectRack(a.target);
  if(a.kind==='act')return s.act(a.id).ok;
  throw new Error(a.kind);
}
test('following only the single next action completes the demo; goal index never goes back',()=>{
  const s=createWorldStore();let last=1,clicks=0;const seenGoals=new Set();
  while(nextAction(s.state).kind!=='done'){const a=nextAction(s.state);assert.ok(a.label&&a.hint,'label + one hint');assert.equal(a.disabled??false,false);
    const g=goalOf(s.state.request.phase);assert.ok(g.index>=last);last=g.index;seenGoals.add(g.index);assert.ok(perform(s,a));clicks++;assert.ok(clicks<40);}
  assert.equal(s.state.request.phase,'reported');assert.deepEqual([...seenGoals],[1,2,3,4,5]);assert.equal(goalOf('reported').done,true);
  assert.ok(clicks<=16,`${clicks} clicks`);
});
test('goal 1 sends the player to the requesting country; desk keeps a direct alternative',()=>{
  const s=createWorldStore();let a=nextAction(s.state);assert.equal(a.kind,'navigate');assert.equal(a.target,'world');assert.equal(a.alt.id,'review');
  s.navigate('world');s.selectCountry('JP');a=nextAction(s.state);assert.equal(a.kind,'select-country');assert.match(misclickHint(s.state,'country','JP'),/싱가포르/);
  s.selectCountry('SG');assert.equal(nextAction(s.state).id,'review');
});
test('in the server building the guide asks for the target rack before any action; wrong rack gives a hint',()=>{
  const s=createWorldStore();s.act('review');s.act('accept');s.navigate('hall');s.selectRack('A-01');
  assert.deepEqual([nextAction(s.state).kind,nextAction(s.state).target],['select-rack','D-06']);assert.match(misclickHint(s.state,'rack','A-01'),/D-06/);
  s.selectRack('D-06');assert.equal(nextAction(s.state).id,'start');assert.equal(misclickHint(s.state,'rack','D-06'),'');
});
test('guide is read-only and every demo action has feedback',()=>{
  const s=createWorldStore(),before=JSON.stringify(s.state);for(let i=0;i<5;i++){nextAction(s.state);goalOf(s.state.request.phase);misclickHint(s.state,'rack','A-02');}
  assert.equal(JSON.stringify(s.state),before);assert.equal(GOALS.length,5);assert.ok(Object.isFrozen(GOALS));
  for(const a of ['review','accept','start','advance','repair','repair-complete','verify','finish','report'])assert.ok(feedbackFor(a).length>5,a);assert.equal(feedbackFor('__proto__'),'');
});
test('double-click entry: control -> my desk, server -> racks, other facilities -> their interior; invalid ids rejected',()=>{
  const s=createWorldStore(),before=s.domainSnapshot();
  s.state.navigation.nocView='overview';assert.equal(s.enterFacility('NOC'),true);assert.deepEqual([s.state.navigation.route,s.state.navigation.nocView],['noc','desk']);
  assert.equal(s.enterFacility('HALL-01'),true);assert.equal(s.state.navigation.route,'hall');
  for(const id of ROOMS){assert.equal(s.enterFacility(id),true);assert.equal(s.state.navigation.route,'room');assert.equal(s.state.navigation.room,id);}
  assert.deepEqual(breadcrumbs('room').map(x=>x.id),['world','campus','room']);
  for(const id of ['x','__proto__',null])assert.equal(s.enterFacility(id),false);
  assert.deepEqual(s.domainSnapshot(),before,'entering buildings never changes the demo');
});
