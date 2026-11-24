// Korea-centred world map with a dim background network (Issue #3). Customer paths stay dark until the engine
// reports a request that actually arrived from that country; only those paths are lit (Issue #5).
import * as THREE from 'three';
import landSource from './assets/land.geojson?raw';
import { COUNTRIES } from './world-store.js';
import { SCALE, HALF_WIDTH, toMap, unwrap, copyOffsets } from './geo.js';
import { LANDING, BACKGROUND_LINKS, REQUEST_PATHS, activePaths, pathStatus, focusPath, CAUSE_TEXT } from './network-data.js';

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

export function createWorldMap() {
  const group = new THREE.Group(), pickables = [], markers = {};
  // Clip everything that wraps past the seam back to the map edges.
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

  // Country markers: neutral customer sites. No site looks active until a real request arrives.
  const sphereGeo = new THREE.SphereGeometry(.17, 16, 12), ringGeo = new THREE.TorusGeometry(.44, .025, 6, 40);
  const offsets = { KR: [-2.4, 1.9, -1.5], JP: [2.4, 1.2, -1.2], SG: [-2.6, 1.3, 1.3], US: [1.8, 1.4, -1.4] };
  for (const [id, c] of Object.entries(COUNTRIES)) {
    const point = V(...toMap(c.lon, c.lat, .42)); if (id === 'KR') point.set(point.x + .32, 1.05, point.z - .28);
    const mat = new THREE.MeshBasicMaterial({ color: id === 'KR' ? 0x81f1da : NEUTRAL, toneMapped: false });
    const node = new THREE.Mesh(sphereGeo, mat); node.position.copy(point); group.add(node);
    const ring = new THREE.Mesh(ringGeo, mat); ring.rotation.x = Math.PI / 2; ring.position.copy(point); group.add(ring);
    const proxy = new THREE.Mesh(new THREE.SphereGeometry(.75, 10, 8), new THREE.MeshBasicMaterial({ visible: false })); proxy.position.copy(point); proxy.userData.pickId = `country:${id}`; group.add(proxy); pickables.push(proxy);
    const o = offsets[id];
    label(group, id === 'KR' ? 'ULSAN AIDC' : c.short, id === 'KR' ? '남구 황성동·용연 (가상)' : '고객 거점 · 가상', point.x + o[0], o[1], point.z + o[2], id === 'KR' ? 4.6 : 3.6, id === 'KR' ? '#8af0d4' : '#9bb6c6');
    markers[id] = { node, ring, point, mat, labelAt: V(point.x + o[0], o[1] + .95, point.z + o[2]) };
  }
  const kr = markers.KR.point, krGround = V(...toMap(COUNTRIES.KR.lon, COUNTRIES.KR.lat, .22));
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([krGround, kr]), new THREE.LineBasicMaterial({ color: 0x81f1da, transparent: true, opacity: .5 })));

  // Shared landing station and the domestic backbone hop to the AIDC: always drawn, dim until a path is lit.
  const landing = V(...toMap(...LANDING.BUSAN.lonLat, .26));
  const landingNode = new THREE.Mesh(new THREE.CylinderGeometry(.13, .13, .14, 12), new THREE.MeshBasicMaterial({ color: 0xd8f3ff, toneMapped: false })); landingNode.position.copy(landing); group.add(landingNode);
  label(group, 'LANDING · BUSAN', '부산 권역 육양국 (가상)', landing.x + 2.1, .9, landing.z + 1.7, 3.6, '#c9e4f0');
  const hopMid = landing.clone().lerp(kr, .5); hopMid.y = 1.25;
  const hopCurve = new THREE.QuadraticBezierCurve3(landing, hopMid, kr), hopMat = new THREE.MeshBasicMaterial({ color: TONE.idle, toneMapped: false });
  group.add(new THREE.Mesh(new THREE.TubeGeometry(hopCurve, 30, .035, 6, false), hopMat));
  // One sea tube per customer site, dark by default, plus its own packets and request badge.
  const packetGeo = new THREE.SphereGeometry(.075, 8, 6), packetMat = new THREE.MeshBasicMaterial({ color: 0xfff6dd, toneMapped: false });
  const paths = {};
  for (const [code, def] of Object.entries(REQUEST_PATHS)) {
    const pts = polyline(def.sea, .26)[0], curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal', .2);
    const mat = new THREE.MeshBasicMaterial({ color: TONE.idle, transparent: true, opacity: .55, toneMapped: false });
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 160, .04, 6, false), mat); group.add(tube);
    const packets = []; for (let k = 0; k < 9; k++) { const m = new THREE.Mesh(packetGeo, packetMat); m.visible = false; group.add(m); packets.push({ m, offset: k / 9 }); }
    const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 150; const tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace;
    const badge = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, toneMapped: false })); badge.scale.set(3.8, .9, 1); badge.renderOrder = 6; badge.visible = false;
    badge.position.copy(markers[code].labelAt); group.add(badge);
    paths[code] = { curve, mat, tube, packets, badge, canvas, tex, key: '' };
  }
  function drawRequestBadge(p, s) {
    const c = p.canvas.getContext('2d'), col = s.aidc !== 'ok' ? '#ff8a9a' : s.link !== 'ok' ? '#ffb27a' : s.tone === 'incoming' ? '#f4ca8d' : '#8af0d4';
    c.clearRect(0, 0, 640, 150); c.fillStyle = '#10161fee'; c.fillRect(0, 0, 640, 150); c.fillStyle = col; c.fillRect(0, 0, 8, 150);
    c.font = '600 46px Consolas, "Malgun Gothic", monospace'; c.fillText(`요청 #${s.rid} · ${s.tone === 'incoming' ? '새 요청 도착' : '작업 중'}`, 28, 64);
    c.font = '28px "Malgun Gothic", sans-serif'; c.fillStyle = '#c8d6e0'; c.fillText(s.aidc !== 'ok' ? 'AIDC 서버 문제 · 회선 정상' : s.cause !== 'ok' ? CAUSE_TEXT[s.cause] : '가상 경로 · 출처/조건 확인', 30, 116); p.tex.needsUpdate = true;
  }
  // Fault badge for the AIDC end of the focused path (shown only when that segment has a problem).
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

  function update(time, state, { reducedMotion = false } = {}) {
    const lit = Object.fromEntries(activePaths(state).map(p => [p.code, pathStatus(p)])), focus = focusPath(state);
    // Ambient network: a very slow, dim breathing of the background lines (never gold, never packets).
    bgMat.opacity = reducedMotion ? .5 : .46 + .08 * Math.sin(time * .5);
    for (const [code, p] of Object.entries(paths)) {
      const s = lit[code], m = markers[code];
      p.badge.visible = !!s;
      if (!s) { p.mat.color.setHex(TONE.idle); p.mat.opacity = .5; m.mat.color.setHex(NEUTRAL); m.ring.scale.setScalar(1); p.packets.forEach(x => { x.m.visible = false; }); continue; }
      const tone = s.link !== 'ok' ? TONE.degraded : s.cause === 'rerouted' ? TONE.check : TONE[s.tone];
      p.mat.color.setHex(tone); p.mat.opacity = s.focus ? .95 : .7; m.mat.color.setHex(tone);
      m.ring.scale.setScalar(1 + (reducedMotion ? 0 : (s.tone === 'incoming' ? .3 : .1) * (.5 + .5 * Math.sin(time * 3))));
      const key = `${s.rid}:${s.tone}:${s.aidc}:${s.link}:${s.cause}`; if (key !== p.key) { p.key = key; drawRequestBadge(p, s); }
      p.packets.forEach(({ m: dot, offset }) => {
        const u = reducedMotion ? offset : (time * .07 + offset) % 1, onHop = u > .88;
        dot.visible = !(onHop && s.aidc !== 'ok') && s.link === 'ok';
        if (dot.visible) dot.position.copy(onHop ? hopCurve.getPoint((u - .88) / .12) : p.curve.getPoint(u / .88));
      });
    }
    const any = !!focus;
    hopMat.color.setHex(!any ? TONE.idle : focus.aidc !== 'ok' ? TONE[focus.aidc] : focus.link !== 'ok' ? TONE.degraded : TONE[focus.tone]);
    markers.KR.mat.color.setHex(!any || focus.aidc === 'ok' ? 0x81f1da : TONE[focus.aidc]);
    markers.KR.ring.scale.setScalar(1 + (any && focus.aidc === 'fault' && !reducedMotion ? .3 * (.5 + .5 * Math.sin(time * 4)) : 0));
    const kind = !any ? '' : focus.aidc !== 'ok' ? focus.aidc : focus.link !== 'ok' ? 'degraded' : '';
    const bkey = `${kind}:${focus?.cause}`; badge.visible = !!kind; if (kind && badgeKey !== bkey) { badgeKey = bkey; drawBadge(kind, focus.cause); }
    visual = { lit: Object.keys(lit), focus: focus?.code ?? null, tone: focus?.tone ?? 'idle', hop: '#' + hopMat.color.getHexString(), aidcMarker: '#' + markers.KR.mat.color.getHexString(),
      markers: Object.fromEntries(Object.keys(REQUEST_PATHS).map(c => [c, '#' + markers[c].mat.color.getHexString()])),
      sea: Object.fromEntries(Object.entries(paths).map(([c, p]) => [c, '#' + p.mat.color.getHexString()])),
      packetsVisible: Object.values(paths).some(p => p.packets.some(x => x.m.visible)), packetsMoving: !reducedMotion, faultBadge: badge.visible, faultKind: kind || null, cause: focus?.cause ?? null,
      requestBadges: Object.entries(paths).filter(([, p]) => p.badge.visible).map(([c]) => c),
      background: { links: BACKGROUND_LINKS.length, color: '#' + bgMat.color.getHexString(), opacity: +bgMat.opacity.toFixed(3) } };
  }
  return { group, pickables, update, markers, visual: () => visual && { ...visual }, point: id => markers[id]?.point.clone(), landing: () => landing.clone(), clip };
}
