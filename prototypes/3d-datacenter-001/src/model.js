// Independent, memory-only demonstration. No game imports, storage or host controls.
export const STATES = Object.freeze({ normal: '정상 운영', fault: '장애 발생', repairing: '복구 중', awaiting: '사후 확인 대기', verified: '사후 확인 완료' });
export const FAULTS = Object.freeze({ network: '업링크 단절', power: '전력 공급 중단', cooling: '냉각 유량 저하', hardware: '서버 장애 (엔진)' });
export const REPAIR_SECONDS = 6;

export function createFacility() {
  const assets = [];
  for (let row = 0; row < 4; row++) for (let col = 0; col < 6; col++) {
    const id = `${'ABCD'[row]}-${String(col + 1).padStart(2, '0')}`;
    assets.push({ id, kind: 'rack', name: `RACK ${id}`, location: `서버홀 · ${'ABCD'[row]}열 · ${col + 1}번`,
      x: -10.7 + col * 1.72, z: -5.8 + row * 3.25,
      base: { gpu: 58 + ((row * 7 + col * 3) % 30), power: 16.4 + ((row + col) % 5) * 1.1, temp: 21.4 + ((row + col) % 4) * .6, network: 68 + ((col * 7 + row * 3) % 30) },
      state: 'normal', fault: null, repairElapsed: 0, verifiedAt: null });
  }
  for (const a of [
    { id: 'UPS-01', name: 'UPS / PDU 01', kind: 'power', x: -13.7, z: -5.3, location: '전력 설비 · A/B 이중 급전 (모식)' },
    { id: 'CRAC-01', name: 'COOLING 01', kind: 'cooling', x: -13.7, z: -.6, location: '냉각 설비 · 저온 공기 공급 (모식)' },
    { id: 'CRAC-02', name: 'COOLING 02', kind: 'cooling', x: -13.7, z: 4.4, location: '냉각 설비 · 저온 공기 공급 (모식)' },
    { id: 'NET-01', name: 'NETWORK CORE', kind: 'network', x: 1.6, z: -6.6, location: '네트워크 설비 · 가상 코어 스위치' },
  ]) assets.push({ ...a, base: { gpu: 0, power: 8.2, temp: 22.1, network: 96 }, state: 'normal', fault: null, repairElapsed: 0, verifiedAt: null });
  return { assets, selectedId: 'A-01', elapsed: 0, events: [{ time: 0, text: '가상 시설 초기화 완료. 장비를 선택하여 상태를 확인하세요.' }] };
}
export function selected(facility) { return facility.assets.find(a => a.id === facility.selectedId); }
export function selectAsset(facility, id) {
  if (!facility.assets.some(a => a.id === id)) return false;
  facility.selectedId = id;
  return true;
}
function log(f, text) {
  f.events.unshift({ time: f.elapsed, text });
  f.events.length = Math.min(f.events.length, 100);
}
export function injectFault(f, kind) {
  const a = selected(f);
  if (!a || !FAULTS[kind] || !['normal', 'verified'].includes(a.state)) return false;
  a.state = 'fault'; a.fault = kind; a.repairElapsed = 0; a.verifiedAt = null;
  log(f, `${a.id} · ${FAULTS[kind]} 감지. 원인별 지표와 설비 상태를 확인하세요.`);
  return true;
}
export function startRepair(f) {
  const a = selected(f);
  if (a?.state !== 'fault') return false;
  a.state = 'repairing'; a.repairElapsed = 0;
  log(f, `${a.id} · ${FAULTS[a.fault]} 가상 복구 시작 (6초).`);
  return true;
}
export function advance(f, dt) {
  if (!Number.isFinite(dt) || dt < 0) return;
  f.elapsed += dt;
  for (const a of f.assets) if (a.state === 'repairing') {
    a.repairElapsed = Math.min(REPAIR_SECONDS, a.repairElapsed + dt);
    if (a.repairElapsed >= REPAIR_SECONDS) {
      a.state = 'awaiting';
      log(f, `${a.id} · 복구 처리 완료. 센서가 회복되었으며 사후 확인을 기다립니다.`);
    }
  }
}
export function readings(a) {
  const result = { ...a.base, online: a.kind === 'rack' ? 8 : 0 };
  if (['fault', 'repairing'].includes(a.state)) {
    if (a.fault === 'network') { result.network = 0; result.gpu = 8; result.power = 7.2; }
    if (a.fault === 'power') { result.power = 0; result.gpu = 0; result.network = 0; result.online = 0; }
    if (a.fault === 'cooling') { result.temp = 38.6; result.gpu = 24; result.power = 11.2; }
    // Engine server fault mirrored on its rack (world demo only): the server is unusable, GPUs offline.
    if (a.fault === 'hardware') { result.gpu = 0; result.online = 0; result.network = 0; result.power = 3.1; }
  }
  return result;
}
export function verify(f) {
  const a = selected(f);
  if (a?.state !== 'awaiting') return false;
  // Verification is explicit and only allowed after the simulated repair.
  a.state = 'verified'; a.verifiedAt = f.elapsed;
  log(f, `${a.id} · 전력/유입 온도/업링크 사후 확인 완료. 정상 범위 복귀를 확인했습니다.`);
  return true;
}
export function totals(f) {
  const racks = f.assets.filter(a => a.kind === 'rack');
  return { gpu: racks.reduce((s, a) => s + readings(a).online, 0),
    power: f.assets.reduce((s, a) => s + readings(a).power, 0),
    temp: racks.reduce((s, a) => s + readings(a).temp, 0) / racks.length,
    faults: f.assets.filter(a => ['fault', 'repairing'].includes(a.state)).length,
    awaiting: f.assets.filter(a => a.state === 'awaiting').length };
}
