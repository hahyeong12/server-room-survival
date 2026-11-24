// Result and transition screens (Issue #5). They only read the engine snapshot and offer real next steps:
// a new story / free / tutorial game is a NEW engine save; nothing here forges completion, score or resources.
import {isOpen,STAGE_LABEL,COUNTRY_NAMES} from './game-view.js';

export function createScreens({ $, el, button, store, game, send, newGame, openGame, showMenu, toast, ui, render }) {
  const dlg = $('screen-dialog'), slot = $('screen-slot');
  let seen = { tutorial: false, skipped: false, chapter: false, failed: false, jobs: new Set() }, open = null, history = [];

  function close() { if (dlg.open) dlg.close(); open = null; }
  function nextButtons(kinds) {
    const row = el('div', 'screen-actions');
    const defs = {
      story: ['스토리 도전 시작', async () => { close(); await newGame('story'); }, 'primary'],
      free: ['자유·연습', async () => { close(); await newGame('free'); }, ''],
      tutorial: ['튜토리얼 재연습', async () => { close(); await newGame('tutorial'); }, ''],
      menu: ['메뉴', () => { close(); showMenu(); }, ''],
      stay: ['이 화면 닫기', () => close(), 'link'],
      result: ['결과 탭 보기', () => { close(); store.setNocView('desk'); if (store.state.navigation.route !== 'noc') { store.navigate('noc'); send({ type: 'navigate', route: 'noc', via: 'button' }, { quiet: true }); } ui.tab = 'result'; render(); }, ''],
    };
    for (const k of kinds) { const [label, fn, cls] = defs[k]; row.append(button(label, fn, cls, { 'data-next': k })); }
    return row;
  }
  function show(kind, nodes) {
    open = kind; history.push({ kind, clock: game()?.clock?.label ?? null });
    slot.replaceChildren(...nodes); slot.firstChild?.classList?.add('screen'); slot.dataset.screen = kind;
    if (!dlg.open) dlg.showModal();
    dlg.querySelector('[data-next]')?.focus();
  }
  const rows = pairs => { const d = el('dl', 'ops-readings'); for (const [k, v] of pairs) d.append(el('dt', '', k), el('dd', '', String(v))); return d; };

  function tutorialDone(g) {
    const j = g.journey, res = g.story?.result, box = el('section', 'screen');
    box.append(el('span', 'eyebrow', 'TUTORIAL · 실습 완료'), el('h2', '', '튜토리얼 실습을 모두 마쳤습니다'),
      el('p', 'screen-sub', '아래 내용은 모두 직접 조작한 실제 엔진 결과입니다. 튜토리얼 저장은 본편으로 이어지지 않으므로, 스토리 도전은 새 저장으로 시작합니다.'));
    const ul = el('ul'); for (const t of j.learned) ul.append(el('li', '', t)); box.append(el('strong', '', '익힌 것'), ul);
    if (res) box.append(rows([['결과', res.summary?.map(([k, v]) => `${k} ${v}`).join(' · ') ?? '—'], ['운영 점수', `${res.score}점`], ['기한', res.on_time ? '준수' : '초과'], ['오클릭·재시도', `${j.misclicks}회 (점수와 무관)`]]));
    box.append(nextButtons(['story', 'free', 'tutorial', 'menu']));
    show('tutorial-complete', [box]);
  }
  function tutorialSkipped(g) {
    const box = el('section', 'screen');
    box.append(el('span', 'eyebrow', 'TUTORIAL · 안내 끔'), el('h2', '', '튜토리얼 안내를 껐습니다 · 실습 미완료'),
      el('p', 'screen-sub', `완료한 단계 ${g.journey.doneSteps}/${g.journey.totalSteps}. 건너뛰기는 자원·점수·고객 업무를 바꾸지 않습니다. 이 저장에서 안내 없이 계속하거나 다른 모드로 갈 수 있습니다.`),
      nextButtons(['stay', 'story', 'free', 'tutorial', 'menu']));
    show('tutorial-skipped', [box]);
  }
  function chapterClear(g) {
    const st = g.story, res = st.result, box = el('section', 'screen');
    box.append(el('span', 'eyebrow', `STORY · ${st.chapter.heading}`), el('h2', '', `${st.chapter.label} 클리어 · ${st.chapter.title}`),
      el('p', 'screen-sub', `고객 업무 ${st.jobsDone}/${st.jobsTotal}건을 정상 완료했습니다 (엔진 판정: ${st.chapter.stateLabel}).`));
    if (res) box.append(rows(res.summary ?? []));
    box.append(el('p', 'screen-sub', '다음 장: 제2장 — 한정된 자원. 3D 이식은 다음 단계(Phase 5)에서 제공될 예정이며, 지금 3D 저장에서는 시작할 수 없습니다. 이 장의 기록은 이 저장에 그대로 남습니다.'),
      nextButtons(['menu', 'free', 'tutorial', 'stay']));
    show('chapter-clear', [box]);
  }
  function chapterFailed(g) {
    const st = g.story, box = el('section', 'screen');
    box.append(el('span', 'eyebrow', `STORY · ${st.chapter.heading}`), el('h2', '', '요청이 정상 완료되지 않았습니다'),
      el('p', 'screen-sub', st.chapter.text || '엔진이 이 장의 실패를 확정했습니다.'), el('p', 'screen-sub', '재도전은 새 스토리 저장으로 시작합니다. 기존 저장은 지우지 않습니다.'),
      nextButtons(['story', 'menu', 'stay']));
    show('chapter-failed', [box]);
  }
  function jobDone(g, r) {
    const s = r.summary || {}, box = el('section', 'screen'), next = g.requests.find(x => isOpen(x) && x.id !== r.id);
    box.append(el('span', 'eyebrow', `${g.modeLabel}${g.story ? ` · ${g.story.chapter.label} 업무 ${g.story.jobsDone}/${g.story.jobsTotal}` : ''}`),
      el('h2', '', `요청 #${r.id} ${r.company} · ${s.label || STAGE_LABEL[r.stage]}`),
      rows([['실행', s.mode ? `${s.mode} · GPU ${s.gpu} / 전력 ${s.power}` : '—'], ['완료 / 기한', s.due ? `${s.completed} / ${s.due} · ${s.deadline}` : '—'], ['운영 점수', r.score != null ? `${r.score}점` : '—'], ['자원', r.stage === 'done' ? 'GPU·전력 반환됨' : '—']]));
    if (next) box.append(el('p', 'screen-sub', `다음 업무 도착: ${COUNTRY_NAMES[next.code] || next.country} · ${next.company} (요청 #${next.id}). 내 모니터 요청함에서 확인하세요.`));
    box.append(nextButtons(['result', 'stay']));
    show('job-done', [box]);
  }

  // Decide which screen a new snapshot calls for. Each screen appears once per save (the engine state stays).
  function check(prev, g) {
    if (!g) return;
    const j = g.journey;
    if (j?.kind === 'tutorial') {
      if (j.completed && !seen.tutorial) { seen.tutorial = true; tutorialDone(g); return; }
      if (j.skipped && !j.completed && !seen.skipped) { seen.skipped = true; tutorialSkipped(g); return; }
    }
    if (g.mode === 'story' && g.story) {
      if (g.story.done && !seen.chapter) { seen.chapter = true; chapterClear(g); return; }
      if (g.story.step === 'closed' && !seen.failed) { seen.failed = true; chapterFailed(g); return; }
    }
    if (j?.kind !== 'tutorial') for (const r of g.requests) {
      const before = prev?.requests?.find(x => x.id === r.id);
      if (!isOpen(r) && before && isOpen(before) && !seen.jobs.has(r.id)) { seen.jobs.add(r.id); jobDone(g, r); return; }
    }
  }
  function alarms(prev, g) {
    for (const r of g?.requests ?? []) {
      const before = prev?.requests?.find(x => x.id === r.id);
      if (!before || before.stage === r.stage) continue;
      if (r.stage === 'hw_fault') toast(`경보 · 요청 #${r.id} ${r.hardware}${g.journey?.kind === 'tutorial' ? ' (교육용 훈련 장애)' : ''} · 진행률 정지`, 'hint');
      if (r.stage === 'net_fault') toast(`경보 · 요청 #${r.id} 네트워크 장애 · 필요 ${r.network.needed} / 가용 ${r.network.available}`, 'hint');
    }
    const arrived = (g?.requests ?? []).filter(r => !prev?.requests?.some(x => x.id === r.id));
    if (prev && arrived.length) toast(`새 고객 요청 도착 · ${arrived.map(r => `${COUNTRY_NAMES[r.code] || r.country} #${r.id}`).join(', ')} · 세계지도에 경로 점등`);
  }
  return {
    // A loaded save that is already finished goes straight to its screen, so a finished tutorial is never a dead end.
    reset(g) { close(); seen = { tutorial: false, skipped: false, chapter: false, failed: false, jobs: new Set((g?.requests ?? []).filter(r => !isOpen(r)).map(r => r.id)) }; setTimeout(() => check(null, game()), 0); },
    afterAction(prev, g) { alarms(prev, g); check(prev, g); },
    state: () => ({ open, history: history.map(h => ({ ...h })) }),
  };
}
