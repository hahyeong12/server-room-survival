// Result and transition screens (Issue #5). They only read the engine snapshot and offer real next steps:
// a new story / free / tutorial game is a NEW engine save; nothing here forges completion, score or resources.
import {isOpen,STAGE_LABEL,COUNTRY_NAMES,placeName,isGlobal} from './game-view.js';
import {resultRows,resultNotes,missionOf,cardRows} from './campaign-view.js';

export function createScreens({ $, el, button, store, game, send, newGame, openGame, retryChapter, showMenu, toast, ui, render }) {
  const dlg = $('screen-dialog'), slot = $('screen-slot');
  let seen = { tutorial: false, skipped: false, chapters: new Set(), failed: false, jobs: new Set() }, open = null, history = [], onClose = null;
  // Closing a senior's card (button or Esc) records that it was shown, so the engine shows each card once.
  dlg.addEventListener('close', () => { const f = onClose; onClose = null; open = null; f?.(); });

  function close() { if (dlg.open) dlg.close(); else { const f = onClose; onClose = null; f?.(); } open = null; }
  function nextButtons(kinds) {
    const row = el('div', 'screen-actions');
    const defs = {
      story: ['스토리 도전 시작', async () => { close(); await newGame('story'); }, 'primary'],
      free: ['자유·연습', async () => { close(); await newGame('free'); }, ''],
      tutorial: ['튜토리얼 재연습', async () => { close(); await newGame('tutorial'); }, ''],
      menu: ['메뉴', () => { close(); showMenu(); }, ''],
      stay: ['이 화면 닫기', () => close(), 'link'],
      result: ['결과 탭 보기', () => { close(); store.setNocView('desk'); if (store.state.navigation.route !== 'noc') { store.navigate('noc'); send({ type: 'navigate', route: 'noc', via: 'button' }, { quiet: true }); } ui.tab = 'result'; render(); }, ''],
      // Phase 5: the next chapter starts in THIS save through the engine (start_chapter*); a retry is a NEW slot.
      'next-chapter': [`${game()?.story?.next?.heading ?? '다음 장'} 시작`, async () => { const nx = game()?.story?.next; close(); if (nx) await send({ type: 'start_next_chapter', chapter: String(nx.key) }); }, 'primary'],
      retry: [`${game()?.story?.chapter?.label ?? '현재 장'} 재도전 (새 슬롯)`, async () => { close(); await retryChapter(); }, ''],
      practice: ['같은 장 다시 연습 (새 연습 저장)', async () => { close(); await retryChapter(); }, ''],
      // Phase 6: the next shift starts in THIS save (engine start_next_shift); a shift retry is a NEW save.
      'next-shift': [`교대 ${game()?.global?.next ?? ''} 시작`, async () => { const nx = game()?.global?.next, ack = onClose; onClose = null; close(); await ack?.(); if (nx) await send({ type: 'start_next_shift', shift: String(nx) }); }, 'primary'],
      // Record that the result was seen in THIS save first, then open the new slot (as a chapter retry does).
      'retry-shift': [`교대 ${game()?.global?.shift ?? ''} 재도전 (새 슬롯)`, async () => { const ack = onClose; onClose = null; close(); await ack?.(); await retryChapter(); }, ''],
      'global-free': ['글로벌 자유 운영', async () => { close(); await newGame('global_free'); }, ''],
      // Phase 7: incident-response shifts (A -> B -> C) in the same incident save; a retry is a NEW incident save.
      'next-incident': [`근무 ${({ 2: 'B', 3: 'C' })[game()?.global?.next] ?? ''} 시작`, async () => { const nx = game()?.global?.next, ack = onClose; onClose = null; close(); await ack?.(); if (nx) await send({ type: 'start_next_shift', shift: String(nx) }); }, 'primary'],
      'next-linux': [`Linux 근무 ${game()?.global?.next ?? ''} 시작`, async () => {const nx=game()?.global?.next,ack=onClose;onClose=null;close();await ack?.();if(nx)await send({type:'start_next_shift',shift:String(nx)});}, 'primary'],
      'retry-incident': [`${game()?.incident?.practice || game()?.linux?.practice ? '같은 사건 다시 연습' : `근무 ${game()?.incident?.code ?? ''} 재도전`} (새 슬롯)`, async () => { const ack = onClose; onClose = null; close(); await ack?.(); await retryChapter(); }, ''],
    };
    for (const k of kinds) { const [label, fn, cls] = defs[k]; row.append(button(label, fn, cls, { 'data-next': k })); }
    return row;
  }
  function show(kind, nodes, closeHook = null) {
    open = kind; onClose = closeHook; history.push({ kind, clock: game()?.clock?.label ?? null });
    slot.replaceChildren(...nodes); slot.firstChild?.classList?.add('screen'); slot.dataset.screen = kind;
    if (!dlg.open) dlg.showModal();
    render();   // the senior's talk box waits under a result screen
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
  // Which buttons a finished chapter offers. They mean exactly what they do in the engine: [다음 장] only when the
  // engine unlock allows it, [재도전] only when a chapter-start checkpoint exists (or a practice / tutorial copy).
  function chapterActions(st, cleared) {
    const kinds = [];
    if (cleared && st.next?.available) kinds.push('next-chapter');
    if (st.retry?.available) kinds.push(st.retry.kind === 'practice' ? 'practice' : 'retry');
    kinds.push('menu', 'free', 'stay');
    return nextButtons(kinds);
  }
  function resultBlock(box, st) {
    const list = resultRows(st); if (list.length) box.append(rows(list));
    const notes = resultNotes(st); if (notes.length) { const ul = el('ul', 'screen-notes'); for (const t of notes) ul.append(el('li', '', t)); box.append(ul); }
  }
  function chapterClear(g) {
    const st = g.story, box = el('section', 'screen');
    box.append(el('span', 'eyebrow', `STORY · ${st.chapter.heading}`), el('h2', '', `${st.chapter.label} 클리어 · ${st.chapter.title}`),
      el('p', 'screen-sub', st.chapterKey === 1 ? `고객 업무 ${st.jobsDone}/${st.jobsTotal}건을 정상 완료했습니다 (엔진 판정: ${st.chapter.stateLabel}).`
        : `엔진 판정: ${st.chapter.stateLabel} · ${st.chapter.text}`));
    resultBlock(box, st);
    if (st.practice) box.append(el('p', 'screen-sub', '연습 저장입니다. 진급 기록에는 남지 않습니다.'));
    else if (st.next) box.append(el('p', 'screen-sub', st.next.available ? `다음 장: ${st.next.heading} — ${st.next.intro}` : `다음 장은 아직 열리지 않습니다: ${st.next.reason}`));
    box.append(chapterActions(st, true));
    show('chapter-clear', [box]);
  }
  function chapterFailed(g) {
    const st = g.story, box = el('section', 'screen');
    box.append(el('span', 'eyebrow', `STORY · ${st.chapter.heading}`), el('h2', '', st.chapterKey === 1 ? '요청이 정상 완료되지 않았습니다' : `${st.chapter.label} 미션 실패`),
      el('p', 'screen-sub', st.chapter.text || '엔진이 이 장의 실패를 확정했습니다.'));
    resultBlock(box, st);
    box.append(el('p', 'screen-sub', '재도전은 이 장의 시작 지점을 새 슬롯으로 복사해 시작합니다. 지금 저장과 이전 장 기록은 그대로 남습니다.'),
      chapterActions(st, false));
    show('chapter-failed', [box]);
  }
  function graduation(g) {
    const st = g.story, gr = st.graduation, box = el('section', 'screen graduation');
    box.append(el('span', 'eyebrow', 'CAMPAIGN · 제1~5장 클리어'), el('h2', '', gr.title), el('p', 'screen-sub', `${gr.from} → ${gr.title} (${gr.note})`));
    box.append(rows(gr.rows.map(r => [r.heading, r.line])));
    const ul = el('ul', 'screen-notes'); for (const t of gr.learned) ul.append(el('li', '', t)); box.append(el('strong', '', '스스로 해낸 것'), ul);
    resultBlock(box, st);
    box.append(nextButtons(['free', 'menu', 'tutorial', 'stay']));
    show('graduation', [box]);
  }
  // Retry from a senior card: record the card in THIS save first, then open the new slot. The finished-chapter
  // screen of the old save is not shown in between.
  async function retryAfter(ack) {
    const key = String(game()?.story?.chapterKey); seen.chapters.add(key);
    onClose = null; if (dlg.open) dlg.close(); open = null;
    await ack(); await retryChapter();
  }
  // Mid-chapter senior feedback the engine wants shown once: chapter 2 confirmed failure, chapter 3/4 result cards.
  function chapter2Failure(g) {
    const c2 = g.story.chapter2, box = el('section', 'screen');
    box.append(el('span', 'eyebrow', `${g.story.chapter.heading} · 미션 실패 확정`), el('h2', '', '선배의 피드백'));
    for (const [, speaker, text] of c2.failurePages) box.append(el('strong', '', speaker), el('p', 'screen-sub', text));
    const ack = () => send({ type: 'ack_feedback', kind: 'chapter2' }, { quiet: true });
    const row = el('div', 'screen-actions');
    row.append(button('현재 슬롯에서 계속 진행', () => close(), 'primary', { 'data-next': 'continue' }));
    if (g.story.retry?.available) row.append(button(`${g.story.chapter.label} 재도전 (새 슬롯)`, () => retryAfter(ack), '', { 'data-next': 'retry' }));
    box.append(row);
    show('chapter2-failure', [box], ack);
  }
  function incidentCard(g, kind) {
    const view = g.story[kind], pending = view.pending, card = view.cards[String(pending.rid)], box = el('section', 'screen');
    if (!card) { send({ type: 'ack_feedback', kind, key: pending.key }, { quiet: true }); return; }
    box.append(el('span', 'eyebrow', `${g.story.chapter.heading} · 요청 #${pending.rid}`), el('h2', '', card.title));
    box.dataset.tone = card.tone || '';
    box.append(rows(cardRows(card)));
    if (card.mentor) box.append(el('p', 'screen-sub', `선배: ${card.mentor}`));
    for (const [, speaker, text] of pending.pages || []) box.append(el('p', 'screen-sub', `${speaker}: ${text}`));
    const ack = () => send({ type: 'ack_feedback', kind, key: pending.key }, { quiet: true });
    const row = el('div', 'screen-actions');
    row.append(button('업무로 돌아가기', () => close(), 'primary', { 'data-next': 'continue' }));
    if (card.can_retry && g.story.retry?.available) row.append(button(`${g.story.chapter.label} 재도전 (새 슬롯)`, () => retryAfter(ack), '', { 'data-next': 'retry' }));
    box.append(row);
    show(`${kind}-card`, [box], ack);
  }
  function jobDone(g, r) {
    const s = r.summary || {}, box = el('section', 'screen'), next = g.requests.find(x => isOpen(x) && x.id !== r.id);
    box.append(el('span', 'eyebrow', `${g.modeLabel}${g.story ? ` · ${g.story.chapter.label} 업무 ${g.story.jobsDone}/${g.story.jobsTotal}` : ''}`),
      el('h2', '', `요청 #${r.id} ${r.company} · ${s.label || STAGE_LABEL[r.stage]}`),
      rows([['실행', s.mode ? `${s.mode} · GPU ${s.gpu} / 전력 ${s.power}` : '—'], ['완료 / 기한', s.due ? `${s.completed} / ${s.due} · ${s.deadline}` : '—'], ['운영 점수', r.score != null ? `${r.score}점` : '—'], ['자원', r.stage === 'done' ? 'GPU·전력 반환됨' : '—']]));
    if (next) box.append(el('p', 'screen-sub', `다음 업무: ${placeName(next)} · ${next.company} (요청 #${next.id}). 내 모니터 요청함에서 확인하세요.`));
    box.append(nextButtons(['result', 'stay']));
    show('job-done', [box]);
  }

  // Phase 7: a finished incident-response shift. Every row is the engine's incident record (evidence, hypotheses,
  // actions, recovery, report) and the post-mortem the content gives for that cause.
  function incidentShiftDone(g) {
    const gl = g.global, res = gl.result, inc = g.incident, key = `shift${gl.shift}`, box = el('section', 'screen shift-result incident-result');
    const final = res.cleared && !gl.next && !inc.practice && !g.linux?.practice;
    box.append(el('span', 'eyebrow', inc.practice ? 'INCIDENT PRACTICE · 진급 기록 없음' : `INCIDENT SHIFT ${inc.code} · ${gl.shift}/${inc.shiftCount} · ${gl.coachingLabel}`),
      el('h2', '', final ? (g.linux ? '독립 관제 엔지니어 · Linux 연수 수료' : '장애 대응 근무 A·B·C 모두 완료') : `${res.title} · ${res.cleared ? '목표 달성' : '목표 미달성'}`),
      el('p', 'screen-sub', `엔진 판정: 사건 해결 ${res.resolved}/${res.incidents.length}(목표 ${res.goal.minResolved}) · 정상 완료 ${res.success}/${res.total}${res.goal.notifyBeforeRecovery ? ' · 복구 전 고객 안내 필요' : ''} · ${res.started} → ${res.finished}`));
    const table = el('table', 'terms-table shift-table'); table.innerHTML = '<thead><tr><th>사건</th><th>원인(확정)</th><th>고객 · 도시</th><th>결과</th><th>근거 · 반박 · 개선 없음 · 허용 안 됨</th><th>해결 · 완화</th><th>영향</th></tr></thead>';
    const tb = el('tbody');
    for (const r of res.incidents) { const tr = el('tr'); tr.dataset.incident = r.id; tr.dataset.outcome = r.outcome;
      tr.append(el('td', '', r.id), el('td', '', r.label), el('td', '', `${r.client} · ${r.city} (#${r.rid})`), el('td', r.outcome === 'resolved' ? 'ok' : 'warn', ({ resolved: '해결', failed: '실패', void: '사건 없음' })[r.outcome] ?? '진행 중'),
        el('td', '', `관측 ${r.evidence}건${r.wrongHypotheses.length ? ` · 반박 ${r.wrongHypotheses.join(', ')}` : ''}${r.noEffect.length ? ` · 개선 없음 ${r.noEffect.join(', ')}` : ''}${r.refused.length ? ` · 허용 안 됨 ${r.refused.join(', ')}` : ''}`),
        el('td', '', [r.fix, ...r.mitigations].filter(Boolean).join(' + ') || '—'), el('td', '', `정지 ${r.downtime}분 · 지연 ${r.slowMinutes}분${r.notices ? ` · 안내 ${r.notices}회` : ''}`)); tb.append(tr); }
    table.append(tb); box.append(table);
    const ul = el('ul', 'screen-notes'); for (const t of res.feedback) ul.append(el('li', '', t));
    box.append(el('strong', '', gl.coaching === 'none' ? '스스로 돌아보기' : '선배의 짧은 피드백'), ul);
    if(res.linux){const l=res.linux;box.append(el('p','linux-promotion',`교육용 승급: ${l.rank} · 명령 ${l.commands}종 / 관측 ${l.observations}회 · 올바른 해석 ${l.interpreted}회 / 추측 수정 ${l.misinterpretations}회 · 요청한 도움 ${l.help}회${l.practice?' · 진급 기록 없음':''}`));}
    const pm = el('ul', 'screen-notes postmortem'); for (const r of res.incidents) pm.append(el('li', '', `${r.id} · ${r.postmortem.field}`));
    box.append(el('strong', '', '실제 현장이라면 누구에게 알리고 무엇을 더 확인했을까?'), pm);
    if (final) { const hist = el('ul', 'screen-notes'); for (const h of [...gl.history, res]) hist.append(el('li', '', `${h.title}: 사건 해결 ${h.resolved}/${h.incidents.length} · 정상 완료 ${h.success}/${h.total}`));
      box.append(el('strong', '', '장애 대응 근무 기록 (교육용 가상 기록 · 실제 자격 아님)'), hist); }
    const kinds = [];
    if (res.cleared && gl.next) kinds.push(g.linux?'next-linux':'next-incident');
    if (!res.cleared || inc.practice || g.linux?.practice) kinds.push('retry-incident');
    kinds.push('result', 'menu', 'stay');
    box.append(nextButtons(kinds));
    show(final ? 'incident-complete' : res.cleared ? 'incident-clear' : 'incident-failed', [box],
      gl.seen.includes(key) ? null : () => send({ type: 'mark_shift_seen', key }, { quiet: true }));
  }
  // Phase 6: a finished global shift. Every row is the engine's own record (outcome, score, mode, consent).
  function shiftDone(g) {
    if(g.global.kind==='free'&&g.incident){const gl=g.global,res=gl.result,box=el('section','screen shift-result');
      box.append(el('span','eyebrow','FREE SHIFT · 진급 기록 없음'),el('h2','','오늘의 자유 교대를 마쳤습니다'),el('p','screen-sub',`seed ${gl.seed} · ${gl.difficultyLabel} · 정상 완료 ${res.success}/${res.total} · 사건 해결 ${res.resolved}/${res.incidents.length}`));
      const list=el('ul','screen-notes');for(const r of res.rows)list.append(el('li','',`${r.city} · ${r.client}: ${r.label}`));for(const r of res.incidents)list.append(el('li','',`${r.id} ${r.label}: ${r.outcome} · 정지 ${r.downtime}분 · 지연 ${r.slowMinutes}분`));box.append(list,nextButtons(['global-free','menu','stay']));
      show('shift-free',[box],()=>send({type:'mark_shift_seen',key:'shiftNone'},{quiet:true}));return;}
    if (['incident','linux'].includes(g.mode)) return incidentShiftDone(g);
    const gl = g.global, res = gl.result, key = `shift${gl.shift}`, box = el('section', 'screen shift-result');
    const played = new Set([...gl.history.filter(h => h.cleared).map(h => h.shift), res.cleared ? res.shift : null]);
    const final = res.cleared && !gl.next && gl.shifts.every(x => played.has(x.number));
    box.append(el('span', 'eyebrow', `GLOBAL SHIFT ${gl.shift}/${gl.shiftCount} · ${gl.coachingLabel}`),
      el('h2', '', final ? `글로벌 교대 근무 ${gl.shiftCount}개 모두 클리어` : `교대 ${gl.shift} ${res.cleared ? '클리어' : '목표 미달성'} · ${res.title}`),
      el('p', 'screen-sub', `엔진 판정: 정상 완료 ${res.success}/${res.total}건 (목표 ${res.goal.minSuccess}건 이상, 만료 ${res.goal.maxExpired}건까지) · 평균 ${res.average}점 · ${res.started} → ${res.finished}`));
    const table = el('table', 'terms-table shift-table'); table.innerHTML = '<thead><tr><th>요청</th><th>도시</th><th>고객 · 업무</th><th>결과</th><th>실행 · 동의</th><th>점수</th></tr></thead>';
    const tb = el('tbody');
    for (const r of res.rows) { const tr = el('tr'); tr.dataset.outcome = r.outcome;
      tr.append(el('td', '', `#${r.rid}`), el('td', '', `${r.city} (${r.site})`), el('td', '', `${r.client} · ${r.job}`), el('td', r.outcome === 'on_time' ? 'ok' : 'warn', r.label),
        el('td', '', r.mode ? `${r.mode} · ${r.consent}` : r.outcome === 'rejected' ? `거절: ${r.reason}` : '미실행'), el('td', '', r.score ?? '—')); tb.append(tr); }
    table.append(tb); box.append(table);
    const ul = el('ul', 'screen-notes'); for (const t of res.feedback) ul.append(el('li', '', t));
    box.append(el('strong', '', gl.coaching === 'none' ? '스스로 돌아보기' : '선배의 짧은 피드백'), ul);
    if (final) { const hist = el('ul', 'screen-notes'); for (const h of [...gl.history, res]) hist.append(el('li', '', `교대 ${h.shift} ${h.title}: 정상 완료 ${h.success}/${h.total} · 평균 ${h.average}점`));
      box.append(el('strong', '', '글로벌 근무 기록 (교육용 가상 기록 · 실제 자격 아님)'), hist); }
    const kinds = [];
    if (res.cleared && gl.next) kinds.push('next-shift');
    if (!res.cleared) kinds.push('retry-shift');
    kinds.push(final ? 'global-free' : 'result', 'menu', 'stay');
    // Closing this screen (any button / Esc) only records that it was seen. The same actions stay on the
    // monitor's 결과 tab, so a closed screen never strands the save.
    box.append(nextButtons(kinds));
    show(final ? 'global-complete' : res.cleared ? 'shift-clear' : 'shift-failed', [box],
      gl.seen.includes(key) ? null : () => send({ type: 'mark_shift_seen', key }, { quiet: true }));
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
      const st = g.story, key = String(st.chapterKey);
      if (st.chapter2?.failurePending && open !== 'chapter2-failure') { chapter2Failure(g); return; }
      for (const kind of ['chapter3', 'chapter3b']) if (st[kind]?.pending && open !== `${kind}-card`) { incidentCard(g, kind); return; }
      if (st.done && !seen.chapters.has(key)) { seen.chapters.add(key); const m = missionOf(st);
        if (st.graduation) graduation(g); else if (m === 'success') chapterClear(g); else chapterFailed(g); return; }
      if (st.step === 'closed' && !seen.failed) { seen.failed = true; chapterFailed(g); return; }
    }
    if (isGlobal(g) && g.global.done && !g.global.seen.includes(`shift${g.global.shift}`) && !open?.startsWith('shift') && !open?.startsWith('incident-') && open !== 'global-complete') { shiftDone(g); return; }
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
      if (r.stage === 'incident' && r.incidentAffecting?.length) { const rec = g.incident?.records?.find(x => x.id === r.incidentAffecting[0]); if (rec && rec.state === 'alert') toast(`경보 · ${rec.id} ${rec.severity} · 요청 #${r.id} ${rec.symptom} (원인 미확인) · 내 모니터 [사건] 탭`, 'hint'); }
      if (r.stage === 'net_fault') toast(`경보 · 요청 #${r.id} 작업 중단 · 고객 전송 경로 이상 (원인 미확인 · 서버 장비 ${r.hardware ? '확인 필요' : '정상'})`, 'hint');
    }
    const arrived = (g?.requests ?? []).filter(r => !prev?.requests?.some(x => x.id === r.id));
    if (prev && arrived.length) toast(`새 고객 요청 도착 · ${arrived.map(r => `${placeName(r)} #${r.id}`).join(', ')} · 세계지도에 경로 점등`);
  }
  return {
    // A loaded save that is already finished goes straight to its screen, so a finished tutorial is never a dead end.
    reset(g) { onClose = null; if (dlg.open) dlg.close(); open = null; seen = { tutorial: false, skipped: false, chapters: new Set(), failed: false, jobs: new Set((g?.requests ?? []).filter(r => !isOpen(r)).map(r => r.id)) }; setTimeout(() => check(null, game()), 0); },
    afterAction(prev, g) { alarms(prev, g); check(prev, g); },
    // Phase 6: the monitor's 결과 tab reopens the shift result screen (with its next-shift / retry buttons).
    showShift() { const g = game(); if (isGlobal(g) && g.global.done) shiftDone(g); },
    state: () => ({ open, history: history.map(h => ({ ...h })) }),
  };
}
