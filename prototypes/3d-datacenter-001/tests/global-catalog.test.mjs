// Phase 6 (Issue #7): the 3D map data comes from the same catalog file as the Python engine.
import test from 'node:test';
import assert from 'node:assert/strict';
import { CATALOG, SITES, LEGACY, siteOf, routeOf, clusters, isKnownCode } from '../src/catalog.js';
import { REQUEST_PATHS, SITE_PATHS, LANDING, activePaths, pathStatus, litSites, focusPath, pathName } from '../src/network-data.js';
import { COUNTRIES, MAP_SITES, createWorldStore } from '../src/world-store.js';
import { placeName, inboxRows, inboxCounts, globalGoal, isGlobal } from '../src/game-view.js';

const near = (a, b, d) => Math.hypot(a[0] - b[0], a[1] - b[1]) <= d;

test('catalog targets: 20+ cities, 12+ countries, 4+ US cities, 3+ European countries, 2+ KR/IN/JP cities', () => {
  const sites = Object.values(SITES), by = c => sites.filter(s => s.country === c).length;
  assert.ok(sites.length >= 20); assert.ok(new Set(sites.map(s => s.country)).size >= 12);
  assert.ok(by('US') >= 4); for (const c of ['KR', 'IN', 'JP']) assert.ok(by(c) >= 2, c);
  assert.ok(new Set(sites.filter(s => s.region === '유럽').map(s => s.country)).size >= 3);
  assert.ok(Object.keys(CATALOG.clients).length >= 30); assert.ok(Object.keys(CATALOG.jobTypes).length >= 8);
  assert.ok(Object.isFrozen(SITES) && Object.isFrozen(SITES['US-SFO']));
});

test('legacy codes keep their names and sea points and alias the catalog city at the same place', () => {
  assert.deepEqual(Object.keys(REQUEST_PATHS).sort(), ['JP', 'SG', 'US']);
  assert.equal(REQUEST_PATHS.US.name, '미국 서부'); assert.equal(REQUEST_PATHS.SG.sea[0][0], 103.95);
  for (const [code, l] of Object.entries(LEGACY)) {
    assert.deepEqual([COUNTRIES[code].lat, COUNTRIES[code].lon], [SITES[l.site].lat, SITES[l.site].lon]);
    assert.equal(siteOf(code).id, l.site);
  }
  assert.deepEqual(Object.keys(COUNTRIES).sort(), ['JP', 'KR', 'SG', 'US']);
  assert.equal(Object.keys(MAP_SITES).length, Object.keys(SITES).length);
});

test('every city route starts at its city and ends at the virtual Busan landing (international) or Ulsan (domestic)', () => {
  const busan = LANDING.BUSAN.lonLat, ulsan = [CATALOG.aidc.lon, CATALOG.aidc.lat];
  for (const [code, s] of Object.entries(SITES)) {
    const r = routeOf(code), pts = r.legs.flatMap(l => l.points);
    assert.ok(near(pts[0], [s.lon, s.lat], 1.6), `${code} starts near the city`);
    if (s.domestic) { assert.equal(r.landing, null); assert.ok(near(pts.at(-1), ulsan, .05), `${code} ends at Ulsan`); assert.equal(SITE_PATHS[code].segments.length, 2); }
    else { assert.equal(r.landing, 'BUSAN'); assert.ok(near(pts.at(-1), busan, .01), `${code} ends at the landing`); }
  }
  // US east and Europe are not drawn as a direct Pacific cable: they have a land leg first.
  for (const code of ['US-NYC', 'US-IAD', 'DE-FRA', 'GB-LON']) assert.equal(SITE_PATHS[code].legs[0].kind, 'land', code);
  assert.ok(SITE_PATHS['DE-FRA'].legs.some(l => l.name?.includes('수에즈')), 'Europe goes west via Suez, not the Pacific');
  assert.equal(clusters().reduce((n, c) => n + c.sites.length, 0), Object.keys(SITES).length);
});

const path = (rid, code, extra = {}) => ({ rid, code, tone: 'incoming', focus: false, link: 'ok', segments: { sea: 'ok', landing: 'ok', backbone: 'ok', aidc: 'ok' }, ...extra });
test('lit cities: only arrived requests, grouped per city with a count; unknown codes ignored', () => {
  assert.deepEqual(activePaths({ game: null }), []);
  const state = { game: { world: { paths: [path(1, 'US-SFO'), path(2, 'US-SFO', { focus: true }), path(3, 'US-SEA'), path(4, 'XX-NOPE'), path(5, 'KR-SEL', { domestic: true })] } } };
  const lit = litSites(state);
  assert.deepEqual(lit.map(s => [s.code, s.count]), [['US-SFO', 2], ['US-SEA', 1], ['KR-SEL', 1]]);
  assert.deepEqual(lit[0].rids, [1, 2]); assert.equal(lit[0].rid, 2, 'the focused request of a city is the one shown');
  assert.equal(lit[2].domestic, true); assert.equal(focusPath(state).code, 'US-SFO');
  assert.match(pathStatus(path(3, 'US-SEA')).message, /시애틀\(미국\) 새 요청 도착/);
  assert.equal(pathName('US'), '미국 서부'); assert.ok(isKnownCode('KR-DJN') && !isKnownCode('__proto__') && !isKnownCode('US-XXX'));
  const store = createWorldStore(); assert.equal(store.selectCountry('US-SEA'), true); assert.equal(store.selectCountry('constructor'), false);
});

const R = (id, stage, extra = {}) => ({ id, stage, code: 'US-SEA', country: '미국', company: 'x', unread: false, terms: { receivedMinute: 540 + id, dueMinute: 700 - id * 10, expiresMinute: 800 - id }, ...extra });
test('inbox filter / sort and the shift goal read only the engine snapshot', () => {
  const game = { mode: 'global', global: { kind: 'shift', shift: 2, shiftCount: 3, title: '혼잡·경합 교대', coachingLabel: '선배 안내 짧게', briefed: true, done: false, arrived: 3, total: 6, closed: 1, success: 1, goal: { minSuccess: 5, maxExpired: 1 } },
    requests: [R(1, 'done'), R(2, 'incoming', { unread: true }), R(3, 'running'), R(4, 'incoming')] };
  assert.ok(isGlobal(game));
  assert.deepEqual(inboxRows(game, 'open', 'arrival').map(r => r.id), [2, 4]);
  assert.deepEqual(inboxRows(game, 'open', 'due').map(r => r.id), [4, 2]);
  assert.deepEqual(inboxRows(game, 'all', 'expires').map(r => r.id), [4, 2, 1, 3]);
  assert.deepEqual(inboxRows(game, 'closed').map(r => r.id), [1]);
  assert.deepEqual(inboxCounts(game), { open: 2, running: 1, closed: 1, all: 4, unread: 1 });
  assert.match(globalGoal(game).title, /도착 3\/6/); assert.match(globalGoal(game).goal, /5건 이상.*만료 1건까지/);
  assert.match(globalGoal({ ...game, global: { ...game.global, briefed: false } }).title, /브리핑/);
  assert.equal(placeName({ site: { city: '시애틀', countryName: '미국' } }), '시애틀 · 미국'); assert.equal(placeName({ code: 'SG', country: '싱가포르' }), '싱가포르');
});
