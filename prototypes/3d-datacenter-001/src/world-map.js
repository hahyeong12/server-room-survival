// Korea-centred world map with a dim background network (Issue #3). Customer routes stay dark until the engine
// reports a request that actually arrived from that city; only those routes are lit (Issue #5).
// Phase 6 (Issue #7): one marker and one virtual route per catalog city (siteId, e.g. US-SFO / US-SEA). The legacy
// codes SG/JP/US of chapters 1-5 are aliases of the catalog city at the same place (same marker). Nearby cities are
// grouped by a small cluster label; a lit city gets a stacked request badge ("요청 #N · 2건") that can be clicked.
import * as THREE from 'three';
import landSource from './assets/land.geojson?raw';
import { COUNTRIES, MAP_SITES } from './world-store.js';
import { CLUSTERS, LEGACY } from './catalog.js';
import { SCALE, HALF_WIDTH, toMap, unwrap, copyOffsets } from './geo.js';
import { LANDING, BACKGROUND_LINKS, REQUEST_PATHS, SITE_PATHS, litSites, focusPath, CAUSE_TEXT, pathName } from './network-data.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const TONE = { incoming: 0xf3c37b, active: 0x6fe7d2, done: 0x5fb9a9, fault: 0xff657d, repairing: 0xf8be68, check: 0x89baff, ok: 0x6fe7d2, degraded: 0xff9a5c, idle: 0x2c4a5c };
const NEUTRAL = 0x6d8ea3;
const Z_TOP = -84 * SCALE, Z_BOTTOM = 56 * SCALE;

function label(root, text, sub, x, y, z, width = 4, color = '#afd7e4') {
  const canvas = document.createElement('canvas'); canvas.width = 768; canvas.height = 192; const c = canvas.getContext('2d');
  c.fillStyle = '#0c1928dd'; c.fillRect(0, 0, 768, 192); c.fillStyle = color; c.fillRect(0, 0, 5, 192);
  c.font = '500 56px Consolas, "Malgun Gothic", monospace'; c.fillText(text, 26, 80); c.fillStyle = '#a9bccb'; c.font = '30px Consolas, "Malgun Gothic", monospace'; c.fillText(sub, 27, 142);
  const tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, toneMapped: false })); sprite.position.set(x, y, z); sprite.scale.set(width, width / 4, 1); sprite.renderOrder = 5; root.add(sprite); return sprite;
}
// Cluster anchors: where a cluster's label and its stacked request badges sit (map units offset from the centroid).
const CLUSTER_OFFSET = { 'us-west': [1.6, 1.3, -1.9], 'us-east': [-1.4, 1.3, -2.2], 'us-central': [0.4, 1.3, 1.6], in: [-2.2, 1.3, 1.6], kr: [-2.6, 1.9, -1.9],
  jp: [2.6, 1.3, -1.6], eu: [-1.2, 1.3, -2.4], sea: [-2.8, 1.3, 1.6], tw: [1.8, 1.3, 0.9], au: [2.2, 1.3, 1.2] };

export function createWorldMap() {
  const group = new THREE.Group(), pickables = [], markers = {};
  const clip = [new THREE.Plane(V(-1, 0, 0), HALF_WIDTH), new THREE.Plane(V(1, 0, 0), HALF_WIDTH)];
  const base = new THREE.Mesh(new THREE.BoxGeometry(HALF_WIDTH * 2 + 1.4, .5, Z_BOTTOM - Z_TOP + 1.6), new THREE.MeshStandardMaterial({ color: 0x0f1d2e, roughness: .8, metalness: .35 }));
  base.position.set(0, -.3, (Z_TOP + Z_BOTTOM) / 2); base.receiveShadow = true; group.add(base);
  const landMaterial = new THREE.MeshStandardMaterial({ color: 0x29495a, metalness: .34, roughness: .64, clippingPlanes: clip });
  const coastMaterial = new THREE.LineBasicMaterial({ color: 0x527f8a, transparent: true, opacity: .7, clippingPlanes: clip });
  const land = JSON.parse(landSource);
  for (const feature of land.features) {
    const polygons = feature.geometry.type === 'MultiPolygon' ? feature.geometry.coordinates : [feature.geometry.coordinates];
    for (const polygon of polygons) {
      if (polygon[0].every(([, lat]) => lat < -58)) continue; // Antarctica: outside the play area
      const rings = polygon.map(ring => unwrap(ring)), outer = rings[0];
      for (const off of copyOffsets(outer.map(p => p[0]))) {
        const shape = new THREE.Shape(outer.map(([x, lat]) => new THREE.Vector2((x + off) * SCALE, lat * SCALE)));
        for (const hole of rings.slice(1)) shape.holes.push(new THREE.Path(hole.map(([x, lat]) => new THREE.Vector2((x + off) * SCALE, lat * SCALE))));
        const mesh = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: .16, bevelEnabled: false }), landMaterial); mesh.rotation.x = -Math.PI / 2; mesh.position.y = .04; mesh.receiveShadow = true; group.add(mesh);
        group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(outer.map(([x, lat]) => V((x + off) * SCALE, .21, -lat * SCALE))), coastMaterial));
      }
    }
  }
  const gridMat = new THREE.LineBasicMaterial({ color: 0x223a4b, transparent: true, opacity: .55 });
  for (let k = -5; k <= 5; k++) { const x = k * 30 * SCALE; group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([V(x, .015, Z_TOP), V(x, .015, Z_BOTTOM)]), gridMat)); }
  for (let lat = -40; lat <= 80; lat += 30) { const z = -lat * SCALE; group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([V(-HALF_WIDTH, .015, z), V(HALF_WIDTH, .015, z)]), gridMat)); }

  // Background virtual network: many thin, dark, static lines.
  const bgMat = new THREE.LineBasicMaterial({ color: 0x46708a, transparent: true, opacity: .55, clippingPlanes: clip });
  const polyline = (path, y) => { const u = unwrap(path); return copyOffsets(u.map(p => p[0])).map(off => u.map(([x, lat]) => V((x + off) * SCALE, y, -lat * SCALE))); };
  for (const link of BACKGROUND_LINKS) for (const pts of polyline(link.path, .23)) group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), bgMat));
  const nodeGeo = new THREE.SphereGeometry(.07, 8, 6), nodeMat = new THREE.MeshBasicMaterial({ color: 0x4f7890, toneMapped: false });
  for (const link of BACKGROUND_LINKS) for (const end of [link.path[0], link.path.at(-1)]) { const n = new THREE.Mesh(nodeGeo, nodeMat); n.position.set(...toMap(end[0], end[1], .24)); group.add(n); }

  // Ulsan AIDC marker (always) and one small neutral marker per catalog city. No city looks active before a request.
  const sphereGeo = new THREE.SphereGeometry(.17, 16, 12), ringGeo = new THREE.TorusGeometry(.44, .025, 6, 40);
  const siteGeo = new THREE.SphereGeometry(.12, 12, 10), siteRing = new THREE.TorusGeometry(.3, .02, 6, 32), proxyGeo = new THREE.SphereGeometry(.32, 10, 8);
  {
    const c = COUNTRIES.KR, point = V(...toMap(c.lon, c.lat, .42)); point.set(point.x + .32, 1.05, point.z - .28);
    const mat = new THREE.MeshBasicMaterial({ color: 0x81f1da, toneMapped: false });
    const node = new THREE.Mesh(sphereGeo, mat); node.position.copy(point); group.add(node);
    const ring = new THREE.Mesh(ringGeo, mat); ring.rotation.x = Math.PI / 2; ring.position.copy(point); group.add(ring);
    const proxy = new THREE.Mesh(new THREE.SphereGeometry(.5, 10, 8), new THREE.MeshBasicMaterial({ visible: false })); proxy.position.copy(point); proxy.userData.pickId = 'country:KR'; group.add(proxy); pickables.push(proxy);
    label(group, 'ULSAN AIDC', '남구 황성동·용연 (가상)', point.x - 2.4, 1.9, point.z - 1.5, 4.6, '#8af0d4');
    markers.KR = { node, ring, point, mat, labelAt: V(point.x - 2.4, 2.85, point.z - 1.5) };
  }
  const clusterSites = {};
  for (const [id, s] of Object.entries(MAP_SITES)) {
    const point = V(...toMap(s.lon, s.lat, .34));
    const mat = new THREE.MeshBasicMaterial({ color: NEUTRAL, toneMapped: false });
    const node = new THREE.Mesh(siteGeo, mat); node.position.copy(point); group.add(node);
    const ring = new THREE.Mesh(siteRing, mat); ring.rotation.x = Math.PI / 2; ring.position.copy(point); group.add(ring);
    const proxy = new THREE.Mesh(proxyGeo, new THREE.MeshBasicMaterial({ visible: false })); proxy.position.copy(point); proxy.userData.pickId = `country:${id}`; group.add(proxy); pickables.push(proxy);
    markers[id] = { node, ring, point, mat, cluster: s.cluster, labelAt: point.clone() };
    (clusterSites[s.cluster] ||= []).push(id);
  }
  // Legacy codes share the marker of their catalog city (one physical place, one marker).
  for (const [code, l] of Object.entries(LEGACY)) markers[code] = markers[l.site];
  // Cluster labels: the region name and how many virtual customer cities it holds (simple source list in the panel).
  const anchors = {};
  for (const [cluster, ids] of Object.entries(clusterSites)) {
    const c = ids.reduce((a, id) => a.add(markers[id].point), V(0, 0, 0)).multiplyScalar(1 / ids.length), o = CLUSTER_OFFSET[cluster] || [1.5, 1.3, -1.5];
    anchors[cluster] = V(c.x + o[0], o[1], c.z + o[2]);
    if (ids.length > 1 || cluster === 'us-central') label(group, CLUSTERS[cluster], `가상 고객 도시 ${ids.length}곳`, anchors[cluster].x, .75, anchors[cluster].z, 2.6, '#7f9fb2');
  }

  // Shared landing station and the domestic backbone hop to the AIDC: always drawn, dim until a route is lit.
  const kr = markers.KR.point;
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([V(...toMap(COUNTRIES.KR.lon, COUNTRIES.KR.lat, .22)), kr]), new THREE.LineBasicMaterial({ color: 0x81f1da, transparent: true, opacity: .5 })));
  const landing = V(...toMap(...LANDING.BUSAN.lonLat, .26));
  const landingNode = new THREE.Mesh(new THREE.CylinderGeometry(.13, .13, .14, 12), new THREE.MeshBasicMaterial({ color: 0xd8f3ff, toneMapped: false })); landingNode.position.copy(landing); group.add(landingNode);
  label(group, 'LANDING · BUSAN', '부산 권역 육양국 (가상)', landing.x + 2.1, .9, landing.z + 1.7, 3.6, '#c9e4f0');
  const hopMid = landing.clone().lerp(kr, .5); hopMid.y = 1.25;
  const hopCurve = new THREE.QuadraticBezierCurve3(landing, hopMid, kr), hopMat = new THREE.MeshBasicMaterial({ color: TONE.idle, toneMapped: false });
  group.add(new THREE.Mesh(new THREE.TubeGeometry(hopCurve, 30, .035, 6, false), hopMat));

  // One route per legacy code and per city: land legs (metro / backhaul / domestic backbone) thin, sea legs thicker.
  const packetGeo = new THREE.SphereGeometry(.075, 8, 6), packetMat = new THREE.MeshBasicMaterial({ color: 0xfff6dd, toneMapped: false });
  const paths = {};
  function routeCurve(points, y) { const pts = polyline(points, y)[0]; return pts.length > 1 ? new THREE.CatmullRomCurve3(pts, false, 'centripetal', .2) : null; }
  function addRoute(code, legs, domestic) {
    const mat = new THREE.MeshBasicMaterial({ color: TONE.idle, transparent: true, opacity: .55, toneMapped: false });
    const landMat = new THREE.MeshBasicMaterial({ color: TONE.idle, transparent: true, opacity: .4, toneMapped: false });
    const all = [];
    for (const leg of legs) {
      const curve = routeCurve(leg.points, leg.kind === 'land' ? .3 : .26); if (!curve) continue;
      group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, leg.kind === 'land' ? 40 : 140, leg.kind === 'land' ? .022 : .04, 6, false), leg.kind === 'land' ? landMat : mat));
      all.push(...leg.points);
    }
    const curve = routeCurve(domestic ? [...all, [COUNTRIES.KR.lon, COUNTRIES.KR.lat]] : all, .28);
    const packets = []; for (let k = 0; k < (domestic ? 4 : 9); k++) { const m = new THREE.Mesh(packetGeo, packetMat); m.visible = false; group.add(m); packets.push({ m, offset: k / (domestic ? 4 : 9) }); }
    // Request badge: created hidden, drawn only when lit; a hidden badge is never picked.
    const badge = new THREE.Sprite(new THREE.SpriteMaterial({ depthTest: false, toneMapped: false, transparent: true })); badge.scale.set(3.4, .8, 1); badge.renderOrder = 6; badge.visible = false;
    badge.userData.pickId = `country:${code}`; const cast = badge.raycast.bind(badge); badge.raycast = (r, out) => { if (badge.visible) cast(r, out); };
    group.add(badge); pickables.push(badge);
    paths[code] = { curve, mat, landMat, packets, badge, canvas: null, tex: null, key: '', domestic, marker: markers[code] };
  }
  for (const [code, def] of Object.entries(REQUEST_PATHS)) addRoute(code, [{ kind: 'sea', points: def.sea }], false);
  for (const [code, def] of Object.entries(SITE_PATHS)) addRoute(code, def.legs, def.domestic);

  function drawRequestBadge(p, s, code) {
    if (!p.canvas) { p.canvas = document.createElement('canvas'); p.canvas.width = 640; p.canvas.height = 150; p.tex = new THREE.CanvasTexture(p.canvas); p.tex.colorSpace = THREE.SRGBColorSpace; p.badge.material.map = p.tex; p.badge.material.needsUpdate = true; }
    const c = p.canvas.getContext('2d'), col = s.aidc !== 'ok' ? '#ff8a9a' : s.link !== 'ok' ? '#ffb27a' : s.tone === 'incoming' ? '#f4ca8d' : '#8af0d4';
    c.clearRect(0, 0, 640, 150); c.fillStyle = '#10161fee'; c.fillRect(0, 0, 640, 150); c.fillStyle = col; c.fillRect(0, 0, 8, 150);
    c.font = '600 42px Consolas, "Malgun Gothic", monospace';
    c.fillText(`${code} · 요청 #${s.rid}${s.count > 1 ? ` 외 ${s.count - 1}건` : ''}`, 28, 60);
    c.font = '28px "Malgun Gothic", sans-serif'; c.fillStyle = '#c8d6e0';
    c.fillText(s.aidc !== 'ok' ? 'AIDC 서버 문제 · 회선 정상' : s.cause !== 'ok' ? CAUSE_TEXT[s.cause] : `${pathName(code)} · ${s.count > 1 ? `${s.count}건 · ` : ''}${s.tone === 'incoming' ? '새 요청 도착' : '작업 중'}`, 30, 114); p.tex.needsUpdate = true;
  }
  const badgeCanvas = document.createElement('canvas'); badgeCanvas.width = 640; badgeCanvas.height = 160;
  const badgeTex = new THREE.CanvasTexture(badgeCanvas); badgeTex.colorSpace = THREE.SRGBColorSpace;
  const badge = new THREE.Sprite(new THREE.SpriteMaterial({ map: badgeTex, depthTest: false, toneMapped: false })); badge.scale.set(4.2, 1.05, 1); badge.position.set(kr.x + 2.6, 2.2, kr.z + .4); badge.renderOrder = 6; badge.visible = false; group.add(badge);
  let badgeKey = '', visual = null;
  function drawBadge(kind, cause = 'symptom') {
    const c = badgeCanvas.getContext('2d'), col = kind === 'fault' ? '#ff8a9a' : kind === 'repairing' ? '#ffc777' : '#ffb27a';
    c.clearRect(0, 0, 640, 160); c.fillStyle = '#140c12ee'; c.fillRect(0, 0, 640, 160); c.strokeStyle = col; c.lineWidth = 5; c.strokeRect(3, 3, 634, 154);
    c.fillStyle = col; c.font = 'bold 64px "Segoe UI Symbol", sans-serif'; c.fillText(kind === 'repairing' ? '🛠' : '⚠', 22, 104);
    c.font = '600 38px "Malgun Gothic", sans-serif'; c.fillText(kind === 'fault' ? 'AIDC 서버 장애' : kind === 'repairing' ? 'AIDC 서버 복구 중' : cause === 'symptom' ? '전송 이상 · 원인 미확인' : '고객 전송 경로 이상', 110, 72);
    c.font = '26px "Malgun Gothic", sans-serif'; c.fillStyle = '#c8d6e0'; c.fillText(kind === 'degraded' ? (cause === 'symptom' ? '내 모니터 [진단]에서 근거 확인 · AIDC 내부 정상' : CAUSE_TEXT[cause]) : '국제 구간·육양국·국내망은 정상', 112, 122); badgeTex.needsUpdate = true;
  }
  const toneOf = s => s.link !== 'ok' ? TONE.degraded : s.cause === 'rerouted' ? TONE.check : TONE[s.tone];

  function update(time, state, { reducedMotion = false } = {}) {
    const litList = litSites(state), lit = Object.fromEntries(litList.map(s => [s.code, s])), focus = focusPath(state);
    bgMat.opacity = reducedMotion ? .5 : .46 + .08 * Math.sin(time * .5);
    // Stack the badges of lit cities that share a cluster so they never cover each other.
    const stack = {};
    for (const s of litList) { const cl = markers[s.code]?.cluster ?? 'legacy:' + s.code; s.slot = stack[cl] = (stack[cl] ?? -1) + 1; }
    const markerTone = new Map();
    for (const [code, p] of Object.entries(paths)) {
      const s = lit[code];
      p.badge.visible = !!s;
      if (!s) { p.mat.color.setHex(TONE.idle); p.mat.opacity = .5; p.landMat.color.setHex(TONE.idle); p.landMat.opacity = .4; p.packets.forEach(x => { x.m.visible = false; }); continue; }
      const tone = toneOf(s);
      p.mat.color.setHex(tone); p.mat.opacity = s.focus ? .95 : .7; p.landMat.color.setHex(tone); p.landMat.opacity = s.focus ? .9 : .65;
      markerTone.set(p.marker, { tone, incoming: s.tone === 'incoming' });
      const anchor = anchors[p.marker.cluster] || V(p.marker.point.x + 1.8, 1.3, p.marker.point.z - 1.4);
      p.badge.position.set(anchor.x, anchor.y + .95 * s.slot, anchor.z);
      const key = `${s.rid}:${s.count}:${s.tone}:${s.aidc}:${s.link}:${s.cause}`; if (key !== p.key) { p.key = key; drawRequestBadge(p, s, code); }
      p.packets.forEach(({ m: dot, offset }) => {
        const u = reducedMotion ? offset : (time * .07 + offset) % 1, onHop = !p.domestic && u > .88;
        dot.visible = !!p.curve && !(onHop && s.aidc !== 'ok') && s.link === 'ok';
        if (dot.visible) dot.position.copy(onHop ? hopCurve.getPoint((u - .88) / .12) : p.curve.getPoint(p.domestic ? u : u / .88));
      });
    }
    for (const m of new Set(Object.values(markers))) {
      if (m === markers.KR) continue;
      const t = markerTone.get(m);
      m.mat.color.setHex(t ? t.tone : NEUTRAL);
      m.ring.scale.setScalar(t ? 1 + (reducedMotion ? 0 : (t.incoming ? .3 : .1) * (.5 + .5 * Math.sin(time * 3))) : 1);
    }
    const intl = focus && !focus.domestic ? focus : litList.find(s => !s.domestic) || null, any = !!focus;
    hopMat.color.setHex(!intl ? TONE.idle : intl.aidc !== 'ok' ? TONE[intl.aidc] : intl.link !== 'ok' ? TONE.degraded : TONE[intl.tone]);
    markers.KR.mat.color.setHex(!any || focus.aidc === 'ok' ? 0x81f1da : TONE[focus.aidc]);
    markers.KR.ring.scale.setScalar(1 + (any && focus.aidc === 'fault' && !reducedMotion ? .3 * (.5 + .5 * Math.sin(time * 4)) : 0));
    const kind = !any ? '' : focus.aidc !== 'ok' ? focus.aidc : focus.link !== 'ok' ? 'degraded' : '';
    const bkey = `${kind}:${focus?.cause}`; badge.visible = !!kind; if (kind && badgeKey !== bkey) { badgeKey = bkey; drawBadge(kind, focus.cause); }
    visual = { lit: Object.keys(lit), focus: focus?.code ?? null, tone: focus?.tone ?? 'idle', hop: '#' + hopMat.color.getHexString(), aidcMarker: '#' + markers.KR.mat.color.getHexString(),
      markers: Object.fromEntries(Object.keys(paths).map(c => [c, '#' + markers[c].mat.color.getHexString()])),
      sea: Object.fromEntries(Object.entries(paths).map(([c, p]) => [c, '#' + p.mat.color.getHexString()])),
      counts: Object.fromEntries(litList.map(s => [s.code, s.count])),
      packetsVisible: Object.values(paths).some(p => p.packets.some(x => x.m.visible)), packetsMoving: !reducedMotion, faultBadge: badge.visible, faultKind: kind || null, cause: focus?.cause ?? null,
      requestBadges: Object.entries(paths).filter(([, p]) => p.badge.visible).map(([c]) => c), routes: Object.keys(paths).length, sites: Object.keys(MAP_SITES).length,
      background: { links: BACKGROUND_LINKS.length, color: '#' + bgMat.color.getHexString(), opacity: +bgMat.opacity.toFixed(3) } };
  }
  // Screen point for a code: a lit city's badge (what the player clicks), else its marker.
  const point = id => (paths[id]?.badge.visible ? paths[id].badge.position : markers[id]?.point)?.clone();
  return { group, pickables, update, markers, visual: () => visual && { ...visual }, point, markerPoint: id => markers[id]?.point.clone(), landing: () => landing.clone(), clip };
}
