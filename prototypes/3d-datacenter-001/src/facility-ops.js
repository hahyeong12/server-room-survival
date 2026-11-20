// Facility operations for the world demo. Pure state + derived views: no DOM, Three.js, storage or game engine.
// Every value here is a fixed educational demo number, not a physical, electrical or thermal model.
import { totals } from './model.js';

function freeze(v) { Object.values(v).forEach(x => { if (x && typeof x === 'object') freeze(x); }); return Object.freeze(v); }

// Auxiliary (educational) cooling loop. The main cooling plant is assumed to keep running in every mode.
export const COOLING = freeze({
  on:   { label: '켜짐', icon: '❄', tone: 'on',   flow: 42, supply: 18.0, ret: 24.5, fan: 62, inletDelta: 0,   loadKW: 18, summary: '보조 냉각 정상 운전 · 냉각수 순환 중' },
  off:  { label: '꺼짐', icon: '❄', tone: 'off',  flow: 0,  supply: null, ret: null, fan: 0,  inletDelta: 0.8, loadKW: 0,  summary: '보조 냉각 대기 · 주 냉각 계통만 운전' },
  warn: { label: '경고', icon: '⚠', tone: 'warn', flow: 12, supply: 23.5, ret: 31.0, fan: 95, inletDelta: 2.4, loadKW: 26, summary: '냉각수 유량 저하 · 공급 온도 상승' },
});
const COOLING_ACTIONS = freeze({
  'cooling-on':    { from: ['off'],  to: 'on',   text: '보조 냉각 계통 켜짐' },
  'cooling-off':   { from: ['on'],   to: 'off',  text: '보조 냉각 계통 꺼짐 (교육용 전환)' },
  'cooling-warn':  { from: ['on'],   to: 'warn', text: '시연 시나리오: 냉각수 유량 저하 경고' },
  'cooling-reset': { from: ['warn'], to: 'on',   text: '유량 점검 완료 · 보조 냉각 정상 재가동' },
});
const CHECK_ACTIONS = freeze({ 'power-check': 'power', 'ups-test': 'ups', 'network-lookup': 'network' });
export const OPS_ACTIONS = freeze([...Object.keys(COOLING_ACTIONS), ...Object.keys(CHECK_ACTIONS)]);
export const VIRTUAL_LINKS = freeze([
  { id: 'SG', name: '싱가포르', latencyMs: 68 }, { id: 'JP', name: '일본', latencyMs: 31 }, { id: 'US', name: '미국 서부', latencyMs: 129 },
]);
const TREND_LENGTH = 12;

export function createOps() {
  return { cooling: { mode: 'on', trend: Array(TREND_LENGTH).fill(0) }, checks: { power: null, ups: null, network: null }, log: [] };
}

export function opsBlocker(state, action) {
  if (typeof action !== 'string' || !OPS_ACTIONS.includes(action)) return '지원하지 않는 시설 조작입니다.';
  const rule = Object.hasOwn(COOLING_ACTIONS, action) ? COOLING_ACTIONS[action] : null;
  if (rule && !rule.from.includes(state.ops.cooling.mode)) return `현재 보조 냉각 상태(${COOLING[state.ops.cooling.mode].label})에서는 할 수 없는 조작입니다.`;
  return '';
}

// Explicit clicks only. Request, rack and time state are never touched here.
export function applyOpsAction(state, action) {
  const blocker = opsBlocker(state, action); if (blocker) return { ok: false, reason: blocker };
  const ops = state.ops, seq = ops.log.length + 1;
  if (Object.hasOwn(COOLING_ACTIONS, action)) {
    const rule = COOLING_ACTIONS[action], from = COOLING[ops.cooling.mode].inletDelta, to = COOLING[rule.to].inletDelta;
    // Three explanatory points from the previous to the new steady value: a picture of the change, not a simulation.
    for (const k of [1 / 3, 2 / 3, 1]) ops.cooling.trend.push(+(from + (to - from) * k).toFixed(2));
    ops.cooling.trend.splice(0, ops.cooling.trend.length - TREND_LENGTH);
    ops.cooling.mode = rule.to; ops.log.push({ seq, action, text: rule.text });
    return { ok: true, reason: '' };
  }
  const key = CHECK_ACTIONS[action], result = key === 'network' ? networkCause(state) : key === 'ups' ? upsView(state).selfTest : powerView(state).check;
  ops.checks[key] = { seq, phase: state.request.phase, ...result };
  ops.log.push({ seq, action, text: result.title });
  return { ok: true, reason: '' };
}

export function hallInlet(state) { return +(totals(state.facility).temp + COOLING[state.ops.cooling.mode].inletDelta).toFixed(1); }

export function coolingView(state) {
  const mode = state.ops.cooling.mode, c = COOLING[mode], base = totals(state.facility).temp;
  return { mode, ...c, hallInlet: hallInlet(state), trend: state.ops.cooling.trend.map(d => +(base + d).toFixed(2)),
    actions: Object.entries(COOLING_ACTIONS).filter(([, r]) => r.from.includes(mode)).map(([id]) => id) };
}

export function powerView(state) {
  const t = totals(state.facility), cooling = COOLING[state.ops.cooling.mode].loadKW, it = +t.power.toFixed(1);
  return { itLoadKW: it, coolingLoadKW: cooling, totalKW: +(it + cooling).toFixed(1), feeds: 'A / B 수전 정상', capacityKW: 600,
    check: { title: '전력 계통 점검 완료', detail: `IT 부하 ${it} kW + 보조 냉각 ${cooling} kW · 가상 수전 용량 600 kW 이내` } };
}

export function upsView() {
  return { battery: 100, mode: '상용 전원 정상 · UPS 대기', runtime: '약 10분 (가상 고정값)',
    selfTest: { title: 'UPS 자가진단 정상', detail: '배터리 100% · 인버터 정상 · 전환 시험은 시연에서 생략' } };
}

function networkCause(state) {
  const r = state.request;
  if (['fault', 'repairing'].includes(r.phase)) return { title: `원인: ${r.rackId} ToR 업링크 단절`, detail: `${r.buildingId} · 랙 ${r.rackId} 상단 스위치의 업링크가 끊겨 싱가포르 회선 처리량이 0입니다. 서버동 01에서 복구를 진행하세요.`, target: 'hall' };
  if (r.phase === 'awaiting') return { title: '업링크 복구 처리됨 · 사후 확인 대기', detail: `랙 ${r.rackId}의 사후 상태 확인이 남아 있습니다.`, target: 'hall' };
  return { title: '활성 네트워크 장애 없음', detail: '국제 가상 회선과 서버동 업링크가 정상입니다.', target: null };
}

export function networkView(state) {
  const p = state.request.phase, down = ['fault', 'repairing'].includes(p);
  return { uplink: down ? '단절' : p === 'awaiting' ? '복구 · 확인 대기' : '정상', down,
    links: VIRTUAL_LINKS.map(l => ({ ...l, status: l.id === 'SG' && down ? '처리량 0' : '정상', active: l.id === 'SG' })) };
}

export function hallView(state) {
  const t = totals(state.facility), rack = state.facility.assets.find(a => a.id === state.request.rackId);
  return { racks: 24, gpuOnline: t.gpu, faults: t.faults, requestRack: rack.id, requestRackState: rack.state, inlet: hallInlet(state) };
}
