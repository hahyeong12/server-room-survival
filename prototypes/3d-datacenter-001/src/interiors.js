// Small functional interiors for the campus facilities (Issue #3, double-click on a building).
// Each room has its own equipment and a live status display bound to the shared demo state.
// Educational diagrams only: not real plant, switchgear, UPS or network designs.
import * as THREE from 'three';
import { coolingView, powerView, upsView, networkView } from './facility-ops.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const MODE_COLOR = { on: 0x6fe7d2, off: 0x56636e, warn: 0xffad5c };

export const ROOM_POSES = Object.freeze({
  COOLING: { eye: [9.5, 7.5, 10.5], target: [-.3, 1.2, -1] },
  POWER: { eye: [8.5, 7, 10.5], target: [-.5, 1.3, -1.5] },
  UPS: { eye: [9, 7.2, 10], target: [-.5, 1.1, -1] },
  NETWORK: { eye: [8.5, 6.8, 10], target: [-.5, 1.4, -1.5] },
});
export const ROOM_TITLES = Object.freeze({ COOLING: '보조 냉각 펌프실 · AUX-C1', POWER: '배전실 · A/B 수전', UPS: 'UPS · 배터리실', NETWORK: '네트워크 MMR · 업링크' });

function canvasPanel(w, h) {
  const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h;
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; texture.anisotropy = 4;
  return { canvas, texture, ctx: canvas.getContext('2d') };
}
function signTexture(text, sub, color = '#8af0d4') {
  const p = canvasPanel(512, 128), c = p.ctx; c.fillStyle = '#0c1928'; c.fillRect(0, 0, 512, 128); c.fillStyle = color; c.fillRect(0, 0, 6, 128);
  c.font = '600 44px Consolas, "Malgun Gothic", monospace'; c.fillText(text, 22, 56); c.font = '26px "Malgun Gothic", sans-serif'; c.fillStyle = '#a9bccb'; c.fillText(sub, 24, 102); return p.texture;
}

export function createInteriors() {
  const root = new THREE.Group(), rooms = {}, anim = { cooling: { rotors: [], dots: [], curves: [], beacon: null, dotMat: null }, ups: {}, network: {}, power: {} };
  const mat = {
    floor: new THREE.MeshStandardMaterial({ color: 0x3b4c5b, metalness: .3, roughness: .65 }), slab: new THREE.MeshStandardMaterial({ color: 0x223140, metalness: .35, roughness: .6 }),
    wall: new THREE.MeshStandardMaterial({ color: 0x40566a, metalness: .2, roughness: .6 }), dark: new THREE.MeshStandardMaterial({ color: 0x141f2b, metalness: .7, roughness: .4 }),
    metal: new THREE.MeshStandardMaterial({ color: 0x6b7f8c, metalness: .8, roughness: .35 }), blue: new THREE.MeshStandardMaterial({ color: 0x27405e, metalness: .5, roughness: .4 }),
    supply: new THREE.MeshStandardMaterial({ color: 0x3d8f97, metalness: .6, roughness: .35 }), ret: new THREE.MeshStandardMaterial({ color: 0x8c6f45, metalness: .6, roughness: .4 }),
    cabinet: new THREE.MeshStandardMaterial({ color: 0x2c3b4b, metalness: .55, roughness: .45 }), fiber: new THREE.MeshStandardMaterial({ color: 0xc9a443, metalness: .3, roughness: .5 }),
  };
  const boxGeo = new THREE.BoxGeometry(1, 1, 1);
  const box = (g, m, x, y, z, w, h, d) => { const mesh = new THREE.Mesh(boxGeo, m); mesh.position.set(x, y, z); mesh.scale.set(w, h, d); mesh.castShadow = mesh.receiveShadow = true; g.add(mesh); return mesh; };
  const sign = (g, text, sub, x, y, z, w = 2.4, rotY = 0, color) => { const s = new THREE.Mesh(new THREE.PlaneGeometry(w, w / 4), new THREE.MeshBasicMaterial({ map: signTexture(text, sub, color), toneMapped: false })); s.position.set(x, y, z); s.rotation.y = rotY; g.add(s); return s; };
  const tube = (g, pts, m, r = .14) => { const curve = new THREE.CurvePath(); for (let i = 1; i < pts.length; i++) curve.add(new THREE.LineCurve3(V(...pts[i - 1]), V(...pts[i]))); g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 64, r, 10, false), m)); return curve; };
  function shell(g) {
    box(g, mat.slab, 0, -.3, 0, 15, .5, 11); box(g, mat.floor, 0, -.02, 0, 14.6, .06, 10.6);
    for (let x = -7; x <= 7; x += 1) box(g, mat.slab, x, .015, 0, .012, .01, 10.6);
    box(g, mat.wall, 0, 2, -5.3, 14.6, 4, .15); box(g, mat.wall, -7.3, 2, 0, .15, 4, 10.6);
    const light = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0xc5e9ff, toneMapped: false })); light.position.set(0, 3.95, -5.2); light.scale.set(13, .04, .05); g.add(light);
  }
  function display(g, x, y, z, w, h, rotY = 0) {
    const p = canvasPanel(1024, Math.round(1024 * h / w)); box(g, mat.dark, x, y, z - .05, w + .15, h + .15, .08);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: p.texture, toneMapped: false })); m.position.set(x, y, z); m.rotation.y = rotY; g.add(m); return p;
  }

  // ---- Cooling pump room ----
  { const g = new THREE.Group(); shell(g); rooms.COOLING = g;
    for (const [i, z] of [[0, 1.4], [1, -1.4]]) {
      box(g, mat.dark, -3.5, .2, z, 3, .3, 1.4);
      const motor = new THREE.Mesh(new THREE.CylinderGeometry(.45, .45, 1.3, 24), mat.blue); motor.rotation.z = Math.PI / 2; motor.position.set(-4.3, .85, z); motor.castShadow = true; g.add(motor);
      const volute = new THREE.Mesh(new THREE.CylinderGeometry(.6, .6, .5, 24), mat.metal); volute.rotation.x = Math.PI / 2; volute.position.set(-2.8, .9, z); g.add(volute);
      const rotor = new THREE.Group(); rotor.position.set(-5.02, .85, z); g.add(rotor); anim.cooling.rotors.push(rotor);
      for (let b = 0; b < 4; b++) { const blade = new THREE.Mesh(boxGeo, mat.metal); blade.scale.set(.04, .7, .1); blade.rotation.x = b * Math.PI / 4; rotor.add(blade); }
      sign(g, `PUMP P-${i + 1}`, '순환 펌프', -3.5, 1.9, z + .75, 1.8);
    }
    // plate heat exchanger
    box(g, mat.metal, 2.4, 1.2, -2.6, 1.8, 2.4, .2); box(g, mat.metal, 2.4, 1.2, -1.1, 1.8, 2.4, .2);
    const plates = new THREE.InstancedMesh(boxGeo, mat.blue, 24); for (let k = 0; k < 24; k++) plates.setMatrixAt(k, new THREE.Matrix4().compose(V(2.4, 1.2, -2.45 + k * .055), new THREE.Quaternion(), V(1.6, 2.2, .03))); g.add(plates);
    sign(g, 'HEAT EXCHANGER', '판형 열교환기', 2.4, 2.75, -1, 2.2);
    const sup = tube(g, [[-2.2, .9, 1.4], [0, .9, 1.4], [0, .9, -.6], [1.4, .9, -.6], [1.4, 2.0, -1.8], [6.6, 2.0, -1.8], [6.6, 3.4, -1.8]], mat.supply);
    const ret = tube(g, [[6.2, 3.4, -3.6], [6.2, 2.4, -3.6], [1.4, 2.4, -3.6], [1.4, .9, -3.1], [-2.2, .9, -3.1], [-2.2, .9, -1.4]], mat.ret);
    anim.cooling.curves = [sup, ret]; anim.cooling.dotMat = new THREE.MeshBasicMaterial({ color: 0x6fe7d2, toneMapped: false });
    for (let c = 0; c < 2; c++) for (let k = 0; k < 10; k++) { const d = new THREE.Mesh(new THREE.SphereGeometry(.09, 8, 6), anim.cooling.dotMat); g.add(d); anim.cooling.dots.push({ d, c, offset: k / 10 }); }
    sign(g, '→ 서버동 01', '공급 (차가운 물)', 6, 3.7, -1.2, 2.2, 0, '#6fe7d2'); sign(g, '← 환수', '서버동에서 돌아온 물', 5.6, 3.7, -3.2, 2.2, 0, '#e0b067');
    anim.cooling.beacon = new THREE.Mesh(new THREE.SphereGeometry(.22, 16, 12), new THREE.MeshBasicMaterial({ color: MODE_COLOR.on, toneMapped: false })); anim.cooling.beacon.position.set(-1.2, 3.5, -5); g.add(anim.cooling.beacon);
    anim.cooling.display = display(g, -3.4, 2.5, -5.15, 4.4, 2.2);
  }
  // ---- Power distribution room ----
  { const g = new THREE.Group(); shell(g); rooms.POWER = g; anim.power.leds = [];
    for (let k = 0; k < 8; k++) { const x = -5.4 + k * 1.15; box(g, mat.cabinet, x, 1.1, -4.4, 1.05, 2.2, 1.1); box(g, mat.dark, x, 1.5, -3.84, .6, .35, .02);
      const led = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0x6fe7d2, toneMapped: false })); led.position.set(x + .3, 1.9, -3.83); led.scale.set(.12, .12, .02); g.add(led); anim.power.leds.push(led); }
    box(g, mat.dark, -5.4, .9, 1.5, 2, 1.8, 2.4); for (let f = 0; f < 9; f++) box(g, mat.metal, -6.45, .9, .5 + f * .25, .06, 1.6, .12);
    sign(g, 'TRANSFORMER', '변압기 (모식)', -5.4, 2.3, 2.75, 2.2);
    tube(g, [[-6.8, 3.2, -3.3], [6.5, 3.2, -3.3]], new THREE.MeshStandardMaterial({ color: 0xc79c55, metalness: .7, roughness: .35 }), .09);
    tube(g, [[-6.8, 2.9, -3], [6.5, 2.9, -3]], new THREE.MeshStandardMaterial({ color: 0x4a9fb0, metalness: .7, roughness: .35 }), .09);
    sign(g, 'FEED A', 'A 수전 (상용)', 4.6, 3.55, -3.3, 1.8, 0, '#e4bf7d'); sign(g, 'FEED B', 'B 수전 (이중화)', 4.6, 2.5, -2.9, 1.8, 0, '#7fd3e0');
    anim.power.display = display(g, 2.8, 1.6, -5.15, 4, 2);
  }
  // ---- UPS / battery room ----
  { const g = new THREE.Group(); shell(g); rooms.UPS = g; anim.ups.bars = [];
    for (let row = 0; row < 3; row++) for (let k = 0; k < 6; k++) { const x = -4.2 + k * 1, z = -2.6 + row * 2.2; box(g, mat.cabinet, x, .95, z, .85, 1.9, .9);
      const bar = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0x6fe7d2, toneMapped: false })); bar.position.set(x, .95, z + .46); bar.scale.set(.08, 1.4, .02); g.add(bar); anim.ups.bars.push(bar); }
    sign(g, 'BATTERY STRINGS', '배터리 랙 (모식)', -1.7, 2.4, 2.3, 2.6);
    for (const x of [3.4, 4.6]) { box(g, mat.blue, x, 1.1, -4.2, 1.1, 2.2, 1.2); box(g, mat.dark, x, 1.6, -3.58, .7, .4, .02); }
    sign(g, 'UPS MODULE', '무정전 전원장치', 4, 2.6, -3.55, 2.2);
    anim.ups.display = display(g, -3.6, 2.6, -5.15, 3.8, 1.8);
  }
  // ---- Network meet-me room ----
  { const g = new THREE.Group(); shell(g); rooms.NETWORK = g; anim.network.ports = [];
    for (let k = 0; k < 5; k++) { const x = -4.6 + k * 1.4; box(g, mat.dark, x, 1.15, -3.2, 1, 2.3, 1);
      for (let p = 0; p < 24; p++) { const led = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0x6fe7d2, toneMapped: false })); led.position.set(x - .4 + (p % 8) * .11, .8 + Math.floor(p / 8) * .45, -2.69); led.scale.set(.05, .04, .02); g.add(led); anim.network.ports.push({ led, uplink: k === 2 && p < 8 }); } }
    sign(g, 'UPLINK · HALL 01', '서버동 01 업링크 (D-06 ToR 포함)', -1.8, 2.75, -2.68, 2.6);
    tube(g, [[-6.8, 3.4, -3.2], [6.6, 3.4, -3.2]], mat.fiber, .12); tube(g, [[6.6, 3.4, -3.2], [6.6, 3.4, 3.5]], mat.fiber, .12);
    sign(g, '국제 가상 회선 →', '부산 권역 육양국 · 국내망 (가상)', 4.2, 3.75, -3.1, 2.6, 0, '#c9a443');
    box(g, mat.blue, 4, .9, 1.5, 1.6, 1.8, 1.2); sign(g, 'CORE ROUTER', '코어 라우터 (모식)', 4, 2.1, 2.15, 2);
    anim.network.display = display(g, 3.2, 1.9, -5.15, 4, 2);
  }
  for (const [id, g] of Object.entries(rooms)) { g.visible = false; g.userData.room = id; root.add(g); }

  let keys = {}, current = null, visual = null, rotorAngle = 0, flowPhase = 0;
  function draw(panel, lines, accent) {
    const c = panel.ctx, w = panel.canvas.width, h = panel.canvas.height; c.fillStyle = '#071423'; c.fillRect(0, 0, w, h); c.fillStyle = accent; c.fillRect(0, 0, w, 10);
    lines.forEach(([text, size, color], i) => { c.fillStyle = color || '#cfe3ee'; c.font = `${i === 0 ? 600 : 400} ${size}px "Malgun Gothic", Consolas, sans-serif`; c.fillText(text, 36, 40 + lines.slice(0, i + 1).reduce((s, l) => s + l[1] * 1.35, 0)); });
    panel.texture.needsUpdate = true;
  }
  function update(time, state, dt) {
    if (!current) return;
    const cv = coolingView(state), pv = powerView(state), uv = upsView(state), nv = networkView(state), checks = state.ops.checks;
    if (current === 'COOLING') {
      const speed = cv.mode === 'on' ? 5 : cv.mode === 'warn' ? 12 : 0; rotorAngle += speed * dt; for (const r of anim.cooling.rotors) r.rotation.x = rotorAngle;
      flowPhase += (cv.mode === 'on' ? .12 : cv.mode === 'warn' ? .03 : 0) * dt;
      anim.cooling.dotMat.color.setHex(cv.mode === 'warn' ? 0xffad5c : 0x6fe7d2);
      for (const { d, c, offset } of anim.cooling.dots) { d.visible = cv.mode !== 'off'; d.position.copy(anim.cooling.curves[c].getPointAt((flowPhase + offset) % 1)); }
      anim.cooling.beacon.material.color.setHex(cv.mode === 'warn' && Math.sin(time * 6) < 0 ? 0x6a3a1a : MODE_COLOR[cv.mode]);
      const key = `${cv.mode}`; if (keys.COOLING !== key) { keys.COOLING = key;
        draw(anim.cooling.display, [[`${cv.icon}  보조 냉각 ${cv.label}`, 64, cv.mode === 'on' ? '#6fe7d2' : cv.mode === 'warn' ? '#ffad5c' : '#9aa7b2'], [cv.summary, 34], [`냉각수 유량  ${cv.flow} L/min`, 40], [`공급 / 환수  ${cv.supply ?? '—'} / ${cv.ret ?? '—'} °C`, 40], [`펌프 ${cv.fan ? '운전' : '정지'} · 서버동 유입 ${cv.hallInlet} °C`, 34, '#a9bccb']], cv.mode === 'warn' ? '#ffad5c' : '#6fe7d2'); }
      visual = { room: current, mode: cv.mode, pumpsSpinning: speed > 0, flowVisible: cv.mode !== 'off', display: keys.COOLING };
    } else if (current === 'POWER') {
      const done = !!checks.power; anim.power.leds.forEach((l, i) => l.material.color.setHex(done ? 0x7ff5a6 : (Math.floor(time * 2) + i) % 8 === 0 ? 0xe4bf7d : 0x6fe7d2));
      const key = `${pv.totalKW}:${done}`; if (keys.POWER !== key) { keys.POWER = key;
        draw(anim.power.display, [['⚡ 배전 상태', 60, '#e4bf7d'], [pv.feeds, 40], [`부하 ${pv.totalKW} / ${pv.capacityKW} kW`, 44], [`IT ${pv.itLoadKW} kW · 보조 냉각 ${pv.coolingLoadKW} kW`, 34, '#a9bccb'], [done ? '✓ 전력 계통 점검 완료' : '점검 대기', 40, done ? '#7ff5a6' : '#a9bccb']], '#e4bf7d'); }
      visual = { room: current, checked: done, display: keys.POWER };
    } else if (current === 'UPS') {
      const done = !!checks.ups; anim.ups.bars.forEach(b => b.material.color.setHex(0x6fe7d2));
      const key = `${done}`; if (keys.UPS !== key) { keys.UPS = key;
        draw(anim.ups.display, [['🔋 배터리 ' + uv.battery + '%', 60, '#6fe7d2'], [uv.mode, 38], [`예비 시간 ${uv.runtime}`, 36], [done ? '✓ 자가진단 정상' : '자가진단 대기', 42, done ? '#7ff5a6' : '#a9bccb']], '#6fe7d2'); }
      visual = { room: current, checked: done, display: keys.UPS };
    } else if (current === 'NETWORK') {
      for (const { led, uplink } of anim.network.ports) led.material.color.setHex(uplink && nv.down ? (Math.sin(time * 5) > 0 ? 0xff657d : 0x4a1b24) : uplink && nv.uplink !== '정상' ? 0x89baff : 0x6fe7d2);
      const c = checks.network, key = `${nv.uplink}:${nv.links.map(l => l.status).join(',')}:${c?.seq ?? 0}`; if (keys.NETWORK !== key) { keys.NETWORK = key;
        draw(anim.network.display, [[`업링크 ${nv.uplink}`, 60, nv.down ? '#ff8a9a' : '#6fe7d2'], ...nv.links.map(l => [`${l.name}  ${l.latencyMs} ms  ${l.status}`, 34, l.status === '대역폭 부족' ? '#ff8a9a' : l.active ? '#f4ca8d' : '#cfe3ee']), [c ? c.title : '원인 조회 대기', 36, c ? '#ffd2a6' : '#a9bccb']], nv.down ? '#ff657d' : '#6fe7d2'); }
      visual = { room: current, uplinkDown: nv.down, faultPortsBlinking: nv.down, display: keys.NETWORK };
    }
  }
  function show(id) { current = Object.hasOwn(rooms, id) ? id : null; for (const [k, g] of Object.entries(rooms)) g.visible = k === current; keys[current] = null; }
  return { root, show, update, visual: () => visual && current ? { ...visual } : null, pose: id => ROOM_POSES[id], current: () => current };
}
