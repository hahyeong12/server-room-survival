// Goal + next-action guide (Issue #3). Pure: reads the shared demo state and answers
// "which single thing should the player do now?" It never changes state itself.
import { nextDemoStep, demoBlocker } from './demo-actions.js';

function freeze(v) { Object.values(v).forEach(x => { if (x && typeof x === 'object') freeze(x); }); return Object.freeze(v); }

export const GOALS = freeze([
  { id: 'country',  title: '요청 국가 확인',       phases: ['new'] },
  { id: 'accept',   title: '요청 접수',            phases: ['reviewed'] },
  { id: 'rack',     title: '랙 찾기 · 작업 시작',  phases: ['accepted'] },
  { id: 'incident', title: '작업 진행 · 장애 확인', phases: ['running', 'fault'] },
  { id: 'recover',  title: '복구 · 결과 확인',     phases: ['repairing', 'awaiting', 'recovered', 'completed'] },
]);

// One short sentence per situation. Longer explanations live in the collapsible detail.
const HINTS = freeze({
  'review@world': '금색 싱가포르에서 온 요청입니다. 경로를 보고 요청을 확인하세요.',
  'review@away': '새 고객 요청이 왔어요. 어느 나라인지 세계지도에서 확인하세요.',
  accept: '조건(GPU 8 · 20 kW · 40 Gbps)과 배정 랙 D-06을 보고 접수하세요.',
  start: '랙 D-06에서 작업을 시작하세요.',
  advance: '작업을 한 단계 진행해 보세요.',
  repair: '업링크가 끊겼어요. 복구를 시작하세요.',
  'repair-complete': '복구 작업을 마무리하세요.',
  verify: '복구 후 상태가 정상인지 확인하세요.',
  finish: '정상 재개를 확인했으니 작업을 완료하세요.',
  report: '고객에게 보낼 처리 결과를 확인하세요.',
});
const FEEDBACK = freeze({
  review: '요청 조건을 확인했습니다. 이제 내 자리에서 접수하세요.',
  accept: '접수 완료 · 서버동 01의 랙 D-06에 배정했습니다.',
  start: 'D-06에서 작업이 시작됐습니다 · 진행률 25%',
  advance: '장애 발생! D-06 업링크가 끊겨 처리량이 0이 됐습니다.',
  repair: '복구 시작 · 상태가 "복구 중"으로 바뀌었습니다.',
  'repair-complete': '복구 처리 완료 · 사후 확인이 남았습니다.',
  verify: '사후 확인 완료 · 작업이 정상 재개됐습니다 (60%).',
  finish: '작업 완료 · 진행률 100%. 내 자리에서 결과를 확인하세요.',
  report: '첫 업무 완료! 결과 카드를 확인하세요.',
});

export function goalOf(phase) {
  if (phase === 'reported') return { index: GOALS.length, total: GOALS.length, title: '첫 업무 완료', done: true };
  const index = GOALS.findIndex(g => g.phases.includes(phase));
  return { index: index + 1, total: GOALS.length, title: GOALS[index]?.title ?? '', done: false };
}

const NAV_LABEL = { noc: '내 자리로 이동', hall: '서버동 01로 이동', world: '세계지도로 이동' };
export function nextAction(state) {
  const step = nextDemoStep(state), nav = state.navigation, route = nav.route, rack = state.request.rackId;
  if (!step) return { kind: 'done', label: '결과 다시 보기', target: 'noc', hint: '첫 업무를 끝냈습니다. 시설을 자유롭게 둘러보세요.' };
  if (step.id === 'review') {
    if (route === 'world') {
      if (nav.country !== 'SG') return { kind: 'select-country', target: 'SG', label: '싱가포르 선택', hint: '이번 요청은 싱가포르에서 왔어요. 금색 거점을 고르세요.' };
      return { kind: 'act', id: 'review', label: '싱가포르 요청 확인', hint: HINTS['review@world'] };
    }
    const alt = route === 'noc' ? { kind: 'act', id: 'review', label: '지도 없이 바로 확인' } : null;
    return { kind: 'navigate', target: 'world', label: '요청 국가 보기', hint: HINTS['review@away'], alt };
  }
  const routes = step.routes || [step.route];
  if (!routes.includes(route)) return { kind: 'navigate', target: step.route, label: NAV_LABEL[step.route], hint: step.route === 'hall' ? '작업은 서버동 01의 랙에서 합니다. 연결 통로로 이동하세요.' : '이 일은 관제동 내 자리에서 합니다.' };
  if (step.route === 'hall' && state.facility.selectedId !== rack) return { kind: 'select-rack', target: rack, label: `랙 ${rack} 찾기`, hint: `금색 표시가 붙은 랙 ${rack}을 고르세요.` };
  return { kind: 'act', id: step.id, label: step.label, hint: HINTS[step.id], disabled: !!demoBlocker(state, step.id) };
}

export function feedbackFor(action) { return Object.hasOwn(FEEDBACK, action) ? FEEDBACK[action] : ''; }

// Gentle, specific hints for clicks that do not move the current goal forward. Never auto-completes.
export function misclickHint(state, kind, id) {
  const step = nextDemoStep(state); if (!step) return '';
  if (kind === 'rack' && step.route === 'hall' && id !== state.request.rackId) return `${id}은 이번 요청과 관계없는 랙이에요. 찾을 랙은 금색 표시의 ${state.request.rackId}입니다.`;
  if (kind === 'country' && step.id === 'review' && id !== 'SG') return '이 나라에는 지금 요청이 없어요. 금색으로 깜빡이는 싱가포르를 보세요.';
  return '';
}
