// Phase 7: pure helpers of the incident pane. Views only; no rule runs in the browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import { focusIncident, incidentGoal, facilityRows, isIncident, INCIDENT_STAGES } from '../src/incident-pane.js';
import { isGlobal, STAGE_LABEL } from '../src/game-view.js';
import { CAUSE_TEXT } from '../src/network-data.js';

const rec = (id, state, extra = {}) => ({ id, state, stateLabel: state, next: '근거 수집', why: '비교', evidence: [], hypotheses: [], actions: [], ...extra });
const game = recs => ({ mode: 'incident', global: { briefed: true, done: false, coachingLabel: '선배 안내 많음', arrived: 1, total: 3 },
  incident: { code: 'A', practice: null, records: recs, facilities: null } });

test('seven incident stages in the issue order', () => {
  assert.deepEqual(INCIDENT_STAGES, ['경보', '범위 확인', '근거 수집', '원인 판단', '완화·복구', '검증', '보고/종료']);
});
test('incident saves reuse the global shift flow but are told apart', () => {
  assert.equal(isIncident(game([])), true);
  assert.equal(isGlobal(game([])), true);
  assert.equal(isIncident({ mode: 'global', global: {} }), false);
  assert.equal(STAGE_LABEL.incident, '사건 대응 중');
  assert.ok(CAUSE_TEXT.incident.includes('원인 미확인'));
});
test('focus prefers an alert, then an open incident, never an armed one', () => {
  const g = game([rec('INC-A1', 'closed'), rec('INC-A2', 'investigating'), rec('INC-A3', 'alert'), rec('INC-A4', 'armed')]);
  assert.equal(focusIncident(g).id, 'INC-A3');
  assert.equal(focusIncident(g, 'INC-A1').id, 'INC-A1');
  assert.equal(focusIncident(g, 'INC-A4').id, 'INC-A3', 'an armed incident has not happened yet');
});
test('goal line tells the alert without naming a cause', () => {
  const g = game([rec('INC-A1', 'alert', { title: '작업이 멈췄습니다' })]);
  const goal = incidentGoal(g);
  assert.match(goal.title, /경보 · INC-A1/);
  assert.match(goal.what, /원인은 아직 모릅니다/);
  assert.match(incidentGoal({ ...g, global: { ...g.global, briefed: false } }).title, /브리핑/);
});
test('facility rows come from the engine facilities view only', () => {
  const f = { cooling: { Z1: { state: 'warn', servers: ['A', 'B'], pumps: { 'P-1': 'ON', 'P-2': 'WARN', 'P-3': 'OFF' }, flow: 18, inlet: 29.5 } },
    ups: { 'UPS-02': { mode: 'battery', runtime: 12, battery: 70, servers: ['C', 'D'] } },
    tor: { C: { rack: 'C-01', ports: { P1: 'DOWN' }, dual: false } }, edge: { E1: 98, E2: 91, state: 'congested' }, dns: { state: 'ok' },
    storage: [] };
  const g = { ...game([]), incident: { ...game([]).incident, facilities: f } };
  assert.match(facilityRows(g, 'COOLING')[0][1], /P-2 WARN/);
  assert.match(facilityRows(g, 'UPS')[0][1], /배터리 운전 · 남은 보호 시간 약 12분/);
  assert.match(facilityRows(g, 'NETWORK')[0][1], /DOWN/);
  assert.equal(facilityRows({ mode: 'free' }, 'COOLING'), null, 'outside an incident save the demo values stay');
  const away = { ...g, incident: { ...g.incident, facilities: { location: 'noc' } } };
  assert.match(facilityRows(away, 'UPS')[0][1], /건물 안에 들어가면/, 'instruments only on site');
  const fromNetwork = { ...g, incident: { ...g.incident, facilities: { location: 'NETWORK', tor: f.tor, edge: f.edge, dns: f.dns } } };
  assert.match(facilityRows(fromNetwork, 'HALL-01')[0][1], /건물 안에 들어가면/, 'a stale block from another building is not read');
});
