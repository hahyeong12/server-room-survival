import test from 'node:test';
import assert from 'node:assert/strict';
import {buildCommand,interpretationChoices} from '../src/linux-pane.js';
import {isIncident} from '../src/incident-pane.js';
import {isGlobal} from '../src/game-view.js';

test('assembly uses the actual selected options and target; no answer is auto-filled',()=>{
  const spec={syntax:'journalctl -u $unit -n $count'};
  assert.equal(buildCommand(spec,{1:'-u',2:'worker.service',3:'-n',4:'3'}),'journalctl -u worker.service -n 3');
  assert.equal(buildCommand({syntax:'df -h'},{1:'-i'}),'df -i');
  assert.equal(buildCommand({syntax:'ping -c $count $host'}),'ping');
});
test('interpretation options contain neutral IDs and no client-side answer key',()=>{
  const o={seq:12,choices:[{id:'a',text:'statement'},{id:'b',text:'inference'}]};
  assert.deepEqual(interpretationChoices(o),o.choices);
  assert.deepEqual(interpretationChoices({}),[]);
});
test('Linux sessions use existing incident and world views; old modes keep their identity',()=>{
  assert.equal(isIncident({mode:'linux',incident:{}}),true);
  assert.equal(isGlobal({mode:'linux',global:{}}),true);
  assert.equal(isIncident({mode:'story',incident:{}}),false);
  assert.equal(isGlobal({mode:'global',global:{}}),true);
});
