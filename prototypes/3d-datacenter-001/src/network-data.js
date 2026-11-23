// ORIGINAL, hand-drawn virtual international network for the game (Issue #3).
// Inspired only by the general idea of public submarine-cable maps (many sea routes meeting at
// coastal landing stations). No coordinates, names or graphics are copied from TeleGeography or any
// operator; waypoints are rough sea paths drawn for readability. Not real cables, owners or routes.
function freeze(v) { Object.values(v).forEach(x => { if (x && typeof x === 'object') freeze(x); }); return Object.freeze(v); }

export const LANDING = freeze({
  BUSAN: { name: '부산 권역 육양국 (가상)', lonLat: [129.05, 35.08] },
});

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

// The SG request's path: submarine segment -> coastal landing station -> domestic terrestrial
// backbone -> Ulsan AIDC. The cable never touches the AIDC building itself.
export const REQUEST_PATHS = freeze({
  SG: {
    sea: [[103.95, 1.3], [106.5, 4.5], [110.5, 9], [114.5, 15], [119.6, 20.2], [122.8, 24.6], [125.4, 30], [128.3, 33.7], [129.05, 35.08]],
    landing: 'BUSAN',
    segments: [
      { id: 'sea', name: '해저 구간 (가상)' },
      { id: 'landing', name: '부산 권역 육양국' },
      { id: 'backbone', name: '국내 지상망' },
      { id: 'aidc', name: '울산 AIDC · 서버동 업링크' },
    ],
  },
});

// Shared status of the request path, derived only from the request phase (all spaces read the same thing).
export function requestPathStatus(state) {
  const p = state.request.phase;
  const tone = ['new', 'reviewed'].includes(p) ? 'incoming' : ['completed', 'reported'].includes(p) ? 'done' : 'active';
  const aidc = p === 'fault' ? 'fault' : p === 'repairing' ? 'repairing' : p === 'awaiting' ? 'check' : 'ok';
  return { country: state.request.country, tone, packets: tone !== 'done', aidc,
    segments: { sea: 'ok', landing: 'ok', backbone: 'ok', aidc },
    message: aidc === 'fault' ? '국제 구간 정상 · 울산 AIDC 서버동 01 업링크 단절' : aidc === 'repairing' ? 'AIDC 내부 업링크 복구 중' : aidc === 'check' ? '복구 처리됨 · 사후 확인 대기' : tone === 'incoming' ? '싱가포르 새 요청 도착 중' : tone === 'done' ? '처리 완료 · 경로 정상' : '경로 정상 · 작업 트래픽 전송 중' };
}
