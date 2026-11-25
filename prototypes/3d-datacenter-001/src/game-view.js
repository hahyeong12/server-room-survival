// Pure views of the engine snapshot (Issue #5). No DOM, Three.js, storage or rules: the snapshot already holds
// every rule result computed by the Python engine; these helpers only pick and format what the screens show.

export const STAGE_LABEL = Object.freeze({ incoming: '새 요청', running: '작업 진행 중', hw_fault: '서버 장애 · 작업 중단', hw_repair: '서버 복구 중 · 작업 중단',
  migration: '작업 이전 준비 중', net_fault: '네트워크 장애', recovering: '복구 준비 중', done: '처리 완료', failed: '처리 실패', rejected: '요청 종료',
  incident: '사건 대응 중' });
// The 3D scene (desk screens, wall, campus tint, rack pin) still speaks the older phase words. Only server
// (hardware) stages map to 'fault'/'repairing', which tint the server building; network stages never do.
const SCENE_PHASE = Object.freeze({ incoming: 'new', running: 'running', hw_fault: 'fault', hw_repair: 'repairing', migration: 'repairing',
  net_fault: 'degraded', recovering: 'recovering', done: 'completed', failed: 'completed', rejected: 'completed', incident: 'degraded' });
export const MODE_NAMES = Object.freeze({ performance: '고성능 모드', economy: '절약형 모드' });
export const COUNTRY_NAMES = Object.freeze({ SG: '싱가포르', JP: '일본', US: '미국', KR: '대한민국 · 울산' });
export const ENGINE_RACKS = Object.freeze({ A: 'A-01', B: 'B-01', C: 'C-01', D: 'D-01' });
const RACK_SERVER = Object.freeze(Object.fromEntries(Object.entries(ENGINE_RACKS).map(([k, v]) => [v, k])));

export function serverOfRack(rack) { return Object.hasOwn(RACK_SERVER, rack) ? RACK_SERVER[rack] : null; }
export function requestById(game, rid) { return game?.requests?.find(r => r.id === rid) ?? null; }
export function isOpen(r) { return !!r && !['done', 'failed', 'rejected'].includes(r.stage); }
// The request the screens talk about: the engine's selected request, else the newest open one, else the last one.
export function focusRequest(game) {
  if (!game?.requests?.length) return null;
  return requestById(game, game.focus) ?? [...game.requests].reverse().find(isOpen) ?? game.requests.at(-1);
}
export function primaryRack(r) {
  const parts = r?.allocation?.length ? r.allocation : r?.selection?.slices ?? [];
  return parts.length ? [...parts].sort((a, b) => b.gpu - a.gpu)[0].rack : null;
}
export function planRacks(r) { return (r?.allocation?.length ? r.allocation : r?.selection?.slices ?? []).map(p => p.rack); }

export function sceneRequest(game) {
  const r = focusRequest(game);
  if (!r) return { id: '—', customerId: '', rackId: null, phase: 'idle', progress: 0, stage: 'idle' };
  return { id: `REQ-${String(r.id).padStart(3, '0')}`, customerId: r.company, rackId: primaryRack(r), phase: SCENE_PHASE[r.stage] || 'idle',
    progress: Math.round(r.progress), stage: r.stage };
}

// Engine server health -> the 3D rack of that server. Decoration racks stay as they are.
export function syncFacility(facility, game) {
  for (const s of game?.servers ?? []) {
    const a = facility.assets.find(x => x.id === s.rack); if (!a) continue;
    const state = s.state === 'FAULT' ? 'fault' : s.state === 'REPAIRING' ? 'repairing' : 'normal';
    a.state = state; a.fault = state === 'normal' ? null : 'hardware';
    // Phase 7: what is physically visible at the rack during an engine incident (server ledger state keeps precedence):
    // a dead ToR uplink (red network), a cooling zone in warning (amber, warm coolant), a UPS feed on battery (amber power).
    const f = game?.incident?.facilities;
    if (f && state === 'normal') {
      const tor = f.tor?.[s.key], zone = Object.values(f.cooling ?? {}).find(z => z.servers.includes(s.key)), ups = Object.values(f.ups ?? {}).find(u => u.servers.includes(s.key));
      if (tor && Object.values(tor.ports).includes('DOWN') && !tor.rerouted) { a.state = 'fault'; a.fault = 'network'; }
      else if (zone && zone.state !== 'ok') { a.state = 'repairing'; a.fault = 'cooling'; }
      else if (ups && ups.mode === 'battery') { a.state = 'repairing'; a.fault = 'power'; }
    }
  }
  return facility;
}

export function termsLine(r) {
  const p = r?.conditions?.plans?.[r.conditions.requestedMode];
  if (!p) return r ? `${r.company} · 조건 정보 없음 (이전 저장)` : '';
  return `${MODE_NAMES[r.conditions.requestedMode]} · GPU ${p.gpu} · 전력 ${p.power} · 네트워크 ${p.network} · 기한 ${r.terms.due}`;
}
export function allowedLine(r) {
  if (!r?.conditions) return '';
  return r.conditions.type === 'flexible' ? '고객 허용: 고성능·절약형 모두' : '고객 허용: 고성능만 (절약형은 고객 동의 필요)';
}

export function engineTotals(game) {
  const d = game?.datacenter; if (!d) return null;
  const faults = (game.servers ?? []).filter(s => s.state !== 'HEALTHY').length;
  return { gpu: `${d.gpuUsed}/${d.gpuTotal}`, power: `${d.powerUsed}/${d.powerTotal}`, faults, freeGpu: d.healthyFreeGpu, freePower: d.healthyFreePower };
}

// Story / free goal line built from the engine's own objective card (tutorial uses the journey instead).
const STORY_ACTIONS = Object.freeze({
  arrival: ['선배 브리핑', '선배의 브리핑을 읽고 [근무 시작]을 누르세요.'],
  request: ['요청 확인', '내 모니터 요청함에서 새 요청서를 열어 조건을 읽으세요.'],
  preview: ['배정 결정', '내 모니터 [배정 계획]에서 고객 조건에 맞는 배정안을 고르세요.'],
  allocation: ['현장 시작', '서버동 01에서 배정안의 서버 랙을 골라 작업을 시작하세요.'],
  time: ['작업 진행', '위쪽 [⏩] 시간 버튼으로 작업을 끝까지 진행하세요.'],
  complete: ['장 클리어', '이번 장의 업무를 모두 마쳤습니다. 결과를 확인하세요.'],
  closed: ['요청 종료', '요청이 정상 완료되지 않았습니다. 결과와 재도전 방법을 확인하세요.'],
});
export function storyGoal(game) {
  const st = game?.story; if (!st?.card) return null;
  const [title, what] = STORY_ACTIONS[st.step] ?? [st.card.title, st.card.action];
  return { title, what, mentor: st.card.mentor || '', step: st.card.step_no, total: st.card.total, job: st.jobsDone, jobs: st.jobsTotal,
    label: `${st.chapter.label} · 업무 ${Math.min(st.jobsDone + (st.done ? 0 : 1), st.jobsTotal)}/${st.jobsTotal}` };
}
export function freeGoal(game) {
  if (!game?.free) return null;
  const open = (game.requests ?? []).filter(isOpen).length;
  return { title: '자유 운영', what: `열린 요청 ${open}건 · 대기 ${game.free.pending}건 · 다음 접수 예정 ${game.free.nextArrival}`, label: '자유 운영 · 끝없는 근무' };
}

// ---------- Phase 6 (Issue #7): global shifts / global free operations ----------
// Where a request comes from, in words: a catalog city for global requests, the legacy country name otherwise.
export function placeName(r) {
  if (!r) return '';
  return r.site ? `${r.site.city} · ${r.site.countryName}` : (COUNTRY_NAMES[r.code] || r.country);
}
// Phase 7: incident-response shifts reuse the global shift flow (inbox, briefing, shift result) on their own save.
export function isGlobal(game) { return (game?.mode === 'global' || game?.mode === 'incident') && !!game.global; }
// Inbox filter and sort (view only; the engine decides what each request can do).
export const INBOX_FILTERS = Object.freeze({ open: '열린 요청', running: '진행 중', closed: '끝남', all: '전체' });
export const INBOX_SORTS = Object.freeze({ arrival: '도착순', due: '완료 기한순', expires: '최종 접수 임박순' });
export function inboxRows(game, filter = 'open', sort = 'arrival') {
  const rows = [...(game?.requests ?? [])];
  const keep = { open: r => r.stage === 'incoming', running: r => isOpen(r) && r.stage !== 'incoming', closed: r => !isOpen(r), all: () => true }[filter] || (() => true);
  const key = { arrival: r => r.terms.receivedMinute ?? r.id, due: r => r.terms.dueMinute ?? Infinity, expires: r => (r.stage === 'incoming' ? r.terms.expiresMinute : null) ?? Infinity }[sort] || (r => r.id);
  return rows.filter(keep).sort((a, b) => key(a) - key(b) || a.id - b.id);
}
export function inboxCounts(game) {
  const rs = game?.requests ?? [];
  return { open: rs.filter(r => r.stage === 'incoming').length, running: rs.filter(r => isOpen(r) && r.stage !== 'incoming').length,
    closed: rs.filter(r => !isOpen(r)).length, all: rs.length, unread: rs.filter(r => r.unread).length };
}
// Goal line of a global shift, built only from the engine's shift status.
export function globalGoal(game) {
  const g = game?.global; if (!g) return null;
  if (g.kind === 'free') { const open = (game.requests ?? []).filter(isOpen).length;
    return { label: '글로벌 자유 운영 · 진급 기록 없음', title: '세계 각지의 요청을 계속 처리하세요', what: `열린 요청 ${open}건 · 대기 ${g.open}건 · 다음 접수 예정 ${g.next}` }; }
  const goal = `목표: ${g.goal.minSuccess}건 이상 정상 완료${g.goal.maxExpired ? ` · 만료 ${g.goal.maxExpired}건까지` : ' · 만료 없이'}`;
  if (!g.briefed) return { label: `교대 ${g.shift}/${g.shiftCount} · ${g.title}`, title: '선배 브리핑 확인', what: '아래 대화를 읽고 [근무 시작]을 누르세요. 그 전에는 시간이 흐르지 않습니다.', goal };
  if (g.done) return { label: `교대 ${g.shift}/${g.shiftCount} · ${g.title}`, title: g.result.cleared ? '교대 클리어' : '교대 목표 미달성',
    what: `정상 완료 ${g.result.success}/${g.result.total} · 평균 ${g.result.average}점 · 결과 화면을 확인하세요.`, goal };
  return { label: `교대 ${g.shift}/${g.shiftCount} · ${g.title} · ${g.coachingLabel}`, title: `도착 ${g.arrived}/${g.total} · 종료 ${g.closed} · 정상 완료 ${g.success}`,
    what: '요청함에서 도시·업무·원래 조건을 비교하고, 배정 계획 → 서버동 시작 → 시간 진행으로 처리하세요.', goal };
}
