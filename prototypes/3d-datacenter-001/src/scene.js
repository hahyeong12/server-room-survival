import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';
import { readings, totals } from './model.js';
import { DESK_POSE, NOC_OVERVIEW_POSE } from './opening.js';
import { createWorldGeometry } from './world-geometry.js';

const C = { normal: 0x63e4c1, fault: 0xff455c, repairing: 0xffbd59, awaiting: 0x76b7ff, verified: 0x83f5d2 };
const V = (x, y, z) => new THREE.Vector3(x, y, z);

function canvasTexture(w, h, draw) {
  const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h;
  draw(canvas.getContext('2d'), w, h);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}
function labelTexture(text, subtitle = '', color = '#b4d1da', width = 1024, height = 256) {
  return canvasTexture(width, height, (c, w, h) => {
    c.fillStyle = '#142333'; c.fillRect(0, 0, w, h);
    c.fillStyle = color; c.font = `500 ${h * .34}px Consolas, monospace`; c.textBaseline = 'middle';
    c.fillText(text, w * .05, h * .43);
    c.fillStyle = '#7393a8'; c.font = `${h * .13}px Consolas, monospace`; c.fillText(subtitle, w * .05, h * .79);
    c.fillStyle = color; c.fillRect(w * .05, h * .94, w * .18, 2);
  });
}

export function createScene(container, facility, onSelect, options = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.22;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.info.autoReset = false;
  renderer.setClearColor(0x0b111b, 0);
  container.prepend(renderer.domElement);
  renderer.domElement.tabIndex = 0; renderer.domElement.setAttribute('aria-label', '3D 시설 탐색');
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, .1, 180);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = .075; controls.minDistance = 2.5; controls.maxDistance = 65;
  controls.maxPolarAngle = Math.PI * .485; controls.minPolarAngle = .1; controls.target.set(-.5, 0, 0);
  camera.position.set(27, 25, 30); controls.update();

  const pmrem = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, .04);
  scene.environment = environment.texture; scene.environmentIntensity = .42;
  room.dispose(); pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xc1dfff, 0x253244, 2.2));
  const sun = new THREE.DirectionalLight(0xf2f5ff, 3.6); sun.position.set(-8, 22, 12);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -24, right: 24, top: 19, bottom: -19, near: 1, far: 60 });
  sun.shadow.normalBias = .035; sun.shadow.bias = -.0002; scene.add(sun);
  const fill = new THREE.DirectionalLight(0x69c8df, 1.5); fill.position.set(16, 10, -14); scene.add(fill);
  const controlLight = new THREE.PointLight(0x63baff, 95, 22, 2); controlLight.position.set(10, 4, -3); scene.add(controlLight);

  const mat = {
    slab: new THREE.MeshStandardMaterial({ color: 0x283747, metalness: .35, roughness: .55 }),
    floor: new THREE.MeshStandardMaterial({ color: 0x455563, metalness: .32, roughness: .62 }),
    seam: new THREE.MeshStandardMaterial({ color: 0x344858, roughness: .8 }),
    wall: new THREE.MeshStandardMaterial({ color: 0x455c71, metalness: .22, roughness: .58 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x111b25, metalness: .72, roughness: .38 }),
    rail: new THREE.MeshStandardMaterial({ color: 0x4b5d6d, metalness: .8, roughness: .3 }),
    blade: new THREE.MeshStandardMaterial({ color: 0x3c4a59, metalness: .65, roughness: .44 }),
    blue: new THREE.MeshStandardMaterial({ color: 0x243a58, metalness: .5, roughness: .38 }),
    duct: new THREE.MeshStandardMaterial({ color: 0x677d88, metalness: .82, roughness: .38 }),
    cable: new THREE.MeshStandardMaterial({ color: 0xd5a155, metalness: .55, roughness: .42 }),
    black: new THREE.MeshStandardMaterial({ color: 0x090f17, roughness: .6 }),
    teal: new THREE.MeshStandardMaterial({ color: 0x3f797e, metalness: .7, roughness: .4 }),
    light: new THREE.MeshBasicMaterial({ color: 0xc5e9ff, toneMapped: false }),
    cyan: new THREE.MeshBasicMaterial({ color: 0x58cfd3, toneMapped: false }),
    amber: new THREE.MeshBasicMaterial({ color: 0xd9ae65, toneMapped: false }),
    chair: new THREE.MeshStandardMaterial({ color: 0x253748, roughness: .9 }),
  };

  // Most repeated geometry is batched by material, including all rack modules and vents.
  const buckets = new Map(), boxGeo = new THREE.BoxGeometry(1, 1, 1), matrix = new THREE.Matrix4();
  const quat = new THREE.Quaternion(), scale = new THREE.Vector3(), position = new THREE.Vector3();
  function box(material, x, y, z, w, h, d, rotation = 0) {
    if (!buckets.has(material)) buckets.set(material, []);
    quat.setFromAxisAngle(V(0, 1, 0), rotation);
    buckets.get(material).push({ x, y, z, w, h, d, q: quat.clone() });
  }
  function meshBox(material, x, y, z, w, h, d) {
    const mesh = new THREE.Mesh(boxGeo, material); mesh.position.set(x, y, z); mesh.scale.set(w, h, d);
    mesh.castShadow = true; mesh.receiveShadow = true; scene.add(mesh); return mesh;
  }
  function sign(text, subtitle, x, y, z, w, h, rotation = 0, color) {
    const tex = labelTexture(text, subtitle, color);
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
    mesh.position.set(x, y, z); mesh.rotation.y = rotation; scene.add(mesh); return mesh;
  }
  function tube(points, material, radius = .035, segments = 32, parent = scene) {
    const curve = new THREE.CurvePath();
    for (let i = 1; i < points.length; i++) curve.add(new THREE.LineCurve3(V(...points[i - 1]), V(...points[i])));
    const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, segments, radius, 6, false), material);
    parent.add(mesh); return curve;
  }

  // Raised floor, tiles, service channels, cutaway architectural shell.
  box(mat.slab, 0, -.55, 0, 32.5, .85, 21.5);
  box(mat.dark, 0, -.12, 0, 32.1, .15, 21.1);
  box(mat.floor, 0, 0, 0, 32, .12, 21);
  for (let x = -16; x <= 16; x += 1) box(mat.seam, x, .064, 0, .014, .012, 21);
  for (let z = -10.5; z <= 10.5; z += 1) box(mat.seam, 0, .065, z, 32, .012, .014);
  box(mat.wall, 0, 2.15, -10.4, 32.1, 4.3, .2);
  box(mat.wall, -16, 2.15, 0, .2, 4.3, 21);
  box(mat.dark, 0, .25, -10.23, 32, .35, .1);
  for (let x = -15; x < 16; x += 2) box(mat.rail, x, 2.15, -10.24, .028, 4.3, .04);
  box(mat.rail, -15.88, 4.35, 0, .25, .2, 21.2);
  box(mat.rail, 0, 4.35, -10.4, 32.3, .2, .25);
  box(mat.cyan, -15.84, 4.2, 0, .05, .04, 21);
  box(mat.light, 0, 4.23, -10.21, 31.5, .035, .04);
  sign('ULSAN / AIDC', 'COMPUTE HALL 01     /     SIMULATED FACILITY', -7.3, 3.1, -10.22, 8.1, 1.5);
  sign('OPERATIONS', 'NETWORK OPERATIONS CENTER', 9.3, 3.7, -10.22, 6, 1.05, 0, '#a9d6ff');
  // Cutaway front foundation and recessed service lines.
  box(mat.rail, 0, -.35, 10.8, 32.4, .22, .08);
  box(mat.cyan, -5.7, -.37, 10.85, 19, .035, .025);
  sign('SERVER HALL', 'HIGH DENSITY COMPUTE / 24 RACKS', -8.5, -.48, 10.83, 7, .5);
  sign('CONTROL ROOM', 'OPERATIONS & INCIDENT RESPONSE', 9.2, -.48, 10.83, 6, .5);

  // Rack fronts use a detailed, shared procedural metal panel texture.
  const faceTexture = canvasTexture(1024, 256, (c, w, h) => {
    c.fillStyle = '#334250'; c.fillRect(0, 0, w, h);
    const grad = c.createLinearGradient(0, 0, 0, h); grad.addColorStop(0, '#71808a'); grad.addColorStop(.08, '#3b4b5b'); grad.addColorStop(.8, '#263442'); grad.addColorStop(1, '#14212e'); c.fillStyle = grad; c.fillRect(0, 0, w, h);
    for (let x = 95; x < 820; x += 17) for (let y = 38; y < 218; y += 18) { c.fillStyle = '#101923'; c.fillRect(x, y, 10, 9); }
    c.fillStyle = '#9aaab4'; c.fillRect(22, 38, 12, 180); c.fillRect(980, 38, 12, 180);
    c.fillStyle = '#141e28'; for (const x of [52, 947]) for (const y of [32, 221]) { c.beginPath(); c.arc(x, y, 7, 0, Math.PI * 2); c.fill(); }
    c.fillStyle = '#a4bec8'; c.font = '15px Consolas'; c.fillText('GPU COMPUTE / 8X', 88, 25);
    c.fillStyle = '#6c8c9f'; c.fillRect(856, 82, 54, 20); c.fillStyle = '#88ada9'; c.fillRect(856, 125, 54, 18);
  });
  const faceMaterial = new THREE.MeshStandardMaterial({ map: faceTexture, metalness: .6, roughness: .48 });
  const frontGeo = new THREE.PlaneGeometry(.98, .22), frontMatrices = [];
  const selectionBox = new THREE.BoxGeometry(1, 1, 1);
  const selectionGeometry = new THREE.EdgesGeometry(selectionBox); selectionBox.dispose();
  const selectionMaterial = new THREE.LineBasicMaterial({ color: 0x83ffe4 });
  const selectable = [], visuals = new Map(), netLayer = new THREE.Group(), powerLayer = new THREE.Group(), coolLayer = new THREE.Group();
  scene.add(netLayer, powerLayer, coolLayer);
  const networkMaterial = new THREE.MeshBasicMaterial({ color: 0x497caa, transparent: true, opacity: .65 });
  const powerMaterial = new THREE.MeshBasicMaterial({ color: 0xc29d5c, transparent: true, opacity: .6 });
  const particles = [], flows = [];
  const particleGeo = new THREE.SphereGeometry(.065, 6, 5);

  for (const [index, a] of facility.assets.entries()) {
    const x = a.x, z = a.z, isRack = a.kind === 'rack', h = isRack ? 2.9 : 2.7;
    const body = meshBox(mat.dark, x, h / 2 + .16, z, isRack ? 1.22 : 1.5, h, 1.35);
    body.userData.assetId = a.id; selectable.push(body);
    box(mat.black, x, .14, z, isRack ? 1.35 : 1.6, .2, 1.5);
    box(mat.rail, x - (isRack ? .56 : .7), h / 2 + .16, z + .69, .045, h, .05);
    box(mat.rail, x + (isRack ? .56 : .7), h / 2 + .16, z + .69, .045, h, .05);
    box(mat.blade, x, h + .2, z, isRack ? 1.22 : 1.5, .1, 1.36);
    if (isRack) {
      for (let blade = 0; blade < 10; blade++) {
        const y = .5 + blade * .235;
        box(mat.blade, x, y, z + .52, 1.02, .21, .36);
        frontMatrices.push(new THREE.Matrix4().makeTranslation(x, y, z + .708));
      }
      // Top-of-rack switch, rear cabling, mounting feet and vented roof.
      box(mat.blue, x, 2.88, z + .52, 1.02, .18, .35);
      for (let p = 0; p < 8; p++) box(mat.black, x - .41 + p * .114, 2.89, z + .71, .075, .048, .018);
      for (let v = 0; v < 6; v++) box(mat.black, x - .42 + v * .17, 3.16, z, .06, .025, .95);
      box(mat.cable, x + .43, 1.7, z - .71, .045, 2.5, .05);
      box(mat.teal, x - .43, 1.7, z - .71, .045, 2.5, .05);
      for (let p = 0; p < 4; p++) box(mat.rail, x + (p % 2 ? .48 : -.48), .1, z + (p > 1 ? .52 : -.52), .09, .15, .09);
    } else {
      box(a.kind === 'cooling' ? mat.teal : mat.blue, x, 1.6, z + .7, 1.27, 2.25, .06);
      for (let k = 0; k < 16; k++) box(mat.black, x, .7 + k * .09, z + .74, 1.15, .026, .03);
      box(mat.black, x + .27, 2.42, z + .75, .42, .25, .025);
      box(mat.cyan, x + .27, 2.43, z + .768, .31, .13, .01);
      if (a.kind === 'cooling') {
        for (let fan = 0; fan < 2; fan++) {
          const fanMesh = new THREE.Mesh(new THREE.TorusGeometry(.32, .045, 6, 20), mat.rail);
          fanMesh.rotation.x = -Math.PI / 2; fanMesh.position.set(x, 2.94, z - .32 + fan * .64); scene.add(fanMesh);
          box(mat.black, x, 2.88, z - .32 + fan * .64, .5, .04, .5);
        }
      }
    }
    const indicatorMat = new THREE.MeshBasicMaterial({ color: C.normal, toneMapped: false });
    const strip = meshBox(indicatorMat, x - (isRack ? .59 : .74), 1.7, z + .734, .028, 2.45, .03);
    strip.castShadow = false;
    const statusCap = meshBox(indicatorMat, x, h + .29, z + .25, .45, .026, .14); statusCap.castShadow = false;
    sign(a.id, isRack ? 'GPU / 08' : a.kind.toUpperCase(), x, h - .02, z + .752, isRack ? .93 : 1.25, .25);
    const ring = new THREE.LineSegments(selectionGeometry, selectionMaterial);
    ring.scale.set(isRack ? 1.43 : 1.7, .035, 1.65); ring.position.set(x, .16, z); ring.visible = false; scene.add(ring);
    const halo = new THREE.PointLight(C.normal, 1.5, 2.1, 2); halo.position.set(x, .4, z + .85); scene.add(halo);
    // Different fault categories affect their corresponding route and metrics.
    const netMat = networkMaterial.clone(), pwrMat = powerMaterial.clone();
    const netCurve = tube([[x, 3.06, z - .45], [x, 3.9, z - .45], [2.7, 3.9, z - .45], [2.7, 3.7, -7]], netMat, .022, 18, netLayer);
    tube([[x, .1, z + .85], [x, .11, z + 1.14], [-12, .11, z + 1.14]], pwrMat, .025, 12, powerLayer);
    for (let p = 0; p < 2; p++) {
      const dot = new THREE.Mesh(particleGeo, new THREE.MeshBasicMaterial({ color: 0x88ccff, toneMapped: false }));
      netLayer.add(dot); particles.push({ mesh: dot, curve: netCurve, asset: a, offset: index * .031 + p * .5 });
    }
    visuals.set(a.id, { body, strip, cap: statusCap, ring, halo, netMat, pwrMat, index });
  }
  const faces = new THREE.InstancedMesh(frontGeo, faceMaterial, frontMatrices.length);
  frontMatrices.forEach((m, i) => faces.setMatrixAt(i, m)); scene.add(faces);
  // LED pixels on every module: one GPU draw call, colors updated in place.
  const leds = new THREE.InstancedMesh(new THREE.BoxGeometry(.033, .025, .012), new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }), 24 * 20);
  facility.assets.slice(0, 24).forEach((a, index) => {
    for (let b = 0; b < 10; b++) for (let l = 0; l < 2; l++) {
      const i = index * 20 + b * 2 + l;
      leds.setMatrixAt(i, new THREE.Matrix4().makeTranslation(a.x + .405, .47 + b * .235 + l * .055, a.z + .723));
      leds.setColorAt(i, new THREE.Color(C.normal));
    }
  }); scene.add(leds);

  // Cold aisle floor grilles, suspended service trays and overhead luminaires.
  for (let row = 0; row < 4; row++) {
    const z = -4.45 + row * 3.25;
    box(mat.blue, -6.4, .08, z, 10.5, .02, .65);
    for (let col = 0; col < 60; col++) box(mat.rail, -11.5 + col * .175, .097, z, .025, .02, .56);
    box(mat.rail, -5.9, 4.03, z - 1.8, 16.4, .13, .42);
    for (let rung = 0; rung < 40; rung++) box(mat.blade, -13.8 + rung * .4, 3.95, z - 1.8, .035, .07, .5);
    box(mat.light, -6.6, 4.33, z + .2, 10.3, .036, .055);
    box(mat.dark, -6.6, 4.38, z + .2, 10.6, .07, .15);
    for (const supportX of [-11.8, -.6]) box(mat.rail, supportX, 4.22, z - 1.8, .025, .6, .025);
    for (let f = 0; f < 9; f++) {
      const mesh = new THREE.Mesh(new THREE.ConeGeometry(.04, .17, 5), new THREE.MeshBasicMaterial({ color: 0x79dce5, transparent: true, opacity: .48, depthWrite: false }));
      mesh.position.set(-11 + f * 1.1, .25, z); coolLayer.add(mesh);
      const asset = facility.assets.slice(row * 6, row * 6 + 6).reduce((nearest, a) => Math.abs(a.x - mesh.position.x) < Math.abs(nearest.x - mesh.position.x) ? a : nearest);
      flows.push({ mesh, asset, x: mesh.position.x, z, offset: f * .13 + row * .2 });
    }
    // A restrained transparent cold-air volume, visual abstraction only.
    const coldPlane = new THREE.Mesh(new THREE.PlaneGeometry(10.6, 1.6), new THREE.MeshBasicMaterial({ color: 0x48b8d0, transparent: true, opacity: .035, depthWrite: false, side: THREE.DoubleSide }));
    coldPlane.position.set(-6.3, .9, z); coolLayer.add(coldPlane);
  }
  // Main cooling header with return/supply lines and elbows.
  for (const z of [-9, 8.8]) {
    tube([[-14, 3.7, z], [-12.4, 4.4, z], [1.4, 4.4, z]], mat.duct, .17, 24);
    tube([[-14.5, 3.5, z], [-12.7, 4.05, z], [1.4, 4.05, z]], mat.teal, .11, 24);
    for (let x = -12; x < 2; x += 2) box(mat.rail, x, 4.15, z, .06, .7, .7);
  }
  sign('A / B POWER', 'REDUNDANT FEEDS / DIAGRAM', -13.9, 3.5, -10.21, 3, .65, 0, '#e4bf7d');

  // Control room: glazing, mullions, monitor wall, workstations and task chairs.
  box(mat.dark, 9.9, .09, -.5, 11.6, .08, 15);
  for (let x = 4.2; x < 15.8; x += .9) box(mat.seam, x, .14, -.5, .012, .01, 15);
  box(mat.rail, 4.15, .22, -.6, .12, .3, 15.3);
  box(mat.rail, 4.15, 3.4, -.6, .11, .13, 15.3);
  const glassMat = new THREE.MeshPhysicalMaterial({ color: 0x72b8d0, metalness: .05, roughness: .1, transparent: true, opacity: .12, side: THREE.DoubleSide, depthWrite: false });
  for (let z = -7.2; z < 6.6; z += 2.3) {
    // One open doorway in the partition.
    if (z > 3) continue;
    const pane = meshBox(glassMat, 4.15, 1.85, z, .025, 3.05, 2.22); pane.castShadow = false;
    box(mat.rail, 4.15, 1.85, z - 1.12, .06, 3.05, .06);
    box(mat.rail, 4.15, 1.05, z, .06, .025, 2.25);
  }
  sign('NOC / 01', 'OPERATIONS CONTROL', 8.8, 3.28, -7.5, 6.8, .55, 0, '#9ed6f5');
  const wallCanvas = document.createElement('canvas'); wallCanvas.width = 2048; wallCanvas.height = 768;
  const wallTexture = new THREE.CanvasTexture(wallCanvas); wallTexture.colorSpace = THREE.SRGBColorSpace;
  const monitorMaterial = new THREE.MeshBasicMaterial({ map: wallTexture, toneMapped: false });
  meshBox(mat.black, 9.4, 1.98, -7.65, 9.9, 2.05, .16);
  const monitor = new THREE.Mesh(new THREE.PlaneGeometry(9.5, 1.75), monitorMaterial); monitor.position.set(9.4, 2, -7.55); scene.add(monitor);
  box(mat.rail, 9.4, 1.98, -7.50, .035, 1.85, .035);
  for (const x of [6.2, 12.6]) box(mat.rail, x, 1.98, -7.5, .035, 1.85, .035);
  box(mat.rail, 9.4, 1.98, -7.49, 9.6, .035, .035);
  for (let row = 0; row < 2; row++) for (let col = 0; col < 3; col++) {
    const x = 6.2 + col * 3.1, z = -3.8 + row * 4;
    box(mat.blade, x, 1.04, z, 2.6, .11, 1.2);
    box(mat.dark, x, .95, z + .57, 2.65, .19, .07);
    box(mat.dark, x - 1.03, .53, z, .13, 1, .85); box(mat.dark, x + 1.03, .53, z, .13, 1, .85);
    for (const dx of [-.58, .58]) {
      box(mat.black, x + dx, 1.67, z - .3, 1.07, .66, .07);
      box(mat.rail, x + dx, 1.3, z - .3, .06, .35, .06);
      box(mat.dark, x + dx, 1.12, z - .3, .4, .04, .28);
      const screen = new THREE.Mesh(new THREE.PlaneGeometry(.98, .56), monitorMaterial);
      screen.position.set(x + dx, 1.67, z - .254); scene.add(screen);
    }
    box(mat.black, x, 1.11, z + .23, .8, .04, .24);
    for (let key = 0; key < 8; key++) box(mat.blade, x - .33 + key * .09, 1.14, z + .24, .06, .012, .16);
    box(mat.black, x + .7, 1.12, z + .23, .11, .04, .16);
    // Upholstered task chairs with arms and five-spoke base.
    box(mat.chair, x, .62, z + 1.15, .65, .16, .6);
    box(mat.chair, x, 1.07, z + 1.45, .65, .9, .13);
    box(mat.rail, x, .31, z + 1.15, .09, .5, .09);
    for (const dx of [-.4, .4]) { box(mat.dark, x + dx, .83, z + 1.16, .08, .06, .45); box(mat.rail, x + dx, .67, z + 1.3, .04, .3, .04); }
    for (let spoke = 0; spoke < 5; spoke++) box(mat.dark, x, .11, z + 1.15, .85, .07, .07, spoke * Math.PI / 5);
  }
  // Rear technical cabinets and a narrow meeting/incident console.
  box(mat.blue, 14.6, .68, 5.65, 1.2, 1.15, 2.6);
  box(mat.blade, 14.6, 1.3, 5.65, 1.35, .1, 2.8);
  for (let z = 4.8; z < 6.6; z += .6) box(mat.rail, 14.6, .7, z, 1.22, .02, .02);
  box(mat.light, 9.8, .16, 7.14, 10.5, .025, .04);
  box(mat.light, 9.8, 4.15, -5.5, 8, .035, .07);
  box(mat.light, 9.8, 4.15, 3.5, 8, .035, .07);

  for (const [material, entries] of buckets) {
    const batch = new THREE.InstancedMesh(boxGeo, material, entries.length);
    entries.forEach((b, i) => {
      position.set(b.x, b.y, b.z); scale.set(b.w, b.h, b.d); matrix.compose(position, b.q, scale); batch.setMatrixAt(i, matrix);
    });
    batch.castShadow = ![mat.light, mat.cyan, mat.amber].includes(material); batch.receiveShadow = true; scene.add(batch);
  }

  let location = 'hall';
  const originalRoom = new THREE.Group();
  let requestMarker = null;
  let worldGeometry = null;
  const separation = {}, deskScreens = []; let deskKey = '', nocView = 'desk', cinematic = null;
  const CLIP = { hall: [new THREE.Plane(V(-1, 0, 0), 4.2)], noc: [new THREE.Plane(V(1, 0, 0), -4.12)] };
  const campusFog = new THREE.Fog(0x0b111b, 85, 230);
  if (options.worldMode) {
    for (const child of [...scene.children]) if (!child.isDirectionalLight && !child.isHemisphereLight) originalRoom.add(child);
    scene.add(originalRoom);
    const targetId = options.getState?.().request.rackId;
    const asset = facility.assets.find(a => a.id === targetId);
    if(asset) {
      requestMarker = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.5,3.35,1.68)),new THREE.LineBasicMaterial({color:0xf1c382,transparent:true,opacity:.8}));
      requestMarker.position.set(asset.x,1.75,asset.z); originalRoom.add(requestMarker);
    }
    worldGeometry = createWorldGeometry();
    scene.add(worldGeometry.world, worldGeometry.campus);
    worldGeometry.world.visible = false; worldGeometry.campus.visible = false;
    camera.far = 320; camera.updateProjectionMatrix();
    // The original room holds both spaces behind a glass partition at x = 4.15. In the world they are
    // separate buildings: each view clips away the other side and shows a solid boundary wall instead.
    const wallMat = new THREE.MeshStandardMaterial({ color: 0x3b4f62, metalness: .25, roughness: .62 });
    const makeWall = (x, signX, rot, text, sub) => {
      const g = new THREE.Group(), w = new THREE.Mesh(boxGeo, wallMat); w.scale.set(.1, 4.3, 21); w.position.set(x, 2.15, 0); w.receiveShadow = true; g.add(w);
      const s = new THREE.Mesh(new THREE.PlaneGeometry(3.6, .9), new THREE.MeshBasicMaterial({ map: labelTexture(text, sub, '#8af0d4'), toneMapped: false }));
      s.position.set(signX, 2.9, 4.2); s.rotation.y = rot; g.add(s);
      const door = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0x2f6f66, toneMapped: false })); door.scale.set(.02, 2.3, 1.6); door.position.set(signX, 1.15, 6.4); g.add(door);
      originalRoom.add(g); return g;
    };
    separation.hall = makeWall(4.07, 4.0, -Math.PI / 2, 'LINK → NOC', '연결 통로 · 관제동 (별도 건물)');
    separation.noc = makeWall(4.3, 4.37, Math.PI / 2, 'LINK → HALL 01', '연결 통로 · 서버동 01 (별도 건물)');
    // My desk: back-row centre console. Highlight rim, name plate and two monitors bound to the demo state.
    const desk = { x: 9.3, z: .2 };
    const rim = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2.85, .16, 1.38)), new THREE.LineBasicMaterial({ color: 0x8af0d4 }));
    rim.position.set(desk.x, 1.05, desk.z); originalRoom.add(rim);
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.5, .36), new THREE.MeshBasicMaterial({ map: labelTexture('MY DESK / 03', '운영 엔지니어 · 내 자리', '#8af0d4'), toneMapped: false }));
    plate.position.set(desk.x, .78, desk.z + .61); originalRoom.add(plate);
    for (const dx of [-.58, .58]) {
      const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 292;
      const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
      const screen = new THREE.Mesh(new THREE.PlaneGeometry(.98, .56), new THREE.MeshBasicMaterial({ map: texture, toneMapped: false }));
      screen.position.set(desk.x + dx, 1.67, desk.z - .245); originalRoom.add(screen); deskScreens.push({ canvas, texture, side: dx < 0 ? 'left' : 'right' });
    }
    // Colleagues at four other consoles: abstract silhouettes, so the room reads as staffed.
    const seats = [[6.2, -3.8], [9.3, -3.8], [12.4, -3.8], [6.2, .2]];
    const personMat = new THREE.MeshStandardMaterial({ color: 0x1e2c3b, roughness: .85, metalness: .1 });
    const bodies = new THREE.InstancedMesh(new THREE.CapsuleGeometry(.22, .45, 4, 10), personMat, seats.length), heads = new THREE.InstancedMesh(new THREE.SphereGeometry(.14, 14, 10), personMat, seats.length);
    seats.forEach(([x, z], i) => { bodies.setMatrixAt(i, new THREE.Matrix4().makeTranslation(x, 1.08, z + 1.08)); heads.setMatrixAt(i, new THREE.Matrix4().makeTranslation(x, 1.6, z + 1.0)); });
    bodies.castShadow = heads.castShadow = true; originalRoom.add(bodies, heads);
  }
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const ao = new SSAOPass(scene, camera, 1, 1); ao.kernelRadius = 8; ao.minDistance = .001; ao.maxDistance = .06; composer.addPass(ao);
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), .2, .45, 1.05); composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const fxaa = new ShaderPass(FXAAShader); composer.addPass(fxaa);

  let transition = null, hovered = null, pointerStart = null, lastWallUpdate = '', lastLedState = '', contextLost = false, visualElapsed = 0;
  const keys = new Set(), raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  const hoverLabel = document.querySelector('#hover-label');
  const viewPositions = {
    overview: { eye: [27, 25, 30], target: [-.5, 0, 0] },
    hall: { eye: [12, 19, 23], target: [-6.4, 1, -.4] },
    control: { eye: [20, 12, 17], target: [9.4, 1.3, -2] },
    aisle: { eye: [.9, 2.15, 2.25], target: [-10.5, 1.8, 2.25] },
  };
  if (options.worldMode) viewPositions.overview = { eye: [13, 20, 23], target: [-6.4, 0, -.4] };
  function moveTo(eye, target) {
    transition = { from: camera.position.clone(), to: V(...eye), targetFrom: controls.target.clone(), targetTo: V(...target), progress: 0 };
  }
  function view(name, immediate = false) {
    const v = viewPositions[name]; if (!v) return;
    if (immediate) { camera.position.set(...v.eye); controls.target.set(...v.target); controls.update(); transition = null; }
    else moveTo(v.eye, v.target);
  }
  function focus() {
    if (options.worldMode && location !== 'hall' && location !== 'noc') { setLocation(location); return; }
    const a = facility.assets.find(a => a.id === facility.selectedId);
    if (a) moveTo([a.x + 3.8, 4.4, a.z + 6], [a.x, 1.5, a.z]);
  }
  function hit(event) {
    const r = renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX - r.left) / r.width * 2 - 1, -(event.clientY - r.top) / r.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const objects = worldGeometry && ['world','campus'].includes(location) ? worldGeometry.pickables[location] : worldGeometry && location === 'noc' ? [] : selectable;
    const data = raycaster.intersectObjects(objects, false)[0]?.object.userData;
    return data?.pickId || data?.assetId;
  }
  renderer.domElement.addEventListener('pointerdown', e => { pointerStart = { x: e.clientX, y: e.clientY }; renderer.domElement.focus({ preventScroll: true }); transition = null; });
  renderer.domElement.addEventListener('pointerup', e => { if (e.button !== 0 || !pointerStart) return; if (Math.hypot(e.clientX - pointerStart.x, e.clientY - pointerStart.y) < 5) { const id = hit(e); if (id) { if (id.includes(':')) options.onPick?.(id); else onSelect(id); } } pointerStart = null; });
  renderer.domElement.addEventListener('pointermove', e => {
    hovered = hit(e); renderer.domElement.style.cursor = hovered ? 'pointer' : 'grab'; hoverLabel.hidden = !hovered || !!e.buttons;
    if (hovered) { const rect = container.getBoundingClientRect(); hoverLabel.textContent = hovered.includes(':') ? `${worldGeometry?.pickLabel(hovered)} · 선택` : `${hovered} · 장비 선택`; hoverLabel.style.left = `${Math.min(e.clientX - rect.left + 14, rect.width - 185)}px`; hoverLabel.style.top = `${e.clientY - rect.top - 38}px`; }
  });
  renderer.domElement.addEventListener('pointerleave', () => { hovered = null; hoverLabel.hidden = true; });
  renderer.domElement.addEventListener('keydown', e => { if (['KeyW','KeyA','KeyS','KeyD','KeyQ','KeyE','KeyF'].includes(e.code)) { e.preventDefault(); keys.add(e.code); if (e.code === 'KeyF') focus(); } });
  renderer.domElement.addEventListener('keyup', e => keys.delete(e.code));
  renderer.domElement.addEventListener('blur', () => keys.clear());
  renderer.domElement.addEventListener('webglcontextlost', e => { e.preventDefault(); contextLost = true; document.querySelector('#fatal').hidden = false; document.querySelector('#fatal').textContent = '그래픽 컨텍스트가 중단되었습니다. 페이지를 새로고침하여 가상 시설을 다시 시작하세요.'; });
  controls.addEventListener('start', () => { transition = null; });
  const observer = new ResizeObserver(() => resize()); observer.observe(container);
  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h); composer.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    const dpr = renderer.getPixelRatio(); fxaa.uniforms.resolution.value.set(1 / (w * dpr), 1 / (h * dpr));
  }
  resize();

  function drawWall() {
    const ctx = wallCanvas.getContext('2d'), w = wallCanvas.width, h = wallCanvas.height, t = totals(facility);
    ctx.fillStyle = '#061220'; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#1c3749'; ctx.lineWidth = 2;
    for (let x = 0; x < w; x += 80) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
    for (let y = 0; y < h; y += 64) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    ctx.fillStyle = '#9ee9e4'; ctx.font = '36px Consolas'; ctx.fillText('ULSAN / LIVE OPERATIONS', 50, 66);
    ctx.fillStyle = '#7996ac'; ctx.font = '20px Consolas'; ctx.fillText('SIMULATED TELEMETRY   /   PROTOTYPE 001', 53, 108);
    ctx.fillStyle = t.faults ? '#ff667c' : '#6de5c4'; ctx.font = '52px Consolas'; ctx.fillText(t.faults ? `INCIDENTS / ${t.faults}` : t.awaiting ? 'VERIFICATION REQUIRED' : 'SYSTEMS NOMINAL', 1050, 72);
    const labels = ['GPU ONLINE', 'POWER / kW', 'INLET / C'];
    [t.gpu, t.power.toFixed(1), t.temp.toFixed(1)].forEach((v, i) => {
      ctx.fillStyle = '#759ab4'; ctx.font = '22px Consolas'; ctx.fillText(labels[i], 60 + i * 320, 185);
      ctx.fillStyle = '#b9e5eb'; ctx.font = '66px Consolas'; ctx.fillText(String(v), 60 + i * 320, 265);
    });
    facility.assets.slice(0, 24).forEach((a, i) => {
      const x = 1090 + (i % 6) * 145, y = 170 + Math.floor(i / 6) * 120;
      ctx.fillStyle = '#' + new THREE.Color(C[a.state]).getHexString(); ctx.globalAlpha = .35; ctx.fillRect(x, y, 110, 70); ctx.globalAlpha = 1;
      ctx.fillStyle = '#b2dbeb'; ctx.font = '22px Consolas'; ctx.fillText(a.id, x + 18, y + 43);
    });
    for (let line = 0; line < 3; line++) {
      ctx.strokeStyle = ['#64d9c9', '#89a1e8', '#e1b96a'][line]; ctx.lineWidth = 3; ctx.beginPath();
      for (let x = 50; x < 965; x += 8) {
        const y = 410 + line * 105 + Math.sin(x * .015 + line + facility.elapsed * .15) * 18 + Math.sin(x * .051 + line) * 9;
        if (x === 50) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      } ctx.stroke();
    }
    ctx.fillStyle = '#8faabd'; ctx.font = '20px Consolas'; ctx.fillText('POWER FEED A/B    |    COLD AISLE    |    CORE UPLINK', 50, 735);
    if (options.getState) {
      const request = options.getState().request;
      ctx.fillStyle = '#071a29'; ctx.fillRect(40, 295, 950, 58);
      ctx.fillStyle = '#a0e4d4'; ctx.font = '25px Consolas';
      ctx.fillText(`${request.id} / ${request.rackId} / ${request.phase.toUpperCase()} / ${request.progress}%   AUX COOLING ${({on:'ON',off:'OFF',warn:'WARN'})[options.getState().ops?.cooling.mode] || '-'}`, 55, 333);
    }
    const event = facility.events[0]; ctx.fillText(`${Math.floor(event.time)}s / ${event.text.replace(/[^\x00-\x7F]/g, '').slice(0, 75)}`, 1050, 735);
    wallTexture.needsUpdate = true;
  }
  // My two desk monitors redraw only when the shared state they show changes.
  function drawDeskScreens() {
    const s = options.getState(), r = s.request, cool = s.ops.cooling.mode, t = totals(facility);
    const key = `${r.phase}:${r.progress}:${cool}:${t.gpu}`; if (key === deskKey || !deskScreens.length) return; deskKey = key;
    for (const { canvas, texture, side } of deskScreens) {
      const c = canvas.getContext('2d'); c.fillStyle = '#061626'; c.fillRect(0, 0, 512, 292); c.fillStyle = '#8af0d4'; c.fillRect(0, 0, 512, 6);
      c.font = '22px Consolas, monospace'; c.fillStyle = '#7fa3bb';
      if (side === 'left') {
        c.fillText('MY INBOX / 1 REQUEST', 22, 44);
        c.fillStyle = r.phase === 'new' ? '#f3c37b' : ['fault','repairing'].includes(r.phase) ? '#ff8a9a' : '#b9f0e0'; c.font = '40px Consolas, monospace'; c.fillText(r.id, 22, 110);
        c.font = '26px Consolas, monospace'; c.fillStyle = '#c8dbe7'; c.fillText(`${r.customerId} / ${r.rackId}`, 22, 156); c.fillText(`${r.phase.toUpperCase()} · ${r.progress}%`, 22, 200);
        c.fillStyle = '#1f3a4a'; c.fillRect(22, 232, 468, 16); c.fillStyle = '#6fe7d2'; c.fillRect(22, 232, 468 * r.progress / 100, 16);
      } else {
        c.fillText('FACILITY WATCH', 22, 44); c.font = '27px Consolas, monospace';
        const rows = [['GPU ONLINE', `${t.gpu}/192`, '#b9f0e0'], ['UPLINK', ['fault','repairing'].includes(r.phase) ? 'DOWN' : 'OK', ['fault','repairing'].includes(r.phase) ? '#ff8a9a' : '#b9f0e0'], ['AUX COOLING', cool === 'on' ? 'ON' : cool === 'warn' ? 'WARN' : 'OFF', cool === 'on' ? '#6fe7d2' : cool === 'warn' ? '#ffad5c' : '#8796a3'], ['UPS', 'STANDBY', '#b9f0e0']];
        rows.forEach(([k, v, col], i) => { c.fillStyle = '#9fb6c6'; c.fillText(k, 22, 100 + i * 48); c.fillStyle = col; c.fillText(v, 300, 100 + i * 48); });
      }
      texture.needsUpdate = true;
    }
  }
  function animate(dt) {
    if (contextLost) return;
    visualElapsed = options.worldMode ? visualElapsed + dt : facility.elapsed;
    worldGeometry?.update(visualElapsed, options.getState());
    if(requestMarker) requestMarker.visible = location === 'hall' && !['new','reviewed'].includes(options.getState().request.phase);
    if (cinematic) {
      const k = cinematic.keys[cinematic.index]; cinematic.t = (performance.now() - cinematic.segmentStart) / 1000; cinematic.frames++;
      const p = Math.min(1, cinematic.t / k.duration), e = p * p * (3 - 2 * p);
      camera.position.lerpVectors(V(...k.from.eye), V(...k.to.eye), e); controls.target.lerpVectors(V(...k.from.target), V(...k.to.target), e);
      camera.lookAt(controls.target);
      if (p >= 1) nextSegment();
    }
    if (options.worldMode) drawDeskScreens();
    if (transition) {
      transition.progress = Math.min(1, transition.progress + dt / 1.15);
      const k = transition.progress * transition.progress * (3 - 2 * transition.progress);
      camera.position.lerpVectors(transition.from, transition.to, k); controls.target.lerpVectors(transition.targetFrom, transition.targetTo, k);
      if (transition.progress === 1) transition = null;
    }
    if (keys.size && !transition) {
      const forward = camera.getWorldDirection(V(0, 0, 0)); forward.y = 0; forward.normalize();
      const right = forward.clone().cross(V(0, 1, 0)); const move = V(0, 0, 0);
      if (keys.has('KeyW')) move.add(forward); if (keys.has('KeyS')) move.sub(forward);
      if (keys.has('KeyD')) move.add(right); if (keys.has('KeyA')) move.sub(right);
      if (keys.has('KeyQ')) move.y -= 1; if (keys.has('KeyE')) move.y += 1;
      move.multiplyScalar(dt * 5); controls.target.add(move); camera.position.add(move);
      controls.target.x = THREE.MathUtils.clamp(controls.target.x, -20, 20); controls.target.z = THREE.MathUtils.clamp(controls.target.z, -15, 15);
    }
    controls.update();
    for (const a of facility.assets) {
      const v = visuals.get(a.id), color = C[a.state], bad = a.state === 'fault', fixing = a.state === 'repairing';
      v.strip.material.color.setHex(color); v.ring.visible = a.id === facility.selectedId;
      v.halo.color.setHex(color); v.halo.intensity = bad ? 4 + Math.sin(visualElapsed * 6) * 2 : fixing ? 2.5 + Math.sin(visualElapsed * 4) : .7;
      v.strip.material.color.multiplyScalar(bad ? .7 + Math.sin(visualElapsed * 6) * .25 : 1);
      v.netMat.color.setHex((bad || fixing) && a.fault === 'network' ? C[a.state] : 0x497caa);
      v.pwrMat.color.setHex((bad || fixing) && a.fault === 'power' ? C[a.state] : 0xc29d5c);
    }
    const ledState = facility.assets.map(a => a.state + a.fault).join('|');
    if (ledState !== lastLedState) {
      facility.assets.slice(0, 24).forEach((a, index) => { for (let i = 0; i < 20; i++) leds.setColorAt(index * 20 + i, new THREE.Color(readings(a).power === 0 ? 0x16232b : C[a.state])); });
      leds.instanceColor.needsUpdate = true; lastLedState = ledState;
    }
    for (const p of particles) {
      p.mesh.visible = readings(p.asset).network > 0;
      if (p.mesh.visible) p.mesh.position.copy(p.curve.getPointAt((visualElapsed * .15 + p.offset) % 1));
    }
    for (const f of flows) {
      const coolingFault = f.asset.fault === 'cooling' && ['fault','repairing'].includes(f.asset.state);
      f.mesh.position.y = .15 + ((visualElapsed * .43 + f.offset) % 1) * 1.8;
      f.mesh.material.color.setHex(coolingFault ? 0xffb578 : 0x79dce5);
      f.mesh.material.opacity = coolingFault ? .25 : .48;
    }
    const wallKey = `${Math.floor(visualElapsed)}:${options.getState?.().request.phase || ''}:${options.getState?.().ops?.cooling.mode || ''}`;
    if (wallKey !== lastWallUpdate) { drawWall(); lastWallUpdate = wallKey; }
    renderer.info.reset(); composer.render();
  }
  function snapshot() {
    const gl = renderer.getContext(), debug = gl.getExtension('WEBGL_debug_renderer_info');
    return { renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
      webgl: gl.getParameter(gl.VERSION), width: renderer.domElement.width, height: renderer.domElement.height, dpr: renderer.getPixelRatio(),
      calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures,
      camera: camera.position.toArray(), target: controls.target.toArray(), contextLost, location,
      quality: 'Desktop High · 2048 shadow · SSAO · bloom · FXAA · DPR ≤ 2',
      layers: { network: netLayer.visible, cooling: coolLayer.visible, power: powerLayer.visible },
      nocView, clip: renderer.clippingPlanes.map(p => ({ normal: p.normal.toArray(), constant: p.constant })), fog: !!scene.fog, cinematic: !!cinematic };
  }
  // GPU timing is asynchronous, with the disjoint extension; no forced GPU synchronization.
  const gl = renderer.getContext(), timerExt = gl.getExtension('EXT_disjoint_timer_query_webgl2');
  let pendingQuery = null, activeQuery = null, lastGpuMs = null;
  function beginGpuTimer() {
    if (!timerExt || pendingQuery || activeQuery) return;
    activeQuery = gl.createQuery(); gl.beginQuery(timerExt.TIME_ELAPSED_EXT, activeQuery);
  }
  function endGpuTimer() { if (activeQuery) { gl.endQuery(timerExt.TIME_ELAPSED_EXT); pendingQuery = activeQuery; activeQuery = null; } }
  function pollGpuTimer() {
    if (pendingQuery && gl.getQueryParameter(pendingQuery, gl.QUERY_RESULT_AVAILABLE)) {
      if (!gl.getParameter(timerExt.GPU_DISJOINT_EXT)) lastGpuMs = gl.getQueryParameter(pendingQuery, gl.QUERY_RESULT) / 1e6;
      gl.deleteQuery(pendingQuery); pendingQuery = null;
    }
    return lastGpuMs;
  }
  function projectAsset(id) {
    const a = facility.assets.find(a => a.id === id); if (!a) return null;
    const v = V(a.x, 1.7, a.z + .7).project(camera), r = renderer.domElement.getBoundingClientRect();
    return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height, visible: v.z > -1 && v.z < 1 };
  }
  // Visibility, clipping and fog for one space; no camera change.
  function showLocation(next) {
    location = next; keys.clear(); hoverLabel.hidden = true; pointerStart = null;
    originalRoom.visible = next === 'noc' || next === 'hall';
    worldGeometry.world.visible = next === 'world'; worldGeometry.campus.visible = next === 'campus';
    renderer.clippingPlanes = CLIP[next] || [];
    separation.hall.visible = next === 'hall'; separation.noc.visible = next === 'noc';
    scene.fog = next === 'campus' ? campusFog : null;
  }
  function setLocation(next, immediate = false, view = nocView) {
    if (!worldGeometry || !['world','noc','campus','hall'].includes(next) || cinematic) return false;
    if (view === 'desk' || view === 'overview') nocView = view;
    showLocation(next);
    const positions = { world: {eye:[0,35,19], target:[0,0,0]}, campus:{eye:[29,28,31],target:[0,0,0]}, noc: nocView === 'desk' ? DESK_POSE : NOC_OVERVIEW_POSE, hall:viewPositions.overview };
    const p = positions[next];
    if(immediate) {camera.position.set(...p.eye);controls.target.set(...p.target);transition=null;controls.update();}
    else moveTo(p.eye,p.target);
    return true;
  }
  // Cinematic camera path. Each key may switch space; camera input is disabled until it ends or is skipped.
  function playCinematic(keysList, { onSegment, onDone } = {}) {
    if (!worldGeometry || !keysList.length) return false;
    cinematic = { keys: keysList, index: -1, t: 0, onSegment, onDone, frames: 0, started: performance.now(), segmentStart: performance.now() };
    transition = null; controls.enabled = false; nextSegment(); return true;
  }
  function nextSegment() {
    const c = cinematic; c.index++; c.t = 0; c.segmentStart = performance.now();
    if (c.index >= c.keys.length) { const done = c.onDone; stopCinematic(); done?.(false); return; }
    const k = c.keys[c.index]; if (k.location !== location) showLocation(k.location);
    camera.position.set(...k.from.eye); controls.target.set(...k.from.target); camera.lookAt(controls.target);
    c.onSegment?.(c.index, k);
  }
  function stopCinematic() { if (!cinematic) return false; cinematic = null; controls.enabled = true; return true; }
  return { renderer, animate, view, focus, snapshot, beginGpuTimer, endGpuTimer, pollGpuTimer, projectAsset, setLocation, playCinematic, stopCinematic,
    cinematicState: () => cinematic && { index: cinematic.index, t: cinematic.t, location },
    coolingVisual: () => worldGeometry?.coolingVisual() ?? null,
    deskScreenKey: () => deskKey,
    focusWorld(id) { const p = worldGeometry?.focusPoint(location,id); if(!p)return false; const offset=location==='world'?[0,16,10]:[12,12,14];moveTo([p.x+offset[0],p.y+offset[1],p.z+offset[2]],[p.x,p.y,p.z]);return true; },
    projectWorld: id => worldGeometry?.project(location, id, camera, renderer.domElement.getBoundingClientRect()),
    worldMarker: id => worldGeometry?.markerColor(id) ?? null,
    setLayer(name, visible) { ({ network: netLayer, cooling: coolLayer, power: powerLayer })[name].visible = visible; },
    visuals: () => Object.fromEntries(facility.assets.map(a => [a.id, { color: visuals.get(a.id).strip.material.color.getHexString(), selected: visuals.get(a.id).ring.visible, networkFlow: readings(a).network > 0 }])) };
}
