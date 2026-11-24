// My-monitor panes for chapters 2-5 (Issue #6). DOM only: every number, verdict and lock comes from the Python
// engine snapshot or from the engine's reply to a real action. Nothing here completes a step by itself: a tab or
// a page only shows; the buttons send the same actions the Tkinter game calls (wait / reject / respond / repair /
// migrate / training_*), and the engine accepts or refuses them.
import {LAB_STAGES} from './campaign-view.js';

export function createChapterPanes({ el, button, chip, readingsGrid, send, ui, render }) {
  const pre = text => { const p = el('pre', 'lab-out'); p.textContent = text; return p; };
  const lines = (list, cls = 'ws-note') => { const box = el('div', 'eng-lines'); for (const t of list || []) box.append(el('p', cls, t)); return box; };

  // ---- chapter 2: compare the two customers on the same basis (engine chapter2_comparison_lines) ----
  function compareCard(g) {
    const c2 = g.story?.chapter2; if (!c2 || !c2.comparison?.length) return null;
    const card = el('div', 'ws-card compare-card'); card.dataset.compare = '';
    card.append(el('strong', '', '두 고객 요청 비교 · 엔진 현재 값 (정답·권장 없음)'), lines(c2.comparison));
    return card;
  }
  // Waiting and rejecting are real chapter-2 choices (engine wait_request / reject_request).
  function decisionRow(g, r) {
    if (!g.story || g.story.chapterKey === 1 || r.stage !== 'incoming') return null;
    const row = el('div', 'decision-row');
    row.append(button('요청 대기 (자원 미점유)', () => send({ type: 'wait_request', rid: r.id }), '', { 'data-wait': String(r.id) }));
    const input = el('input'); input.type = 'text'; input.placeholder = '거절 사유 (고객에게 전달)'; input.maxLength = 120; input.dataset.rejectReason = String(r.id);
    row.append(input, button('거절', () => send({ type: 'reject_request', rid: r.id, reason: input.value }), 'danger', { 'data-reject': String(r.id) }));
    return row;
  }
  function planBriefing(res) { return res?.briefing?.length ? lines(res.briefing, 'ws-note brief') : null; }
  function impactLines(res, mode, index) { const list = res?.[mode]?.impacts?.[index]; return list?.length ? list.map(t => el('small', 'impact', `다른 고객: ${t}`)) : []; }

  // ---- chapter 3: engine network diagnosis (view_network_diagnosis) ----
  function networkEvidence(d) {
    const card = el('div', 'ws-card net-evidence'); card.dataset.netDiagnosis = d.kind;
    card.append(el('strong', '', `네트워크 진단 · ${d.summary}`));
    card.append(lines(d.observations));
    card.append(readingsGrid([['주 통신 경로', d.primary], ['필요 / 가용 대역폭', `${d.needed} / ${d.available}${d.link_ok ? '' : ' (사용 가능한 경로 없음)'}`], ['백업 경로', d.backup],
      ['장비(서버·GPU)', d.equipment], ['네트워크 중단', `${d.downtime}/${d.limit}분`], ['대응', `${d.attempts}/3회${d.responses?.length ? ` · ${d.responses.join(' → ')}` : ''}`]]));
    card.append(el('small', 'ws-note', '교육용 구성 기준의 관측값입니다. 진단은 원인을 정해 주지 않습니다 — 관측과 대응의 관계를 스스로 판단하세요.'));
    return card;
  }
  // ---- chapter 4: engine hardware diagnosis (view_hardware_diagnosis) ----
  function hardwareEvidence(d) {
    const card = el('div', 'ws-card hw-evidence'); card.dataset.hwDiagnosis = d.server;
    card.append(el('strong', '', `장비 진단 · Server ${d.server} ${d.health}${d.repair_left ? ` · 복구 ${d.repair_left}분 남음` : ''}`));
    const normal = (d.normal || []).map(n => `${n.key} GPU ${n.gpu}/전력 ${n.power}`).join(' · ') || '없음';
    card.append(readingsGrid([['영향 작업', `${d.company} · ${d.mode} · 이 서버 조각 GPU ${d.slice_gpu}/전력 ${d.slice_power}`],
      ['필요 자원(작업 전체)', `GPU ${d.need_gpu} / 전력 ${d.need_power}`], ['정상 서버 여유', `${normal} (합계 GPU ${d.normal_gpu} / 전력 ${d.normal_power})`],
      ['장비 복구', `${d.repair_minutes}분 → 예상 완료 ${d.repair_finish_label} · ${d.repair_on_time === null ? '기한 없음' : d.repair_on_time ? '기한 내' : '기한 초과'}`],
      ['작업 이전', d.migrate_possible ? `준비 ${d.migrate_minutes}분 → 예상 완료 ${d.migrate_finish_label} · ${d.migrate_on_time ? '기한 내' : '기한 초과'}` : `불가 · ${d.reason}`],
      ['완료 기한', d.due_label || '—'], ['누적 중단', `${d.downtime}분`]]));
    if (d.advice) card.append(el('p', 'ws-note', d.advice));
    return card;
  }
  function trainingSymptom(d) {
    const card = el('div', 'ws-card'); card.dataset.trainingSymptom = '';
    card.append(el('strong', '', '증상만 보입니다 · 독립 진단'), el('p', 'ws-note', d.symptom || '작업 상태를 확인하세요.'),
      el('p', 'ws-note', '원인 근거는 [연수] 탭의 가상 터미널로 직접 관측하세요. 조치는 이 탭의 대응 버튼으로 하며, 엔진이 Stage 5 판단 전 조치를 막습니다.'));
    if (d.locked) card.append(el('p', 'ws-warn', d.locked));
    return card;
  }

  // ---- chapter 5: Engineering Lab (TrainingProgress Stage 1~5) ----
  const SEGMENTS = [['edge-primary', '고객 단말 → 주 경로 라우터'], ['primary-wan', '주 경로 라우터 → AIDC 게이트웨이'], ['edge-backup', '고객 단말 → 백업 경로 라우터'],
    ['backup-wan', '백업 경로 라우터 → AIDC 게이트웨이'], ['gateway-servers', 'AIDC 게이트웨이 → 서버 A~D (내부)']];
  const SEG_STATE = { up: 'UP', down: 'DOWN', standby: '대기', active: '사용 중' };
  function labState(gid) { ui.lab ??= {}; ui.lab[gid] ??= { log: [], feedback: '', blocks: ['', '', ''], preview: null, facts: {} }; return ui.lab[gid]; }
  async function labSend(gid, action, after) {
    const res = await send(action, { quiet: true }); const st = labState(gid);
    if (res?.result?.lab) after?.(res.result.lab, st);
    if (res && !res.ok) st.feedback = `↺ ${res.message}${res.hint ? ` · ${res.hint}` : ''}`;
    render(); return res;
  }
  function question(gid, t, stage, qkey, current) {
    const q = t.questions[`${stage}:${qkey}`]; if (!q) return null;
    const box = el('div', 'lab-q'); box.dataset.labQuestion = `${stage}:${qkey}`; box.append(el('strong', '', q.prompt));
    for (const [key, label] of q.options) {
      const sel = current?.answer === key;
      box.append(button(label, () => labSend(gid, { type: 'lab_answer', stage, question: qkey, answer: key }, (lab, st) => { st.feedback = `${lab.correct ? '✓' : '↺'} ${lab.text}`; }),
        `lab-opt${sel ? (current.correct ? ' ok' : ' warn') : ''}`, { 'data-answer': `${stage}:${qkey}:${key}` }));
    }
    return box;
  }
  function terminal(gid, t, stage, st) {
    const box = el('div', 'lab-term'); box.dataset.terminal = stage;
    const log = el('div', 'term-log'); log.setAttribute('aria-live', 'polite');
    for (const item of st.log.slice(-6)) { log.append(el('div', 'term-line', `${t.prompt} ${item.line}`)); log.append(pre(item.output)); if (item.hint) log.append(el('small', 'ws-warn', item.hint)); }
    if (!st.log.length) log.append(el('small', 'ws-note', `${t.hostLabel}(${t.prompt.split(':')[0]})에 접속했습니다. 지원: ${t.supported.join(', ')} · 미구현: ${t.unsupported.join(', ')}`));
    const form = el('form', 'term-form'); const input = el('input'); input.type = 'text'; input.autocomplete = 'off'; input.spellcheck = false; input.maxLength = 200;
    input.dataset.terminalInput = stage; input.dataset.focusKey = `term-${stage}`; input.setAttribute('aria-label', '가상 터미널 명령 입력');
    form.append(el('span', 'term-prompt', t.prompt), input, button('실행', () => {}, 'primary', { type: 'submit', 'data-terminal-run': stage }));
    form.addEventListener('submit', e => { e.preventDefault(); const line = input.value.trim(); if (!line) return; input.value = '';
      labSend(gid, { type: 'lab_command', source: 'terminal', stage, payload: line }, (lab, s) => { if (lab.kind === 'clear') s.log = []; else s.log.push({ line, output: lab.output, hint: lab.hint }); s.feedback = ''; }); });
    box.append(log, form);
    return box;
  }
  function paneLab(body, g) {
    const t = g.story?.training; if (!t) { body.append(el('p', 'ws-note', '제5장(심화 연수) 또는 Engineering Lab 연습에서 열립니다.')); return; }
    const s = t.status, gid = g.id, st = labState(gid), stage = s.current;
    const map = el('div', 'lab-map'); map.dataset.labMap = '';
    for (const x of s.stages) { const b = el('span', `lab-badge ${x.badge}`, `${x.no}. ${x.short} · ${x.badge_text}`); b.dataset.labStage = x.key; map.append(b); }
    body.append(map);
    const head = el('div', `ws-card lab-head tone-${s.headline.tone}`); head.dataset.labHead = s.headline.action || '';
    head.append(chip(s.headline.chip, s.headline.tone === 'warn' ? 'warn' : 'ok'), el('strong', '', s.headline.title), el('p', 'ws-note', s.headline.detail));
    body.append(head);
    const info = t.stages.find(x => x.key === stage);
    if (!s.done) body.append(el('p', 'ws-label', `Stage ${info.no} · ${info.title} — ${info.goal}`));
    const card = el('div', 'ws-card lab-stage'); card.dataset.labStageBody = stage;
    if (stage === 'structure') {
      card.append(el('small', 'ws-note', `${t.notice} · 증상: ${t.network.symptom}`));
      const grid = el('div', 'seg-grid');
      for (const [id, label] of SEGMENTS) { const state = t.network.segments[id], picked = s.segment?.answer === id;
        grid.append(button(`${label}${state ? ` · ${SEG_STATE[state]}` : ''}`, () => labSend(gid, { type: 'lab_segment', segment: id }, (lab, x) => { x.feedback = `${lab.correct ? '✓' : '↺'} ${lab.text}`; }),
          `seg${picked ? ' picked' : ''}${state === 'down' ? ' down' : ''}`, { 'data-segment': id })); }
      card.append(grid);
      if (s.segment?.correct) card.append(question(gid, t, 'structure', 'impact', s.impact));
    } else if (stage === 'tool') {
      const q = el('div', 'lab-q'); q.append(el('strong', '', t.choiceQuestion));
      for (const name of t.choices) q.append(button(`${name} — ${t.specs[name].summary}`, () => labSend(gid, { type: 'lab_command', source: 'choice', stage: 'tool', payload: name }, (lab, x) => { x.log.push({ line: lab.line, output: lab.output, hint: lab.hint }); x.feedback = ''; }),
        `lab-opt${s.choice?.answer === name ? ' picked' : ''}`, { 'data-choice': name }));
      card.append(q);
      const last = st.log.at(-1); if (last) card.append(el('div', 'term-line', `${t.prompt} ${last.line}`), pre(last.output));
      if (s.choice) { const fit = t.choiceFit[s.choice.answer]; if (fit) card.append(el('p', fit[0] === 'best' ? 'ws-note ok' : 'ws-warn', `${s.choice.answer}: ${fit[1]}`)); }
      if (s.choice?.correct) card.append(question(gid, t, 'tool', 'limit', s.limit));
    } else if (stage === 'assemble') {
      const opts = { command: Object.keys(t.blocks.command), option: Object.keys(t.blocks.option), target: [...Object.values(t.targets.routers), t.targets.gateway, ...Object.values(t.targets.servers)] };
      const row = el('div', 'block-row');
      ['command', 'option', 'target'].forEach((slot, i) => {
        const sel = el('select'); sel.dataset.block = slot; sel.setAttribute('aria-label', `${slot} 블록`);
        sel.append(Object.assign(el('option', '', slot === 'command' ? '명령 블록' : slot === 'option' ? '옵션 블록 (없음)' : '대상 블록 (없음)'), { value: '' }));
        for (const v of opts[slot]) { const o = el('option', '', v); o.value = v; sel.append(o); }
        sel.value = st.blocks[i];
        sel.addEventListener('change', () => { st.blocks[i] = sel.value; send({ type: 'lab_blocks_preview', blocks: st.blocks.map(x => x || null) }, { quiet: true }).then(res => { if (res?.ok) st.preview = res.result.lab; render(); }); });
        row.append(sel);
      });
      card.append(row);
      if (st.preview) card.append(el('div', 'term-line', `조립 결과: ${st.preview.line || '(비어 있음)'}`), lines(st.preview.roles, 'ws-note small'), ...st.preview.errors.map(e => el('p', 'ws-warn', e)));
      card.append(button('조립한 명령 실행', () => labSend(gid, { type: 'lab_command', source: 'blocks', stage: 'assemble', payload: st.blocks.map(x => x || null) }, (lab, x) => { x.log.push({ line: lab.line, output: lab.output, hint: lab.hint }); x.feedback = ''; }), 'primary', { 'data-run-blocks': '' }));
      const last = st.log.at(-1); if (last) card.append(el('div', 'term-line', `${t.prompt} ${last.line}`), pre(last.output));
      if (s.assembly) { const q = el('div', 'lab-q'); q.dataset.labQuestion = 'assemble:received'; q.append(el('strong', '', `방금 실행한 "${s.assembly.line}"의 응답은 몇 개였나요?`));
        for (const n of s.received_options) q.append(button(String(n), () => labSend(gid, { type: 'lab_answer', stage: 'assemble', question: 'received', answer: n }, (lab, x) => { x.feedback = `${lab.correct ? '✓' : '↺'} ${lab.text}`; }),
          `lab-opt${s.received?.answer === n ? (s.received.correct ? ' ok' : ' warn') : ''}`, { 'data-answer': `assemble:received:${n}` }));
        card.append(q); }
    } else if (stage === 'terminal' || stage === 'independent') {
      // The question the player must answer now goes ABOVE the terminal, so it is reachable without scrolling.
      const term = terminal(gid, t, stage, st);
      if (stage === 'terminal') {
        const ev = s.evidence, list = el('div', 'evidence'); list.dataset.evidence = '';
        for (const [k, label] of [['near', '가까운 네트워크 장비'], ['remote', '원격 서버(AIDC 쪽)'], ['route', '라우팅 정보']]) list.append(chip(`${ev[k] ? '✓' : '○'} ${label}`, ev[k] ? 'ok' : ''));
        card.append(list);
        if (s.statements.length) {
          const form = el('div', 'lab-q'); form.dataset.labQuestion = 'terminal:facts'; form.append(el('strong', '', '터미널 출력으로 확인된 사실과 아직 확정할 수 없는 것을 나누세요.'));
          for (const [key, text] of s.statements) { const row = el('div', 'fact-row'); row.append(el('span', '', text));
            for (const [v, label] of [['confirmed', '확인된 사실'], ['unknown', '아직 확정 불가']]) row.append(button(label, () => { st.facts[key] = v; render(); }, `lab-opt${st.facts[key] === v ? ' picked' : ''}`, { 'data-fact': `${key}:${v}` }));
            form.append(row); }
          form.append(button('분류 제출', () => labSend(gid, { type: 'lab_answer', stage: 'terminal', question: 'facts', answer: { ...st.facts } }, (lab, x) => { x.feedback = `${lab.correct ? '✓' : '↺'} ${lab.text}`; }), 'primary', { 'data-facts-submit': '' }));
          if (!s.facts?.correct) form.dataset.labTarget = '';
          card.append(form);
        }
        card.append(term);
      } else {
        const s5 = s.stage5;
        card.append(el('p', 'ws-note', `조치 전 직접 관측 ${s5.evidence_count}건${s5.evidence_ok ? ' · 판단할 근거 있음' : ''}${s5.recovered ? ' · 조치 완료' : ''}${s5.verified ? ' · 재확인 완료' : ''}`));
        if (s5.evidence_ok && !s5.cause?.correct) { const q = question(gid, t, 'independent', 'cause', s5.cause); q.dataset.labTarget = ''; card.append(q); }
        if (s5.cause?.correct && !s5.recovered) card.append(el('p', 'ws-note', '판단을 마쳤습니다. 조치는 [진단] 탭의 대응 버튼으로 합니다.'));
        card.append(term);
      }
    }
    if (s.done) card.append(el('p', 'ws-note', '다섯 Stage를 모두 통과했습니다. 결과 화면에서 기록을 확인하세요.'));
    body.append(card);
    if (st.feedback) body.append(el('p', 'lab-feedback', st.feedback));
    const foot = el('div', 'ws-foot');
    if (s.can_advance) foot.append(button(`다음 Stage 시작`, () => labSend(gid, { type: 'lab_next_stage' }, (lab, x) => { x.log = []; x.feedback = ''; }), 'primary', { 'data-lab-next': '' }));
    if (s.can_restart) foot.append(button('연수 사건 다시 받기', () => { if (confirm('같은 교육 조건의 새 연수 사건을 접수할까요? 통과한 Stage와 지난 기록은 유지됩니다.')) labSend(gid, { type: 'lab_restart_incident' }); }, '', { 'data-lab-restart': '' }));
    if (s.practice) for (const key of LAB_STAGES) if (key !== stage) foot.append(button(`Stage ${LAB_STAGES.indexOf(key) + 1} 연습`, () => labSend(gid, { type: 'lab_focus_stage', stage: key }, (lab, x) => { x.log = []; }), 'link', { 'data-lab-focus': key }));
    body.append(foot);
  }
  return { compareCard, decisionRow, planBriefing, impactLines, networkEvidence, hardwareEvidence, trainingSymptom, paneLab };
}
