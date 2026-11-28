// Phase 7 (Issue #8): the incident-management card on my monitor and the on-site evidence buttons in each building.
// View + clicks only: every judgement (evidence reading, hypothesis verdict, action effect, approval, consent, timers,
// verification, report) is the Python engine's (IncidentSession). Before a diagnosis the snapshot carries no cause.
import { isOpen } from './game-view.js';

export const INCIDENT_STAGES = Object.freeze(['경보', '범위 확인', '근거 수집', '원인 판단', '완화·복구', '검증', '보고/종료']);
const STATE_TONE = { alert: 'fault', investigating: 'new', diagnosed: 'warn', recovering: 'recover', monitoring: 'recover', verified: 'ok', closed: 'done', failed: 'fault', void: 'muted' };
const VERDICT = { confirmed: ['원인 확정', 'ok'], refuted: ['반박됨', 'fault'], insufficient: ['근거 부족', 'warn'] };
const RESULT = { fix: ['해결 조치', 'ok'], move: ['작업 이전', 'recover'], pause: ['계획 중단', 'recover'], call: ['담당 호출', 'new'], notice: ['고객 안내', 'new'],
  consent: ['동의 요청', 'new'], isolate_move: ['격리·이전', 'recover'], isolate_repair: ['격리·수리', 'recover'], none: ['개선 없음', 'warn'], refused: ['허용 안 됨', 'fault'] };
const GROUP_LABEL = { escalate: '담당팀 호출', network: '네트워크', compute: 'GPU·작업', storage: '스토리지', facility: '시설·전원(요청)', platform: '플랫폼' };

export function isIncident(game) { return ['global', 'incident', 'linux', 'senior'].includes(game?.mode) && !!game.incident; }
export function incidentRecords(game) { return game?.incident?.records ?? []; }
export function focusIncident(game, id) {
  const recs = incidentRecords(game).filter(r => r.state !== 'armed');
  return recs.find(r => r.id === id) ?? recs.find(r => r.state === 'alert') ?? recs.find(r => !['closed', 'failed', 'void'].includes(r.state)) ?? recs.at(-1) ?? null;
}
// One line for the goal head / strip, from the engine records only.
export function incidentGoal(game) {
  const inc = game?.incident, g = game?.global; if (!inc || !g) return null;
  const label = `${g.kind==='free'?`글로벌 자유 교대 · ${g.difficultyLabel}`:game.senior ? `담당 엔지니어 · 선임 평가 ${g.shift}/2` : game.linux ? (game.linux.practice ? 'Linux 사건 연습' : `Linux 근무 ${game.linux.shift}/5`) : inc.practice ? '사건 연습' : `장애 대응 근무 ${inc.code}`} · ${g.coachingLabel ?? ''}`;
  if (!g.briefed) return { label, title: '근무 브리핑 확인', what: '아래 대화를 읽고 [근무 시작]을 누르세요. 그 전에는 시간이 흐르지 않고 배정·대응도 잠겨 있습니다.' };
  if (g.done && g.result.handoff) return { label, title: '교대 종료 · 미해결 인계', what: `인계 사건 ${g.result.handoff.incidents.length}건(방치 ${g.result.handoff.neglected}) · 요청 ${g.result.handoff.requests.length}건 — 해결로 세지 않습니다. 결과 화면에서 근거를 확인하세요.` };
  if (g.done) return { label, title: g.result.cleared ? '근무 목표 달성' : '근무 목표 미달성', what: `사건 해결 ${g.result.resolved}/${g.result.incidents.length} · 정상 완료 ${g.result.success}/${g.result.total} · 결과 화면을 확인하세요.` };
  const open = inc.records.filter(r => !['armed', 'closed', 'failed', 'void'].includes(r.state));
  const alert = inc.records.find(r => r.state === 'alert');
  if (alert) return { label, title: `경보 · ${alert.id} ${alert.title}`, what: '내 모니터 [사건] 탭에서 범위부터 확인하세요. 원인은 아직 모릅니다.' };
  if (open.length) { const r = open[0]; return { label, title: `${r.id} · ${r.stateLabel}`, what: `지금 할 일: ${r.next} — ${r.why}` }; }
  if (g.kind === 'free') return {label: `글로벌 자유 교대 · ${g.difficultyLabel} · seed ${g.seed}`, title: g.closing ? '남은 업무 정리' : '요청 배정·돌발 사건 대응', what: g.closing ? `남은 요청 ${g.remaining}건 · 사건 ${g.openIncidents}건을 마무리하세요.` : '요청함에서 조건을 읽고 배정하세요. 원할 때 [교대 마무리·결과 보기]로 접수를 멈출 수 있습니다.'};
  return { label, title: `도착 ${g.arrived}/${g.total} · 사건 ${inc.records.filter(r => r.state === 'closed').length}건 종료`, what: '요청함의 업무를 배정하고 시간을 진행하세요. 경보는 작업 진행 중에 들어옵니다.' };
}

export function createIncidentPane({ el, button, chip, readingsGrid, send, ui, render, here, goTo }) {
  const where = (g, loc) => g.incident.menu.locations[loc] || loc;
  function spark(trend) {
    if (!trend?.values?.length) return null;
    const v = trend.values, min = Math.min(...v), max = Math.max(...v), w = 160, h = 30, span = max - min || 1;
    const pts = v.map((y, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - 3 - (y - min) / span * (h - 6)).toFixed(1)}`).join(' ');
    const box = el('span', 'inc-spark'); box.innerHTML = `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
    box.append(el('small', '', `${trend.label}: ${v.join(' → ')}`)); return box;
  }
  function evidenceRow(e, g) {
    const row = el('li', `inc-ev ${e.status}`); row.dataset.evidence = e.probe;
    const head = el('div', 'inc-ev-head'); head.append(chip(e.status === 'ok' ? '정상' : e.status === 'warn' ? '주의' : '이상', e.status === 'ok' ? 'ok' : e.status === 'warn' ? 'warn' : 'fault'),
      el('strong', '', g.incident.menu.probes.find(p => p.id === e.probe)?.label ?? e.probe), el('small', '', `${e.time}${e.after ? ' · 복구 후' : ''} · ${where(g, e.location)}`));
    row.append(head, el('p', '', e.summary)); for (const l of e.lines || []) row.append(el('small', 'inc-line', l));
    const s = spark(e.trend); if (s) row.append(s); return row;
  }
  function probeButtons(g, rec, probes, { compact = false } = {}) {
    const box = el('div', 'inc-probes'), at = here();
    for (const p of probes) {
      if (g.linux && !g.linux.optional && !['cooling', 'ups'].includes(p.id)) continue;
      const ok = p.location === at, seen = rec.evidence.some(e => e.probe === p.id && e.minute === g.clock.minute);
      if (ok) { const b = button(`${seen ? '✓ ' : ''}관측 · ${p.label}`, () => send({ type: 'incident_observe', incident: rec.id, probe: p.id }), 'probe', { 'data-probe': p.id, title: `${p.fact} 명령어 예시(입력 불가): ${p.example}` }); box.append(b); }
      else if (!compact) box.append(button(`→ ${p.where} · ${p.label}`, () => goTo(p.location), 'link probe-away', { 'data-goto': p.location, 'data-probe-away': p.id, title: '현장 관측은 그 장소에서만 기록됩니다' }));
    }
    return box;
  }
  function stepper(rec) {
    const ol = el('ol', 'inc-stepper'); ol.setAttribute('aria-label', '사건 단계');
    INCIDENT_STAGES.forEach((s, i) => { const li = el('li', i < rec.stage ? 'done' : i === rec.stage ? 'now' : '', s); if (i === rec.stage) li.setAttribute('aria-current', 'step'); ol.append(li); });
    return ol;
  }
  function actionsBlock(g, rec) {
    const box = el('div', 'inc-actions'); box.dataset.incidentActions = rec.id;
    const scope = rec.scope?.jobs ?? [], sel = el('select'); sel.dataset.incidentRid = rec.id; sel.setAttribute('aria-label', '조치 대상 작업');
    for (const j of scope) { const o = el('option', '', `요청 #${j.rid} ${j.client} · 서버 ${j.servers.join('·') || '—'}`); o.value = String(j.rid); sel.append(o); }
    sel.value = String(ui.incidentRid?.[rec.id] ?? rec.rid); sel.addEventListener('change', () => { ui.incidentRid = { ...(ui.incidentRid || {}), [rec.id]: Number(sel.value) }; });
    const groups = {}, notes = rec.actionNotes || {};
    for (const a of g.incident.menu.actions) if (a.group !== 'comm') (groups[a.group] ||= []).push(a);
    // Phase9 sessions only: the engine states the real cost of quick workarounds (shorter stop, slower running after).
    if (g.incident.tradeoff) box.append(el('p', 'ws-note inc-tradeoff', g.incident.tradeoff));
    for (const [group, list] of Object.entries(groups)) {
      const row = el('div', 'inc-group'); row.append(el('small', '', GROUP_LABEL[group] || group));
      for (const a of list) {
        const location=g.linux?.actionLocations?.[rec.id]?.[a.id];
        if(location&&location!==here())row.append(button(`→ ${where(g,location)} · ${a.label}`,()=>goTo(location),'link',{'data-action-goto':a.id}));
        else row.append(button(notes[a.id] ? `${a.label} · 임시 우회` : a.label, () => send({ type: 'incident_act', incident: rec.id, action: a.id, ...(['load_shed', 'planned_pause'].includes(a.id) ? { rid: Number(sel.value) } : {}) }), '', { 'data-incident-action': a.id, ...(notes[a.id] ? { title: notes[a.id] } : {}) }));
      }
      box.append(row);
    }
    if (scope.length > 1) { const l = el('label', 'select-line', '이전·계획 중단 대상'); l.append(sel); box.prepend(l); }
    return box;
  }
  // Phase 10: the engine tries every recovery path of the diagnosed cause on a rolled-back copy (no save/time change).
  const RISK = { ok: ['✓ 기한 내', 'ok'], late: ['⚠ 기한 초과', 'warn'], fail: ['✕ 작업 실패', 'fault'], stuck: ['⏸ 8시간 안에 끝나지 않음', 'fault'] };
  function jobLine(j) {
    const line = el('div', 'inc-fc-job'); const [w, t] = RISK[j.risk]; line.dataset.risk = j.risk;
    line.append(chip(w, t), el('span', '', ` 요청 #${j.rid} ${j.client} · ${j.risk === 'fail' ? `${j.failedAt} 실패` : j.finish ? `완료 ${j.finish}` : '완료 미정'} · 기한 ${j.due ?? '—'}${j.late ? ` (${j.late}분 초과)` : ''}`),
      el('small', 'inc-line', `정지 ${j.stopMinutes}분 · 감속 운전 ${j.slowMinutes}분`));
    return line;
  }
  function forecastBlock(g, rec) {
    const box = el('div', 'inc-block inc-forecast'); box.dataset.forecast = rec.id;
    const f = ui.forecast?.[rec.id], fresh = f && f.minute === g.clock.minute;
    const run = () => send({ type: 'incident_forecast', incident: rec.id }).then(res => { const out = res?.result?.incident?.forecast; if (res?.ok && out) { ui.forecast = { ...(ui.forecast || {}), [rec.id]: out }; render(); } });
    const head = el('div', 'inc-head'); head.append(el('strong', '', '조치별 영향 비교 · 엔진 예측'), button(fresh ? '다시 계산' : '영향 비교 계산', run, fresh ? 'link' : 'primary', { 'data-forecast-run': rec.id }));
    box.append(head);
    if (!f || f.incident !== rec.id) { box.append(el('small', 'ops-note', '원인을 확정했습니다. 조치마다 준비·정지 시간, 복구 뒤 처리 속도, 영향 작업별 예상 완료와 기한 위험을 비교할 수 있습니다. 계산은 저장과 가상 시간을 바꾸지 않습니다.')); return box; }
    if (!fresh) box.append(el('p', 'ws-warn', `${f.time} 기준 예측입니다. 시간이 지났으니 다시 계산하세요.`));
    const table = el('table', 'inc-forecast-table'); table.setAttribute('aria-label', '조치별 영향 비교');
    const hr = el('tr'); for (const h of ['조치', '준비 · 복구', '영향 작업별 결과']) hr.append(el('th', '', h)); table.append(hr);
    for (const o of [f.baseline, ...f.options]) {
      const tr = el('tr'); tr.dataset.forecastOption = o.action ?? 'none';
      const name = el('td'); name.append(el('strong', '', o.label));
      if (o.kind) name.append(el('small', 'inc-line', o.kind === 'workaround' ? '임시 우회 · 정지 짧음 · 복구 뒤 감속' : '원인 조치 · 복구 뒤 정상 속도'));
      const prep = el('td'); prep.append(el('span', '', !o.feasible ? `불가 — ${o.reason}` : o.restored ? `복구 ${o.restored}` : o.incidentState === 'failed' ? '복구 전에 영향 작업이 실패 → 사건 실패' : o.action ? '8시간 안에 복구 안 됨' : '원인 그대로'));
      for (const st of o.steps || []) prep.append(el('small', 'inc-line', st));
      if (o.residual) prep.append(el('small', 'inc-line', o.residual));
      const jobs = el('td'); if (o.feasible) for (const j of o.jobs) jobs.append(jobLine(j)); else jobs.append(el('span', '', '—'));
      tr.append(name, prep, jobs); table.append(tr);
    }
    box.append(table, el('small', 'ops-note', f.notice));
    return box;
  }
  function handoffBlock(g) {
    const h = g.incident?.handoff; if (!h || g.incident.handedOff || !g.global?.briefed || g.global?.done) return null;
    const box = el('div', 'ws-card inc-handoff'); box.dataset.handoff = h.available ? 'available' : 'blocked';
    box.append(el('strong', '', '교대 종료 · 미해결 인계'));
    if (!ui.handoffOpen) {
      box.append(el('small', 'ops-note', h.available ? '해결하지 못한 사건·요청을 다음 교대에 명시적으로 넘기고 이번 교대를 끝냅니다. 인계는 해결로 세지 않습니다.' : h.reason),
        button('인계 목록 검토', () => { ui.handoffOpen = true; render(); }, 'link', { 'data-handoff-open': '', ...(!h.available ? { disabled: '' } : {}) }));
      return box;
    }
    box.append(el('p', 'ws-warn', h.notice));
    const ul = el('ul', 'inc-list');
    for (const x of h.incidents) { const li = el('li'); li.dataset.handoffClass = x.class; li.append(chip(x.classLabel, x.class === 'handover' ? 'warn' : 'fault'), el('span', '', ` ${x.id} · ${x.note}${x.missing.length ? ` — 부족: ${x.missing.join(', ')}` : ''}`)); ul.append(li); }
    for (const x of h.requests) { const li = el('li'); li.append(chip('요청 인계', 'new'), el('span', '', ` 요청 #${x.rid} ${x.client} · ${x.statusLabel} · 기한 ${x.due ?? '—'}`)); ul.append(li); }
    box.append(ul);
    if (h.incidents.some(x => x.class === 'neglect')) box.append(el('p', 'ws-tip', '방치로 기록될 사건이 있습니다. 넘기기 전에 [범위 확인]과 [고객 영향 안내]를 하면 책임 인계가 됩니다.'));
    const row = el('div', 'decision-row');
    row.append(button('인계하고 교대 종료', () => send({ type: 'handoff_shift', confirm: true }).then(res => { if (res?.ok) { ui.handoffOpen = false; render(); } }), 'primary', { 'data-handoff-confirm': '' }),
      button('취소', () => { ui.handoffOpen = false; render(); }, 'link', { 'data-handoff-cancel': '' }));
    box.append(row);
    return box;
  }
  function statusLines(rec) {
    const lines = [];
    for (const e of Object.values(rec.escalations)) lines.push(`${e.label}: ${e.called} 호출 · ${e.ready ? '승인됨' : `승인 예정 ${e.approved}`}`);
    if (rec.consent) lines.push(`고객 동의: ${rec.consent === 'accepted' ? '동의' : '거절'}`);
    if (rec.busyUntil) lines.push(`직전 조치 결과 확인 중 · ${rec.busyUntil} 이후 다음 조치`);
    if (rec.recoveryBy) lines.push(`복구 조치: ${rec.recoveryBy}${rec.eta ? ` · 예상 ${rec.eta}` : ''}`);
    if (rec.limitLeft != null) lines.push(`제한 시간 남음 ${rec.limitLeft}분(가상) · 영향이 남으면 작업 실패`);
    if (rec.residual) lines.push(`${rec.residual.label} — ${rec.residual.text}`);
    if (rec.recovered) lines.push(`복구 ${rec.recovered}${rec.verified ? ` · 사후 확인 ${rec.verified}` : ''}${rec.reported ? ` · 보고 ${rec.reported}` : ''}`);
    if (rec.customers?.length > 1) lines.push('영향 고객 안내: ' + rec.customers.map(c => `요청 #${c.rid} ${c.client} ${c.notified.length ? `✓ ${c.notified.at(-1)}` : '✕ 아직 안내 안 함'}`).join(' · '));
    else if (rec.notified.length) lines.push(`고객 안내: ${rec.notified.join(', ')}`);
    return lines;
  }
  function card(g, rec) {
    const box = el('div', 'ws-card inc-card'); box.dataset.incident = rec.id; box.dataset.state = rec.state;
    const head = el('div', 'inc-head'); head.append(el('strong', '', `${rec.id} · ${rec.severity ?? ''} · ${rec.title}`), chip(rec.stateLabel, STATE_TONE[rec.state]));
    box.append(head, el('p', 'ws-note', `요청 #${rec.rid} ${rec.client ?? ''}(${rec.city ?? ''}) · 발견 ${rec.detected ?? '—'} · 증상: ${rec.symptom ?? '—'}${rec.causeLabel ? ` · 원인: ${rec.causeLabel}` : ' · 원인 미확인'}`));
    box.append(stepper(rec));
    const now = el('p', 'inc-now'); now.dataset.incidentNext = rec.next; now.append(el('b', '', `지금 할 일: ${rec.next}`), document.createTextNode(` — ${rec.why}`)); box.append(now);
    if (rec.hint) box.append(el('p', 'ws-tip mentor-hint', `선배: ${rec.hint}`));
    const open = !['closed', 'failed', 'void'].includes(rec.state);
    const row = el('div', 'decision-row');
    if (rec.state === 'alert') row.append(button('범위 확인 · 영향 고객·작업·장비', () => send({ type: 'incident_ack', incident: rec.id }), 'primary', { 'data-incident-ack': rec.id }));
    if (open && rec.acknowledged) row.append(button('고객 영향 안내 · 예상 시각', () => send({ type: 'incident_act', incident: rec.id, action: 'notify_customer' }), '', { 'data-incident-notify': rec.id }));
    if (g.linux && open && rec.acknowledged) row.append(button('Linux 진단 · 내 모니터', () => {ui.tab='linux';ui.incident=rec.id;if(ui.linux)ui.linux.incident=rec.id;goTo('noc');render();}, 'primary', {'data-open-linux':rec.id}));
    if (rec.state === 'monitoring') row.append(button('사후 확인', () => send({ type: 'incident_verify', incident: rec.id }), 'primary', { 'data-incident-verify': rec.id }));
    if (rec.state === 'verified') row.append(button('고객에게 사건 보고 · 종료', () => send({ type: 'incident_report', incident: rec.id }), 'primary', { 'data-incident-report': rec.id }));
    if (row.childElementCount) box.append(row);
    if (rec.scope) box.append(el('p', 'ws-note inc-scope', `영향 범위: ${rec.scope.text}`));
    const lines = statusLines(rec); if (lines.length) box.append(readingsGrid(lines.map((l, i) => [i ? '' : '진행', l]), 'ops-readings inc-status'));
    if (rec.verifyBlocker && rec.state === 'monitoring') box.append(el('p', 'ws-warn', rec.verifyBlocker));
    if (rec.verifyProbes?.length && ['recovering', 'monitoring'].includes(rec.state)) box.append(el('p', 'ws-note', '복구 뒤 다시 볼 지표: ' + rec.verifyProbes.map(id => { const p = g.incident.menu.probes.find(x => x.id === id); return p ? `${p.label}(${p.where})` : id; }).join(', ')));
    if (open && rec.acknowledged && ['investigating', 'monitoring'].includes(rec.state)) {
      const p = el('div', 'inc-block'); p.dataset.labTarget = ''; p.dataset.labQuestion = `${rec.id}:${rec.state}`; p.append(el('strong', '', rec.state === 'monitoring' ? '복구 뒤 다시 관측 (지금 있는 곳에서 가능한 것)' : `근거 수집 · 지금 위치: ${where(g, here())}`));
      p.append(probeButtons(g, rec, g.incident.menu.probes)); p.append(el('small', 'ops-note', g.linux ? 'Linux 증거는 내 모니터 [Linux]에서 수집합니다. 냉각·UPS BMS는 해당 현장에서 별도로 관측합니다.' : '명령어 예시는 버튼 설명(마우스 올림)에만 있고 이번 단계에서 직접 입력하지 않습니다. 실제 OS·장비 명령은 실행되지 않습니다.')); box.append(p);
    }
    if (rec.state === 'investigating') {
      const h = el('div', 'inc-block inc-hypo'), sel = el('select'); sel.dataset.causeSelect = rec.id; sel.setAttribute('aria-label', '원인 가설');
      for (const c of g.incident.menu.causes) { const o = el('option', '', c.label); o.value = c.id; sel.append(o); }
      sel.value = ui.cause?.[rec.id] ?? g.incident.menu.causes[0].id; sel.addEventListener('change', () => { ui.cause = { ...(ui.cause || {}), [rec.id]: sel.value }; });
      h.append(el('strong', '', '원인 판단 (관측과 맞지 않는 가설은 반박됩니다)'), sel, button('가설 판단', () => send({ type: 'incident_hypothesis', incident: rec.id, cause: sel.value }), 'primary', { 'data-hypothesis': rec.id }));
      box.append(h);
    }
    if (rec.state === 'diagnosed' && g.incident.rules10) box.append(forecastBlock(g, rec));
    if (['diagnosed', 'recovering'].includes(rec.state)) { const a = actionsBlock(g, rec); a.dataset.labTarget = ''; a.dataset.labQuestion = `${rec.id}:${rec.state}`; box.append(a); }
    if (rec.hypotheses.length) { const ul = el('ul', 'inc-list'); for (const x of rec.hypotheses.slice(-4)) { const [w, t] = VERDICT[x.verdict]; const li = el('li'); li.dataset.verdict = x.verdict; li.append(chip(w, t), el('span', '', `${x.label} — ${x.reason}`)); ul.append(li); } box.append(el('strong', '', '가설 기록'), ul); }
    if (rec.actions.length) { const ul = el('ul', 'inc-list'); for (const x of rec.actions.slice(-5)) { const [w, t] = RESULT[x.result]; const li = el('li'); li.dataset.result = x.result; li.append(chip(w, t), el('span', '', `${x.time} ${x.label} — ${x.text}`)); ul.append(li); } box.append(el('strong', '', '조치 기록'), ul); }
    if (rec.evidence.length) { const ul = el('ul', 'inc-evidence'); for (const e of rec.evidence.slice(-6).reverse()) ul.append(evidenceRow(e, g)); const d = el('details', 'inc-details'); d.open = rec.state === 'investigating'; d.append(el('summary', '', `관측 기록 ${rec.evidence.length}건`), ul); box.append(d); }
    if (rec.postmortem) { const d = el('details', 'inc-details'); d.open = true; d.dataset.postmortem = rec.id;
      d.append(el('summary', '', '사후 분석 · 다른 가능한 가설'), el('p', '', `인과: ${rec.postmortem.causal}`), el('p', '', `배제한 가설: ${rec.postmortem.alternatives}`), el('p', 'ws-tip', rec.postmortem.field)); box.append(d); }
    const tl = el('details', 'inc-details'); tl.append(el('summary', '', `사건 타임라인 ${rec.timeline.length}건`)); const ol = el('ol', 'result-timeline'); for (const [t, , x] of rec.timeline.slice(-12)) ol.append(el('li', '', `${t} ${x}`)); tl.append(ol); box.append(tl);
    return box;
  }
  function paneIncident(body, g) {
    const recs = incidentRecords(g).filter(r => r.state !== 'armed');
    body.append(el('div', 'ws-label', `${g.incident.title} · ${g.incident.notice.slice(0, 60)}…`));
    if (!g.global.briefed) { body.append(el('p', 'ws-note', '근무 브리핑을 확인하면 시작합니다. 브리핑 전에는 조회·이동만 할 수 있습니다.')); return; }
    if (!recs.length) { body.append(el('p', 'ws-note', '아직 사건 경보가 없습니다. 요청함의 업무를 배정하고 작업이 진행되면 경보가 들어올 수 있습니다.')); const h = handoffBlock(g); if (h) body.append(h); return; }
    const handoff = handoffBlock(g);
    if (handoff && ui.handoffOpen) body.append(handoff);
    const list = el('div', 'inc-tabs');
    const cur = focusIncident(g, ui.incident);
    for (const r of recs) list.append(button(`${r.id} ${r.state === 'alert' ? '⚠ ' : ''}${r.cause ? r.causeLabel : r.symptom}`, () => { ui.incident = r.id; render(); }, r.id === cur?.id ? 'active' : '', { 'data-incident-select': r.id, 'data-state': r.state }));
    body.append(list);
    if (cur) body.append(card(g, cur));
    if (handoff && !ui.handoffOpen) body.append(handoff);
  }
  // On-site panel for a building interior / the server hall: what the instruments show + the probes recordable here.
  function siteEvidence(g, location) {
    if (!g?.incident || !g.global?.briefed) return null;
    const box = el('div', 'inc-site'); box.dataset.siteEvidence = location;
    const probes = g.incident.menu.probes.filter(p => p.location === location);
    const open = incidentRecords(g).filter(r => r.acknowledged && (g.linux ? ['investigating','diagnosed','recovering','monitoring'] : ['investigating','monitoring']).includes(r.state));
    box.append(el('strong', '', `현장 관측 · ${where(g, location)}`), el('small', 'ops-note', `여기서 기록할 수 있는 관측: ${probes.map(p => p.label).join(', ') || '없음'}`));
    if (!open.length) box.append(el('small', 'ops-note', '범위를 확인한 진행 중 사건이 없으면 관측을 기록하지 않습니다. 계기는 그대로 볼 수 있습니다.'));
    for (const rec of open) { const row = el('div', 'inc-site-row'); row.append(el('span', '', `${rec.id} · 요청 #${rec.rid}`), probeButtons(g, rec, probes, { compact: true })); box.append(row);
      if(g.linux&&['diagnosed','recovering'].includes(rec.state))box.append(actionsBlock(g,rec));
    }
    return box;
  }
  return { paneIncident, siteEvidence };
}

// Physical instrument rows for a facility card (engine facilities view). Visible to anyone standing in the building.
export function facilityRows(g, id) {
  const f = g?.incident?.facilities; if (!f) return null;
  // Each building has its own instruments; a block from the previous place may still be in the snapshot for a frame.
  const need = { COOLING: 'cooling', UPS: 'ups', POWER: 'ups', NETWORK: 'edge', 'HALL-01': 'storage' }[id];
  if (need && !f[need]) return [['계기', '건물 안에 들어가면 이 건물의 계기를 볼 수 있습니다(현장 정보).']];
  if (id === 'COOLING') return Object.entries(f.cooling).map(([z, c]) => [`냉각 구역 ${z} (${c.servers.join('·')})`, `${c.state === 'ok' ? '정상' : c.state === 'warn' ? '⚠ 경고' : '↻ 복구 중'} · P-1 ${c.pumps['P-1']} / P-2 ${c.pumps['P-2']} / 예비 P-3 ${c.pumps['P-3']} · 유량 ${c.flow} L/min · 흡입 ${c.inlet} °C`]);
  if (id === 'UPS' || id === 'POWER') return Object.entries(f.ups).map(([n, u]) => [`${n} (서버 ${u.servers.join('·')})`, u.mode === 'battery' ? `⚠ 배터리 운전 · 남은 보호 시간 약 ${u.runtime}분(가상) · 잔량 ${u.battery}%${u.restoring ? ' · 전원팀 복구 중' : ''}` : '상용 전원 정상 · 배터리 대기']);
  if (id === 'NETWORK') return [...Object.values(f.tor).map(t => [`ToR-${t.rack}${t.dual ? ' (이중 업링크)' : ' (단일 업링크)'}`, Object.entries(t.ports).map(([p, s]) => `${p} ${s === 'DOWN' ? '✕ DOWN' : 'UP'}`).join(' · ') + (t.rerouted ? ' · P2로 우회 중' : '')]),
    ['엣지 링크', `E1 ${f.edge.E1}% · E2 ${f.edge.E2}%${f.edge.state === 'congested' ? ' · ⚠ 혼잡' : ''}${f.edge.qos ? ' · QoS 조정 중' : ''}`], ['DNS 리졸버', f.dns.state === 'fail' ? `⚠ 주 리졸버 응답 없음${f.dns.failover ? ' · 보조 전환 중' : ''}` : '정상']];
  if (id === 'HALL-01') return [['랙 ToR 포트 LED', Object.values(f.tor).map(t => `${t.rack} ${Object.values(t.ports).includes('DOWN') && !t.rerouted ? '✕' : '●'}`).join(' · ')], ['스토리지 패널', f.storage.length ? f.storage.map(v => `${v.volume} 사용 ${v.used}% · 지연 ${v.latency} ms`).join(' / ') : '이상 볼륨 없음']];
  return null;
}
export { isOpen };
