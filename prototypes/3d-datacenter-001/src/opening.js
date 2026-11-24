// Skippable opening: world traffic -> Korea/Ulsan -> industrial district -> campus -> my desk.
// Pure camera data. Playing it never touches the request, facility or ops state.
import { COUNTRIES } from './world-store.js';
import { toMap } from './geo.js';

const U = COUNTRIES.KR, ulsan = toMap(U.lon, U.lat, .3);
// Korea-centred world view (Issue #3): Ulsan sits in the middle of the visible map area.
export const WORLD_POSE = Object.freeze({ eye: [0, 27, 11.5], target: [0, 0, -2.6] });
export const DESK_POSE = Object.freeze({ eye: [9.3, 2.05, 3.05], target: [9.3, 1.3, -3.4] });
export const NOC_OVERVIEW_POSE = Object.freeze({ eye: [17.5, 8.2, 10.5], target: [9.2, 1.2, -2.2] });
export const OPENING_STORAGE_KEY = 'srs3d.opening.seen.v1';

export const OPENING = Object.freeze([
  { location: 'world', duration: 2.6, from: { eye: [0, 40, 22], target: [0, 0, -1] }, to: { eye: [0, 24, 9], target: [0, 0, -3] },
    title: '세계를 잇는 통신망', sub: '해저 회선과 국내 백본이 울산 AIDC로 모입니다 · 아직 도착한 요청 없음 · 가상 경로, 실제 해저케이블 경로 아님' },
  { location: 'world', duration: 2.3, from: { eye: [0, 24, 9], target: [0, 0, -3] }, to: { eye: [ulsan[0] - .4, 4.4, ulsan[2] + 3.4], target: ulsan },
    title: '대한민국 · 울산', sub: '남구 황성동·용연 권역 · 지도 정밀도는 설명용' },
  { location: 'campus', duration: 2.7, from: { eye: [95, 58, 70], target: [15, 0, 0] }, to: { eye: [46, 28, 42], target: [4, 0, 0] },
    title: '울산미포국가산단 인근', sub: '에너지·화학 설비 사이의 미래 가상 AIDC · 실제 부지·배치·조감도가 아닌 자체 재구성' },
  { location: 'campus', duration: 2.2, from: { eye: [46, 28, 42], target: [4, 0, 0] }, to: { eye: [-1, 7.5, 17], target: [-8, 1, 4.5] },
    title: '울산 AIDC 캠퍼스 · 관제동', sub: '서버동 01과 연결 통로로 이어진 운영 건물' },
  { location: 'noc', duration: 2.4, from: { eye: [9.3, 3.6, 8.5], target: [9.3, 1.6, -4] }, to: DESK_POSE,
    title: '관제동 운영석 03 · 내 자리', sub: '근무를 시작하면 고객 요청이 내 모니터로 들어옵니다' },
]);
export const OPENING_SECONDS = OPENING.reduce((s, k) => s + k.duration, 0);
