import test from 'node:test';
import assert from 'node:assert/strict';
import {buildCommand,interpretationChoices,toggleExpanded,choiceLine} from '../src/linux-pane.js';
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
test('expanded terminal is a view preference outside the terminal draft/history state',()=>{
  const ui={linux:{draft:'ping -c 3 10.20.0.15',history:['df -h']}};
  assert.equal(toggleExpanded(ui),true);assert.equal(ui.linuxExpanded,true);
  assert.equal(toggleExpanded(ui),false);assert.equal(toggleExpanded(ui,true),true);
  assert.deepEqual(ui.linux,{draft:'ping -c 3 10.20.0.15',history:['df -h']});
});
test('choice level only swaps the chosen target or port into the catalog example',()=>{
  assert.equal(choiceLine({syntax:'ping -c $count $host',example:'ping -c 3 10.20.0.15'},{host:'10.20.12.15'}),'ping -c 3 10.20.12.15');
  assert.equal(choiceLine({syntax:'ethtool $iface',example:'ethtool swp1'},{iface:'swp2'}),'ethtool swp2');
  assert.equal(choiceLine({syntax:'df -h',example:'df -h'}),'df -h');
  assert.equal(choiceLine({syntax:'ping -c $count $host',example:'ping -c 3 10.20.0.15'}),'ping -c 3 10.20.0.15');
});
