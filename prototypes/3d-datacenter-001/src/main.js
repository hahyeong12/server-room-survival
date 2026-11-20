import './style.css';
import { createFacility, selected, selectAsset, injectFault, startRepair, verify, advance, readings, totals, STATES, FAULTS, REPAIR_SECONDS } from './model.js';
import { createScene } from './scene.js';

const $ = id => document.getElementById(id), facility = createFacility();
const kindNames = { rack: 'GPU COMPUTE RACK', power: 'POWER DISTRIBUTION', cooling: 'COOLING SYSTEM', network: 'NETWORK CORE' };
let scene, uiSignature = '', perfExpanded = false, lastUi = 0, lastFrame = performance.now(), lastPerf = lastFrame, frameIndex = 0;
const frames = [], gpuSamples = [];
const stats = { fps: 0, p95FrameMs: 0, averageFrameMs: 0, gpuMs: null, frameCount: 0 };

for (const a of facility.assets) {
  const option = document.createElement('option'); option.value = a.id; option.textContent = a.name; $('equipment-select').append(option);
  if (a.kind === 'rack') {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = a.id;
    b.setAttribute('aria-label', `${a.name} 선택`); b.dataset.asset = a.id; b.addEventListener('click', () => choose(a.id)); $('mini-map').append(b);
  }
}
function choose(id) { if (selectAsset(facility, id)) updateUI(); }
$('equipment-select').addEventListener('change', e => choose(e.target.value));
$('inject-fault').addEventListener('click', () => { injectFault(facility, $('fault-kind').value); updateUI(); });
$('start-repair').addEventListener('click', () => { startRepair(facility); updateUI(); });
$('verify').addEventListener('click', () => { verify(facility); updateUI(); });
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
  scene.view(b.dataset.view); document.querySelectorAll('[data-view]').forEach(x => x.classList.toggle('active', x === b));
}));
document.querySelectorAll('[data-layer]').forEach(b => b.addEventListener('click', () => {
  const on = b.getAttribute('aria-pressed') !== 'true'; b.setAttribute('aria-pressed', String(on)); b.classList.toggle('active', on); scene.setLayer(b.dataset.layer, on);
}));
$('perf-toggle').addEventListener('click', () => { perfExpanded = !perfExpanded; $('perf-panel').hidden = !perfExpanded; $('perf-toggle').setAttribute('aria-expanded', String(perfExpanded)); });

function updateUI() {
  const a = selected(facility), r = readings(a), sum = totals(facility);
  const signature = JSON.stringify([a, sum, facility.events[0]]);
  if (signature !== uiSignature) {
    $('equipment-select').value = a.id; $('asset-name').textContent = a.name; $('asset-kind').textContent = kindNames[a.kind]; $('asset-location').textContent = a.location;
    $('asset-count').textContent = `${String(facility.assets.indexOf(a) + 1).padStart(2, '0')} / 28`;
    $('status-card').dataset.state = a.state; $('status-title').textContent = STATES[a.state];
    $('status-icon').textContent = ({ normal: '✓', fault: '!', repairing: '↻', awaiting: '?', verified: '✓' })[a.state];
    $('status-detail').textContent = ({ normal: '모든 가상 센서가 정상 범위입니다.', fault: `${FAULTS[a.fault]} · 영향 지표를 확인하세요.`, repairing: `${FAULTS[a.fault]} · 처리 중에는 장애 영향이 유지됩니다.`, awaiting: '지표 회복 · 아래 버튼으로 사후 상태를 확인하세요.', verified: '전력·유입 온도·업링크 정상 범위 확인 완료.' })[a.state];
    $('gpu-value').innerHTML = `${r.gpu}<span>%</span>`; $('gpu-meter').style.width = `${r.gpu}%`;
    $('gpu-description').textContent = a.kind === 'rack' ? `8 × 가상 GPU · ${r.online === 0 ? 'OFFLINE' : r.gpu < 30 ? 'THROTTLED / IDLE' : 'RUNNING'}` : '기반 설비 · 연산 GPU 없음';
    $('power-value').innerHTML = `${r.power.toFixed(1)}<span>kW</span>`; $('power-meter').style.width = `${r.power / 24 * 100}%`;
    $('temp-value').innerHTML = `${r.temp.toFixed(1)}<small>°C</small>`; $('temp-value').style.color = r.temp > 30 ? '#ffae76' : '';
    $('network-value').innerHTML = `${r.network}<small>Gbps</small>`;
    $('inject-fault').disabled = !['normal','verified'].includes(a.state); $('fault-kind').disabled = $('inject-fault').disabled;
    $('start-repair').disabled = a.state !== 'fault'; $('verify').disabled = a.state !== 'awaiting';
    $('verify').textContent = a.state === 'verified' ? '✓ 사후 상태 확인 완료' : '사후 상태 확인';
    $('total-gpu').innerHTML = `${sum.gpu} <small>ONLINE</small>`; $('total-power').innerHTML = `${sum.power.toFixed(0)} <small>kW</small>`;
    $('total-temp').innerHTML = `${sum.temp.toFixed(1)} <small>°C</small>`; $('total-faults').textContent = String(sum.faults).padStart(2, '0');
    $('facility-status').textContent = sum.faults ? `장애 대응 ${sum.faults}건` : sum.awaiting ? `사후 확인 ${sum.awaiting}건` : '정상 운영';
    $('facility-status').style.color = sum.faults ? '#ff8994' : sum.awaiting ? '#90beff' : '';
    document.querySelectorAll('[data-asset]').forEach(b => { const asset = facility.assets.find(x => x.id === b.dataset.asset); b.dataset.state = asset.state; b.classList.toggle('selected', a.id === asset.id); b.setAttribute('aria-pressed', String(a.id === asset.id)); b.title = `${asset.name} · ${STATES[asset.state]}`; });
    const event = facility.events[0]; $('event-text').textContent = event.text; $('event-time').textContent = formatTime(event.time);
    uiSignature = signature;
  }
  document.querySelector('.repair-track').hidden = a.state !== 'repairing';
  $('repair-bar').style.width = `${a.repairElapsed / REPAIR_SECONDS * 100}%`;
  $('clock').textContent = new Date().toLocaleTimeString('ko-KR', { hour12: false });
}
function formatTime(s) { return `${String(Math.floor(s / 3600)).padStart(2,'0')}:${String(Math.floor(s / 60) % 60).padStart(2,'0')}:${String(Math.floor(s) % 60).padStart(2,'0')}`; }

try {
  scene = createScene($('viewport'), facility, choose); updateUI(); $('loading').hidden = true;
  // Read-only QA surface: state changes must use the actual UI handlers.
  window.prototypeQA = Object.freeze({
    snapshot: () => ({ facility: structuredClone(facility), renderer: scene.snapshot(), stats: { ...stats }, heap: performance.memory ? { used: performance.memory.usedJSHeapSize, total: performance.memory.totalJSHeapSize, limit: performance.memory.jsHeapSizeLimit } : null, visuals: scene.visuals() }),
    projectAsset: id => scene.projectAsset(id),
  });
  function frame(now) {
    const rawDt = (now - lastFrame) / 1000, dt = Math.min(rawDt, .1); lastFrame = now;
    // Background tabs pause the demonstration clock instead of completing repairs invisibly.
    if (!document.hidden) {
      const previousEvent = facility.events[0];
      advance(facility, dt);
      if (facility.events[0] !== previousEvent) updateUI();
      scene.pollGpuTimer();
      const timed = frameIndex % 30 === 0; if (timed) scene.beginGpuTimer();
      scene.animate(dt); if (timed) scene.endGpuTimer();
      const gpuMs = scene.pollGpuTimer(); if (gpuMs !== null && timed) { gpuSamples.push(gpuMs); if (gpuSamples.length > 60) gpuSamples.shift(); }
      frames.push(rawDt * 1000); if (frames.length > 300) frames.shift();
      if (now - lastUi > 200) { updateUI(); lastUi = now; }
      if (now - lastPerf > 1000) {
        const sorted = [...frames].sort((a,b) => a-b), average = frames.reduce((s,x) => s+x,0) / frames.length;
        Object.assign(stats, { fps: 1000 / average, averageFrameMs: average, p95FrameMs: sorted[Math.floor(sorted.length * .95)], gpuMs: gpuSamples.length ? gpuSamples.reduce((s,x) => s+x,0) / gpuSamples.length : null, frameCount: frameIndex });
        const snap = scene.snapshot(), heap = performance.memory ? performance.memory.usedJSHeapSize / 1048576 : null;
        $('performance').textContent = `${stats.fps.toFixed(0)} FPS / ${snap.width}×${snap.height} / DESKTOP HIGH`;
        $('perf-panel').textContent = `${snap.quality}\n${snap.renderer}\nFPS ${stats.fps.toFixed(1)} / p95 frame ${stats.p95FrameMs.toFixed(2)} ms\nGPU frame ${stats.gpuMs === null ? '측정 불가' : stats.gpuMs.toFixed(2)+' ms'} / JS heap ${heap === null ? '측정 불가' : heap.toFixed(1)+' MiB'}\nDraw calls (all passes) ${snap.calls} / triangles ${snap.triangles.toLocaleString()}\nGeometries ${snap.geometries} / textures ${snap.textures}\nGPU 점유율·전용 VRAM은 NVIDIA-SMI 별도 계측\nJS heap은 VRAM 또는 브라우저 전체 메모리가 아닙니다.`;
        lastPerf = now;
      }
      frameIndex++;
    }
    requestAnimationFrame(frame);
  }
  document.addEventListener('visibilitychange', () => { lastFrame = performance.now(); });
  requestAnimationFrame(frame);
} catch (error) {
  $('loading').hidden = true; $('fatal').hidden = false;
  $('fatal').textContent = `3D 초기화 실패: ${error.message}. 하드웨어 가속을 지원하는 최신 데스크톱 브라우저로 확인해 주세요.`;
  console.error(error);
}
