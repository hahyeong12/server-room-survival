// Tutorial coach (Issue #5): a non-invasive guide layer. It reads the journey step the ENGINE ADAPTER decided
// (what / why / where / target) and points at the real control: an outline on a DOM element, or a ring over a
// 3D object (country, building, rack). It never clicks, selects, assigns or repairs for the player, and its
// buttons only fold the text or switch the guide off (skipping is recorded, never counted as done).
import {focusRequest,primaryRack,planRacks} from './game-view.js';
import {focusPath} from './network-data.js';

// When a target lives in a monitor tab that is not open, point at the tab instead.
const TAB_OF = { '[data-read-request]': 'inbox', '[data-plan-list]': 'plan', '[data-responses]': 'diagnosis' };
const PLACE = route => `#places [data-route=${route}]`;

export function createCoach({ $, el, button, store, game, getScene, isBlocked, send, toast }) {
  let folded = false, last = null, lastStep = null, actionStep = null, spot = null, ring = null, tag = '', shownSpot = null;
  const box = $('coach'), ringEl = $('coach-ring'), tagEl = $('coach-tag');

  function journey() { const j = game()?.journey; return j?.kind === 'tutorial' && !j.skipped && !j.completed ? j : null; }
  function active() { return !!journey()?.current && !isBlocked(); }

  // Resolve the step target into either a DOM element or a 3D point, following where the player is now.
  function resolve() {
    const j = journey(), cur = j?.current; if (!cur) return null;
    const nav = store.state.navigation, route = nav.route, t = cur.target || {}, g = game(), r = focusRequest(g);
    const dom = (selector, label) => { const e = document.querySelector(selector); return e && e.offsetParent !== null ? { kind: 'dom', el: e, selector, label } : null; };
    const go = (wanted, label) => (route !== wanted ? dom(PLACE(wanted), label || '먼저 이곳으로 이동') : null);
    const desk = () => (route === 'noc' && nav.nocView !== 'desk' ? dom('#noc-tools [data-noc-view=desk]', '내 자리 보기') : null);
    const rack = (id, label) => (id ? { kind: 'rack', id, label } : null);
    switch (t.kind) {
      case 'dom': {
        if (t.route) { const moved = go(t.route) || (t.route === 'noc' && desk()); if (moved) return moved; }
        const direct = dom(t.selector, cur.title); if (direct) return direct;
        const tab = TAB_OF[t.selector]; if (tab) return dom(`[data-ws-tab=${tab}]`, '이 탭을 여세요');
        if (t.selector === '[data-start-job]') return rack(planRacks(r)[0], '배정안의 서버 랙');
        return null;
      }
      case 'route': return go(t.route) || (t.then?.kind === 'campus' ? { kind: 'world', id: t.then.id.split(':')[1], label: '예: 냉각 플랜트 (다른 건물도 됩니다)' } : null);
      case 'campus-selected': return go('campus') || { kind: 'world', id: nav.facility, label: '두 번 클릭' };
      case 'world-request': { const p = focusPath(store.state); return go('world') || (p ? { kind: 'world', id: p.code, label: '요청이 온 곳' } : null); }
      case 'racks-of-plan': return go('hall') || rack(primaryRack(r), '배정안의 서버 랙');
      case 'fault-rack': {
        const f = j.fault; if (!f) return null;
        if (route !== 'hall') return go('hall');
        if (store.state.facility.selectedId !== f.rack) return rack(f.rack, '장애가 났던 랙');
        return dom(`[data-verify="${f.rack}"]`, '상태 재확인');
      }
      default: return null;
    }
  }

  function clearSpot() { if (spot) spot.classList.remove('coach-spot'); spot = null; }
  // The senior's card is docked in the right panel under the goal (never floats over controls). Only a small
  // click-through tag sits beside a highlighted DOM control, and a ring over 3D targets.
  function render() {
    const on = active(), j = journey(), cur = j?.current;
    document.body.classList.toggle('coach-folded', on && folded);
    if (!on) { box.hidden = true; ringEl.hidden = true; tagEl.hidden = true; clearSpot(); ring = null; return; }
    if (cur.id !== lastStep) { lastStep = cur.id; folded = false; document.body.classList.remove('coach-folded'); }
    if (actionStep === null) actionStep = cur.id;
    const target = resolve();
    clearSpot(); ring = null; tag = '';
    if (target?.kind === 'dom') { spot = target.el; spot.classList.add('coach-spot'); tag = target.label || '';
      // Bring a target inside a scrolling panel or monitor pane into view once (no page scroll).
      if (spot !== shownSpot) { shownSpot = spot; spot.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } }
    else if (target) ring = target;
    box.hidden = false;
    box.replaceChildren();
    const head = el('div', 'coach-head'); head.append(el('span', 'portrait mentor', '선배'), el('span', 'coach-step', `선배의 안내 · ${cur.title}`)); box.append(head);
    box.append(el('p', 'coach-say', last || (cur.id === 'briefing' ? '화면 아래 대화를 끝까지 읽고 [근무 시작]을 눌러요.' : target?.label ? `금색 테두리: ${target.label}` : '오른쪽 목표를 따라가 보세요.')));
    const row = el('div', 'coach-row');
    row.append(button(folded ? '이유·위치 펼치기' : '이유·위치 접기', () => { folded = !folded; render(); }, 'link', { id: 'coach-fold' }),
      button('튜토리얼 건너뛰기', () => { if (confirm('튜토리얼 안내를 끌까요? 실습 완료로 기록되지 않고, 게임 상태는 그대로입니다.')) send({ type: 'skip_tutorial' }); }, 'link', { id: 'coach-skip' }));
    box.append(row);
    position();
  }
  function position() {
    const scene = getScene();
    if (ring && scene) {
      const p = ring.kind === 'rack' ? scene.projectAsset(ring.id) : scene.projectWorld(ring.id);
      const vp = $('viewport').getBoundingClientRect();
      if (p?.visible) { ringEl.hidden = false; ringEl.style.left = `${p.x - vp.left}px`; ringEl.style.top = `${p.y - vp.top}px`; ringEl.dataset.label = ring.label || ''; }
      else ringEl.hidden = true;
    } else ringEl.hidden = true;
    if (!spot || !tag || spot.offsetParent === null) { tagEl.hidden = true; return; }
    const r = spot.getBoundingClientRect(); tagEl.textContent = `▲ ${tag}`; tagEl.hidden = false;
    const w = tagEl.offsetWidth, h = tagEl.offsetHeight, below = r.bottom + h + 6 <= innerHeight;
    tagEl.textContent = `${below ? '▲' : '▼'} ${tag}`;
    tagEl.style.left = `${Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2))}px`;
    tagEl.style.top = `${below ? r.bottom + 6 : Math.max(6, r.top - h - 6)}px`;
  }
  function afterAction(action, res) {
    const j = game()?.journey;
    if (j?.kind !== 'tutorial') return;
    if (!res?.ok) last = `↺ ${res?.message || '다시 시도하세요'}${res?.hint ? ` · ${res.hint}` : ''}`;
    else if (res.hint) last = `↺ ${res.hint}`;
    else if (actionStep && j.current?.id !== actionStep) { const done = j.goals.flatMap(g => g.steps).find(s => s.id === actionStep); last = `✓ ${done?.title || '이전 단계'} 완료${res.message ? ` · ${res.message}` : ''}`; }
    else if (res.message && !['navigate', 'select_facility', 'inspect_rack'].includes(action.type)) last = res.message;
    actionStep = j.current?.id ?? null;
    render();
  }
  function state() {
    return { active: active(), step: journey()?.current?.id ?? null, bubble: !box.hidden, docked: true, tag: tagEl.hidden ? null : tagEl.textContent, folded,
      spot: spot ? (spot.id ? `#${spot.id}` : spot.getAttribute('data-ws-tab') ? `[data-ws-tab=${spot.dataset.wsTab}]` : spot.className) : null,
      spotSelector: spot ? [...spot.attributes].filter(a => a.name.startsWith('data-') || a.name === 'id').map(a => `${a.name}=${a.value}`).join(' ') : null,
      ring: ring && !ringEl.hidden ? { kind: ring.kind, id: ring.id, label: ring.label } : null, last };
  }
  return { render, position, afterAction, state };
}
