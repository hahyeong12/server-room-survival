// Korea-centred world map with a dim background network and one lit request path (Issue #3).
import * as THREE from 'three';
import landSource from './assets/land.geojson?raw';
import { COUNTRIES } from './world-store.js';
import { SCALE, HALF_WIDTH, toMap, unwrap, copyOffsets } from './geo.js';
import { LANDING, BACKGROUND_LINKS, REQUEST_PATHS, requestPathStatus } from './network-data.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const TONE = { incoming: 0xf3c37b, active: 0x6fe7d2, done: 0x5fb9a9, fault: 0xff657d, repairing: 0xf8be68, check: 0x89baff, ok: 0x6fe7d2 };
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

  // Country markers (customers) and the Ulsan AIDC beacon raised above Korea so the last hop is visible.
  const sphereGeo = new THREE.SphereGeometry(.17, 16, 12), ringGeo = new THREE.TorusGeometry(.44, .025, 6, 40);
  const offsets = { KR: [-2.4, 1.9, -1.5], JP: [2.4, 1.2, -1.2], SG: [-2.6, 1.3, 1.3], US: [1.8, 1.4, -1.4] };
  for (const [id, c] of Object.entries(COUNTRIES)) {
    const point = V(...toMap(c.lon, c.lat, .42)); if (id === 'KR') point.set(point.x + .32, 1.05, point.z - .28);
    const mat = new THREE.MeshBasicMaterial({ color: id === 'KR' ? 0x81f1da : id === 'SG' ? TONE.incoming : 0x6d8ea3, toneMapped: false });
    const node = new THREE.Mesh(sphereGeo, mat); node.position.copy(point); group.add(node);
    const ring = new THREE.Mesh(ringGeo, mat); ring.rotation.x = Math.PI / 2; ring.position.copy(point); group.add(ring);
    const proxy = new THREE.Mesh(new THREE.SphereGeometry(.75, 10, 8), new THREE.MeshBasicMaterial({ visible: false })); proxy.position.copy(point); proxy.userData.pickId = `country:${id}`; group.add(proxy); pickables.push(proxy);
    const o = offsets[id];
    label(group, id === 'KR' ? 'ULSAN AIDC' : c.short, id === 'KR' ? '남구 황성동·용연 (가상)' : id === 'SG' ? 'SG-2026-001 · 요청' : '활성 요청 없음', point.x + o[0], o[1], point.z + o[2], id === 'KR' || id === 'SG' ? 4.6 : 3.6, id === 'SG' ? '#f4ca8d' : id === 'KR' ? '#8af0d4' : '#9bb6c6');
    markers[id] = { node, ring, point, mat };
  }
  const kr = markers.KR.point, krGround = V(...toMap(COUNTRIES.KR.lon, COUNTRIES.KR.lat, .22));
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([krGround, kr]), new THREE.LineBasicMaterial({ color: 0x81f1da, transparent: true, opacity: .5 })));

  // The lit request path: sea cable -> landing station -> domestic backbone (raised hop) -> AIDC.
  const req = REQUEST_PATHS.SG, landing = V(...toMap(...LANDING[req.landing].lonLat, .26));
  const seaPts = polyline(req.sea, .26)[0], seaCurve = new THREE.CatmullRomCurve3(seaPts, false, 'centripetal', .2);
  const seaMat = new THREE.MeshBasicMaterial({ color: TONE.incoming, transparent: true, opacity: .95, toneMapped: false });
  group.add(new THREE.Mesh(new THREE.TubeGeometry(seaCurve, 160, .045, 6, false), seaMat));
  const landingNode = new THREE.Mesh(new THREE.CylinderGeometry(.13, .13, .14, 12), new THREE.MeshBasicMaterial({ color: 0xd8f3ff, toneMapped: false })); landingNode.position.copy(landing); group.add(landingNode);
  label(group, 'LANDING · BUSAN', '부산 권역 육양국 (가상)', landing.x + 2.1, .9, landing.z + 1.7, 3.6, '#c9e4f0');
  const hopMid = landing.clone().lerp(kr, .5); hopMid.y = 1.25;
  const hopCurve = new THREE.QuadraticBezierCurve3(landing, hopMid, kr), hopMat = new THREE.MeshBasicMaterial({ color: TONE.incoming, toneMapped: false });
  group.add(new THREE.Mesh(new THREE.TubeGeometry(hopCurve, 30, .035, 6, false), hopMat));
  const packetMat = new THREE.MeshBasicMaterial({ color: 0xfff6dd, toneMapped: false }), packets = [];
  for (let k = 0; k < 9; k++) { const m = new THREE.Mesh(new THREE.SphereGeometry(.075, 8, 6), packetMat); group.add(m); packets.push({ m, offset: k / 9 }); }
  // Fault badge for the AIDC-internal last mile (shown only when that segment has a problem).
  const badgeCanvas = document.createElement('canvas'); badgeCanvas.width = 640; badgeCanvas.height = 160;
  const badgeTex = new THREE.CanvasTexture(badgeCanvas); badgeTex.colorSpace = THREE.SRGBColorSpace;
  const badge = new THREE.Sprite(new THREE.SpriteMaterial({ map: badgeTex, depthTest: false, toneMapped: false })); badge.scale.set(4.2, 1.05, 1); badge.position.set(kr.x + 2.6, 2.2, kr.z + .4); badge.renderOrder = 6; badge.visible = false; group.add(badge);
  let badgeKey = '', visual = null;
  function drawBadge(aidc) {
    const c = badgeCanvas.getContext('2d'), col = aidc === 'fault' ? '#ff8a9a' : aidc === 'repairing' ? '#ffc777' : '#a7c9ff';
    c.clearRect(0, 0, 640, 160); c.fillStyle = '#140c12ee'; c.fillRect(0, 0, 640, 160); c.strokeStyle = col; c.lineWidth = 5; c.strokeRect(3, 3, 634, 154);
    c.fillStyle = col; c.font = 'bold 64px "Segoe UI Symbol", sans-serif'; c.fillText(aidc === 'fault' ? '⚠' : aidc === 'repairing' ? '🛠' : '✓', 22, 104);
    c.font = '600 38px "Malgun Gothic", sans-serif'; c.fillText(aidc === 'fault' ? 'AIDC 내부 업링크 단절' : aidc === 'repairing' ? 'AIDC 업링크 복구 중' : '복구됨 · 사후 확인 대기', 110, 72);
    c.font = '26px "Malgun Gothic", sans-serif'; c.fillStyle = '#c8d6e0'; c.fillText('국제 구간·육양국·국내망은 정상', 112, 122); badgeTex.needsUpdate = true;
  }

  function update(time, state, { reducedMotion = false } = {}) {
    const s = requestPathStatus(state), color = TONE[s.tone];
    seaMat.color.setHex(color); hopMat.color.setHex(s.aidc === 'ok' ? color : TONE[s.aidc]);
    markers.SG.mat.color.setHex(s.tone === 'incoming' ? TONE.incoming : 0x7fd9c9);
    markers.KR.mat.color.setHex(s.aidc === 'ok' ? 0x81f1da : TONE[s.aidc]);
    const pulse = reducedMotion ? 0 : (s.tone === 'incoming' || s.aidc === 'fault' ? .3 : .1);
    markers.SG.ring.scale.setScalar(1 + pulse * (.5 + .5 * Math.sin(time * 3))); markers.KR.ring.scale.setScalar(1 + (s.aidc === 'fault' && !reducedMotion ? .3 * (.5 + .5 * Math.sin(time * 4)) : 0));
    // Packets run along the sea segment always (while active); they only enter the last hop when it is healthy.
    const moving = s.packets && !reducedMotion;
    packets.forEach(({ m, offset }, i) => {
      m.visible = s.packets; const u = moving ? (time * .07 + offset) % 1 : offset, onHop = u > .88;
      if (onHop && s.aidc !== 'ok') { m.visible = false; return; }
      m.position.copy(onHop ? hopCurve.getPoint((u - .88) / .12) : seaCurve.getPoint(u / .88));
    });
    badge.visible = s.aidc !== 'ok'; if (badge.visible && badgeKey !== s.aidc) { badgeKey = s.aidc; drawBadge(s.aidc); }
    visual = { tone: s.tone, sea: '#' + seaMat.color.getHexString(), hop: '#' + hopMat.color.getHexString(), aidcMarker: '#' + markers.KR.mat.color.getHexString(), packetsVisible: packets.some(p => p.m.visible), packetsMoving: moving, faultBadge: badge.visible,
      background: { links: BACKGROUND_LINKS.length, color: '#' + bgMat.color.getHexString(), opacity: bgMat.opacity } };
  }
  return { group, pickables, update, markers, visual: () => visual && { ...visual }, point: id => markers[id]?.point.clone(), landing: () => landing.clone(), clip };
}
