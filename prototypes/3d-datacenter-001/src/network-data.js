// ORIGINAL, hand-drawn virtual international network for the game (Issue #3).
// Inspired only by the general idea of public submarine-cable maps (many sea routes meeting at
// coastal landing stations). No coordinates, names or graphics are copied from TeleGeography or any
// operator; waypoints are rough sea paths drawn for readability. Not real cables, owners or routes.
import { CATALOG, LEGACY, SITES, siteOf, routeOf } from './catalog.js';

function freeze(v) { Object.values(v).forEach(x => { if (x && typeof x === 'object') freeze(x); }); return Object.freeze(v); }

// Phase 6: landing stations, legacy country paths and every city route come from the single catalog.
export const LANDING = freeze(structuredClone(CATALOG.landings));

// Background virtual links: drawn thin and dark, never animated.
export const BACKGROUND_LINKS = freeze([
  { id: 'v-pac-1', path: [[129.05, 35.08], [131.5, 32.4], [136, 32.8], [141, 34], [150, 35], [165, 33], [180, 29], [-158, 21.3], [-140, 30], [-122.6, 37.7]] },
  { id: 'v-pac-2', path: [[140.8, 35.5], [150, 40], [165, 45], [180, 47], [-160, 48], [-140, 47], [-124.2, 45.6]] },
  { id: 'v-ecs-1', path: [[129, 34.8], [126, 33], [123.5, 31.5], [121.9, 31.2]] },
  { id: 'v-phl-1', path: [[121.8, 24.9], [122.6, 20], [124.5, 16], [130, 14.5], [144.7, 13.4]] },
  { id: 'v-scs-1', path: [[114.2, 22.2], [112, 15], [109.5, 8], [105, 2.6], [104, 1.3]] },
  { id: 'v-ind-1', path: [[103.9, 1.25], [98, 5.5], [90, 7], [80.3, 5.6], [72, 10], [60, 13], [52, 13], [43.5, 12.6], [38, 20], [33.5, 27.5], [32.5, 31.3], [25, 33.5], [15, 36.5], [8, 38.5], [5.4, 43.2]] },
  { id: 'v-aus-1', path: [[104, 1.2], [105.6, -6.6], [110, -15], [113.5, -25], [115.7, -31.9]] },
  { id: 'v-aus-2', path: [[151.3, -33.9], [156, -25], [160, -10], [150, 5], [144.7, 13.4], [140, 25], [139.9, 35]] },
  { id: 'v-afr-1', path: [[72.8, 19], [65, 12], [52, 3], [40.5, -4.1]] },
  { id: 'v-atl-1', path: [[-74, 40.4], [-60, 42], [-40, 47], [-20, 50], [-8, 50.5], [-4.5, 50.3]] },
  { id: 'v-atl-2', path: [[-38.5, -3.7], [-25, -2], [-10, 2], [3.4, 6.3]] },
  { id: 'v-atl-3', path: [[-9.2, 38.7], [-17, 28], [-17.6, 14.7], [-8, 4.4], [3.4, 6.3]] },
  { id: 'v-pac-3', path: [[-118.3, 33.7], [-110, 22], [-95, 12], [-81, 6], [-80.6, -2.2]] },
  { id: 'v-kor-jp', path: [[129.05, 35.08], [130.4, 33.6]] },
]);

// Request paths: submarine segment -> coastal landing station -> domestic terrestrial backbone -> Ulsan AIDC.
// The cable never touches the AIDC building itself. These are drawn for every customer site but stay dark:
// a path is lit only while the engine snapshot reports a request from that country (Issue #5).
const SEGMENTS = Object.freeze([
  { id: 'sea', name: '해저 구간 (가상)' }, { id: 'landing', name: '부산 권역 육양국' },
  { id: 'backbone', name: '국내 지상망' }, { id: 'aidc', name: '울산 AIDC · 서버동' },
]);
// Legacy country paths (chapters 1-5, older saves): same names and sea points as before, now read from the catalog.
export const REQUEST_PATHS = freeze(Object.fromEntries(Object.entries(LEGACY).map(([code, l]) => [code,
  { name: l.name, landing: 'BUSAN', segments: SEGMENTS, sea: l.sea, site: l.site }])));
// Phase 6: one route per catalog city (siteId, e.g. US-SFO / US-SEA). Domestic sites run on the domestic backbone only.
const DOMESTIC_SEGMENTS = Object.freeze([{ id: 'backbone', name: '국내 지상망' }, { id: 'aidc', name: '울산 AIDC · 서버동' }]);
export const SITE_PATHS = freeze(Object.fromEntries(Object.entries(SITES).map(([code, s]) => { const r = routeOf(code);
  return [code, { name: s.city, country: s.countryName, cluster: s.cluster, domestic: !!s.domestic, landing: r.landing,
    segments: s.domestic ? DOMESTIC_SEGMENTS : SEGMENTS, legs: r.legs }]; })));
const known = code => Object.hasOwn(REQUEST_PATHS, code) || Object.hasOwn(SITE_PATHS, code);
export function pathName(code) { return REQUEST_PATHS[code]?.name || (SITE_PATHS[code] ? `${SITE_PATHS[code].name}(${SITE_PATHS[code].country})` : code); }

// Paths lit by the engine snapshot (game.world.paths). No game, no request -> nothing is lit, whatever
// country the player selected or the opening shows.
export function activePaths(state) {
  const paths = state?.game?.world?.paths;
  return Array.isArray(paths) ? paths.filter(p => known(p.code)) : [];
}

const MESSAGE = {
  fault: '국제 구간·육양국·국내망 정상 · 울산 AIDC 서버 장애 (네트워크 문제 아님)',
  repairing: '국제 구간 정상 · AIDC 서버 복구/작업 이전 준비 중',
};
// What the transit is known to be, from the engine evidence the player has opened (Issue #6). Before a network
// diagnosis it is only a symptom; no single international hop is blamed by the display.
export const CAUSE_TEXT = Object.freeze({
  symptom: '전송 이상 · 원인 미확인 (진단 전)', primary_down: '주 통신 경로 신호 없음 · 백업 경로 대기',
  congested: '경로 연결됨 · 대역폭 한계', rerouted: '백업 경로로 우회 전송 중', recovering: '조치 성공 · 복구 준비 중', ok: '',
});
// One path's display status. Every space reads the same derived value.
export function pathStatus(path) {
  const seg = path.segments || {}, aidc = seg.aidc || 'ok', link = seg.sea === 'degraded' ? 'degraded' : 'ok';
  const cause = path.link || (link === 'degraded' ? 'symptom' : 'ok'), note = path.linkNote || CAUSE_TEXT[cause] || '';
  const name = pathName(path.code), domestic = !!(path.domestic || SITE_PATHS[path.code]?.domestic);
  return { code: path.code, rid: path.rid, focus: !!path.focus, tone: path.tone, aidc, link, cause, note, domestic, site: siteOf(path.code)?.id ?? null,
    segments: { sea: seg.sea || 'ok', landing: seg.landing || 'ok', backbone: seg.backbone || 'ok', aidc },
    packets: true, message: aidc !== 'ok' ? MESSAGE[aidc] : cause !== 'ok' ? `${name} 경로 · ${note}`
      : (path.tone === 'incoming' ? `${name} 새 요청 도착 · 경로 확인` : `${name} 경로 정상 · 작업 트래픽 전송 중`) };
}
// Lit paths grouped per city: two requests from one city are one lit route with a "2건" badge (Issue #7).
export function litSites(state) {
  const out = new Map();
  for (const p of activePaths(state)) { const s = pathStatus(p), cur = out.get(p.code);
    if (!cur) out.set(p.code, { ...s, rids: [p.rid], count: 1 });
    else { cur.rids.push(p.rid); cur.count++; if (s.focus) Object.assign(cur, { ...s, rids: cur.rids, count: cur.count }); } }
  return [...out.values()];
}
// The path the panels describe: the focused request if it is lit, else the first lit path.
export function focusPath(state) {
  const all = activePaths(state);
  const p = all.find(x => x.focus) || all[0];
  return p ? pathStatus(p) : null;
}
