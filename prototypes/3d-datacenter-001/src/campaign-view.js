// Pure campaign views (Issue #6, Phase 5). No DOM, Three.js, storage or rules: the Python engine already decided
// every chapter state, objective, unlock, result and score in the snapshot; these helpers only choose wording and
// which engine fields a screen shows. Hints shrink chapter by chapter, and chapter 5 gives no "where".

// Player-facing step titles for each engine step (story.uiStep). Unknown steps fall back to the engine objective.
const STEP_TITLE = Object.freeze({
  c2_briefing: '선배 브리핑', c2_requests: '두 요청서 읽기', c2_review: '배정안 비교', c2_allocate: '처리 결정',
  c2_progress: '작업 진행', c2_finish: '마무리', c2_done: '장 종료',
  c3_briefing: '선배 브리핑', c3_a_start: '미션 A · 작업 시작', c3_a_incident: '미션 A · 작업 진행', c3_a_diagnose: '미션 A · 네트워크 진단',
  c3_a_respond: '미션 A · 원인에 맞는 조치', c3_a_finish: '미션 A · 마무리', c3_b_start: '미션 B · 작업 시작', c3_b_incident: '미션 B · 작업 진행',
  c3_b_diagnose: '미션 B · 네트워크 진단', c3_b_respond: '미션 B · 원인에 맞는 조치', c3_b_finish: '미션 B · 마무리', c3_done: '장 종료',
  c3b_briefing: '선배 브리핑', c3b_a_start: '미션 A · 작업 시작', c3b_a_fault: '미션 A · 작업 진행', c3b_a_diagnose: '미션 A · 장비 진단',
  c3b_a_respond: '미션 A · 복구 또는 이전', c3b_a_finish: '미션 A · 마무리', c3b_b_start: '미션 B · 작업 시작', c3b_b_fault: '미션 B · 작업 진행',
  c3b_b_diagnose: '미션 B · 장비 진단', c3b_b_respond: '미션 B · 복구 또는 이전', c3b_b_finish: '미션 B · 마무리', c3b_done: '장 종료',
  t_structure: 'Stage 1 · 시스템 구조 관찰', t_tool: 'Stage 2 · 진단 도구 선택', t_assemble: 'Stage 3 · 명령어 조립',
  t_terminal: 'Stage 4 · 터미널 직접 입력', t_independent: 'Stage 5 · 독립 진단', t_done: '연수 완료',
});
// Where to act. Chapter 2 names every place, chapters 3-4 name only the tab, chapter 5 names none for Stage 5.
const STEP_WHERE = Object.freeze({
  c2_briefing: '화면 아래 선배 대화', c2_requests: '내 모니터 → 요청함 · 두 요청 각각 [요청서 열기]',
  c2_review: '내 모니터 → 배정 계획 · 두 요청 각각 배정안 선택(미점유)', c2_allocate: '배정 계획에서 고른 뒤 서버동 01의 그 랙에서 시작 · 요청함의 대기/거절도 선택지',
  c2_progress: '위쪽 ⏩ 시간 · 서버동 랙의 고객 색', c2_finish: '위쪽 ⏩ 시간',
  c3_briefing: '화면 아래 선배 대화', c3_a_start: '요청함 → 배정 계획 → 서버동 01', c3_b_start: '요청함 → 배정 계획 → 서버동 01',
  c3_a_incident: '⏩ 시간', c3_b_incident: '⏩ 시간', c3_a_diagnose: '내 모니터 → 네트워크 진단', c3_b_diagnose: '내 모니터 → 네트워크 진단',
  c3_a_respond: '네트워크 진단 탭', c3_b_respond: '네트워크 진단 탭', c3_a_finish: '⏩ 시간', c3_b_finish: '⏩ 시간',
  c3b_briefing: '화면 아래 선배 대화', c3b_a_diagnose: '장비 진단 탭', c3b_b_diagnose: '장비 진단 탭',
  t_structure: '내 모니터 → 연수', t_tool: '내 모니터 → 연수', t_assemble: '내 모니터 → 연수', t_terminal: '내 모니터 → 연수',
});
export const BRIEFING_EVENTS = Object.freeze(['c2_briefing', 'c3_briefing', 'c3b_briefing']);

export function chapterKey(game) { return game?.story?.chapterKey ?? null; }
export function isLaterChapter(game) { return game?.mode === 'story' && !!game.story && game.story.chapterKey !== 1; }

// Goal line for chapters 2-5 (chapter 1 and the tutorial keep their Phase 4 goal views).
export function chapterGoal(game) {
  if (!isLaterChapter(game)) return null;
  const st = game.story, step = st.uiStep;
  const unit = st.chapterKey === 'lab' ? 'Stage' : '업무';
  return { title: STEP_TITLE[step] || st.chapter.title, what: st.objective, where: STEP_WHERE[step] || '',
    label: `${st.chapter.heading} · ${unit} ${st.jobsDone}/${st.jobsTotal}`, state: st.chapter.state };
}

// The senior's pages for the current engine event, shown once (engine dialogue_seen). The last page of a briefing
// is the real engine action (confirm the briefing); any other last page only records that it was read.
export function talkFor(game) {
  if (!isLaterChapter(game)) return null;
  const d = game.story.dialogue;
  if (!d || !d.pages?.length) return null;
  // A briefing stays on screen until the engine has confirmed it, even if its pages were marked read before.
  const briefing = BRIEFING_EVENTS.includes(d.event) && game.story.uiStep === d.event;
  if (d.seen && !briefing) return null;
  return { key: `${game.id}:${d.event}`, event: d.event, briefing, pages: d.pages.map(([role, speaker, text]) => [role, text, speaker]) };
}

// Rows for a chapter result screen, read straight from the engine's result summary.
export function resultRows(story) {
  const r = story?.result, key = story?.chapterKey; if (!r) return [];
  if (key === 1 || key === 'tutorial') return (r.summary || []).map(([k, v]) => [k, v]);
  if (key === 2) { const s = r.summary || {}; return [['미션 판정', s.verdict], ['종합 평가', r.overall != null ? `${r.overall}/100` : '미확정'], ['실행 방식', s.arrangement], ['자원', s.resources], ['전략', s.strategy]].filter(([, v]) => v != null); }
  if (key === 3 || key === '3b') { const s = r.summary || {}; return [['미션 판정', s.verdict], ...(s.table || []).map(row => [`미션 ${row[0]}`, row.slice(1).join(' · ')])]; }
  if (key === 'lab') return [...(r.rows || []).map(([k, v, d]) => [k, `${v} · ${d}`]), ['Stage 5', `증거 ${r.stage5?.evidence ?? 0}건 · 원인 판단 ${r.stage5?.cause_attempts ?? 0}회 · 조치 ${r.stage5?.recovered_by ?? '-'} · 고객 작업 ${r.stage5?.job ?? '-'}`]];
  return [];
}
export function resultNotes(story) {
  const r = story?.result, key = story?.chapterKey; if (!r) return [];
  if (key === 2) return [...(r.decisions || []), ...(r.highlights || [])];
  if (key === 3 || key === '3b') return r.summary?.mentor || r.mentor || [];
  if (key === 'lab') return [r.status ? `고객 작업(요청 #${r.status.rid}) 현재 상태: ${r.status.job_label} · ${r.status.remaining}` : null, r.notice, r.outro].filter(Boolean);
  return [];
}
export function missionOf(story) {
  if (!story?.result) return null;
  if (story.chapterKey === 1 || story.chapterKey === 'tutorial') return story.chapter.state === 'cleared' ? 'success' : 'failed';
  if (story.chapterKey === 'lab') return story.chapter.state === 'cleared' ? 'success' : 'in_progress';
  return story.result.mission;
}
// Chapter 3/4 card rows (engine chapter3_card / chapter3b_card) as [label, value] pairs.
export function cardRows(card) { return (card?.rows || []).map(r => [String(r[0]), String(r[1])]); }
export const LAB_STAGES = Object.freeze(['structure', 'tool', 'assemble', 'terminal', 'independent']);
