import './world.css';
import {createScene} from './scene.js';
import {createWorldStore,LOCATIONS,COUNTRIES,FACILITIES,FIXTURE,PHASES,breadcrumbs} from './world-store.js';
import {readings,totals,STATES} from './model.js';
import {nextDemoStep,demoBlocker} from './demo-actions.js';

document.querySelector('#app').innerHTML=`
<header class="topbar"><a class="brand" href="#world"><span class="brand-icon">▤</span><span>SERVER ROOM<span class="brand-sub">SURVIVAL / CONNECTED WORLD</span></span></a><div class="mode-badge">시연 모드 · 가상 요청 데이터</div><div class="top-right"><span>ULSAN · AIDC</span><button id="help-open">플레이 안내</button></div></header>
<div class="routebar"><button id="back" aria-label="상위 공간으로 복귀">상위 공간</button><nav id="breadcrumbs" aria-label="현재 위치"></nav><span class="route-note">탐색은 작업을 진행하지 않습니다</span></div>
<main>
<section id="viewport" aria-label="3D 세계 탐색"><div class="scene-heading"><div id="scene-eyebrow" class="eyebrow"></div><h1 id="scene-title"></h1><p id="scene-description"></p></div>
<nav id="places" aria-label="공간 이동"><button data-route="world">세계지도</button><button data-route="noc">관제실</button><button data-route="campus">시설 지도</button><button data-route="hall">서버실</button></nav>
<div id="map-legend"><span><i></i>울산 운영 허브</span><span><i class="sg"></i>싱가포르 요청</span><span>연결선은 교육용 가상 경로입니다</span></div>
<div id="hall-tools" hidden><button data-camera="overview">전체 시설</button><button data-camera="hall">랙 보기</button><button data-camera="aisle">통로</button><button id="focus-rack">선택 장비 보기</button><div class="layer-tools"><button data-layer="network" aria-pressed="true">네트워크</button><button data-layer="cooling" aria-pressed="true">냉각</button><button data-layer="power" aria-pressed="true">전력</button></div></div>
<div id="world-country-labels"></div><div id="hover-label" hidden></div><div id="loading">3D 세계 준비 중…</div><div id="fatal" role="alert" hidden></div>
<div class="scene-caption"><b id="scene-code"></b><span id="scene-footnote"></span><span class="caption-line"></span><span>DESKTOP HIGH</span></div>
<div class="camera-help"><kbd>드래그</kbd> 회전 <kbd>우클릭</kbd> 이동 <kbd>휠</kbd> 확대 <kbd>W A S D</kbd> 이동 <kbd>F</kbd> 초점</div></section>
<aside id="panel" aria-label="현재 공간과 고객 요청"><div class="panel-label"><span id="panel-eyebrow">OPERATIONS</span><span id="request-counter">1 REQUEST</span></div><div id="context-panel"></div>
<section class="request-card"><div class="request-card-top"><span>SG / SINGAPORE</span><span id="phase-chip" class="chip"></span></div><h2>싱가포르 고객 요청</h2><div class="identity"><strong data-request-id></strong><span data-customer-id></span></div><p class="workload" id="request-workload"></p><div class="original-label">원래 요청 조건 · 시연 전용</div><div class="terms"><div><strong data-term="gpu"></strong><span>가상 GPU</span></div><div><strong><b data-term="powerKW"></b><small>kW</small></strong><span>가상 전력</span></div><div><strong><b data-term="networkGbps"></b><small>Gbps</small></strong><span>필요 대역폭</span></div></div><p class="terms-note" id="terms-note"></p><div class="assigned"><span>처리 위치</span><strong id="request-location"></strong></div>
<div class="progress-label"><span id="progress-text">접수 전</span><strong id="progress-value">0%</strong></div><div class="progress-track"><i id="progress-bar"></i></div>
<div class="step-note" id="step-note"></div><div id="request-actions"></div><div id="action-feedback" role="status" aria-live="polite"></div></section>
<section id="asset-panel" hidden></section><section class="mini-status"><div><span>링크 상태</span><strong id="link-status">정상</strong></div><div><span>가상 GPU 온라인</span><strong id="gpu-online">192 / 192</strong></div><div><span>시연 진행</span><strong id="step-count">0회</strong></div></section><p class="panel-note">가상 요청을 사용하는 독립 시연입니다. 이동·대기·카메라 조작으로 작업이 진행되지 않습니다.</p></aside>
<section class="mission-strip"><div class="mission-title"><span class="eyebrow">ONE REQUEST / FOUR SPACES</span><strong id="objective">싱가포르의 새 요청을 확인하세요</strong><p id="objective-detail">세계지도에서 고객과 울산 AIDC의 관계를 살펴보세요.</p></div><div class="flow"><span data-step="world">세계지도</span><i></i><span data-step="noc">관제실</span><i></i><span data-step="campus">시설 지도</span><i></i><span data-step="hall">서버실</span></div><div class="mission-id"><strong data-request-id></strong><span>가상 고객 요청 1건</span></div></section>
</main><footer><span><b>WORLD SKELETON / PHASE 0–2</b> · 기존 엔진 미연결</span><span id="performance">성능 측정 중…</span><button id="perf-toggle" aria-expanded="false">성능 상세</button><a href="./lab.html">기존 3D 실험실</a></footer><div id="perf-panel" hidden></div>
<dialog id="help"><button id="help-close" aria-label="안내 닫기">닫기</button><span class="eyebrow">시연 플레이 안내</span><h2>한 고객의 요청을 따라가 보세요.</h2><ol><li>세계지도에서 싱가포르를 선택하고 요청을 확인합니다.</li><li>울산 관제실에서 원래 조건을 읽고 접수합니다.</li><li>시설 지도에서 서버동 01을 선택해 들어갑니다.</li><li>랙 D-06을 선택하고 시연 작업을 시작합니다.</li><li>다음 단계 버튼으로 장애·복구·사후 확인을 살펴봅니다.</li><li>관제실과 세계지도로 돌아가 같은 요청 상태를 확인합니다.</li></ol><p>모든 진행은 명시적 클릭으로만 일어납니다. 아무리 기다려도 자동으로 완료되지 않습니다. 새로고침하면 이 시연만 초기화됩니다.</p><p>3D 화면에 포커스를 둔 뒤 W/A/S/D로 이동, Q/E로 높이 조절, F로 초점을 맞출 수 있습니다. 카메라 충돌 판정은 없습니다.</p></dialog>`;

const $=id=>document.getElementById(id),store=createWorldStore();
let scene,lastRoute=null,resultScrolledFor=null,visualSeconds=0,frame=0,lastTime=performance.now(),lastPerf=0,perfOpen=false;
const frameTimes=[],gpuTimes=[];let stats={fps:0,p95FrameMs:0,gpuMs:null};
const descriptions={world:'세계의 고객, 그리고 울산의 하나의 데이터센터.',noc:'요청을 검토하고, 시설과 작업의 상태를 연결하세요.',campus:'전력에서 냉각까지. 하나의 작업을 뒷받침하는 시설들.',hall:'요청이 처리되는 물리적 위치를 직접 확인하세요.'};
const notes={world:'Made with Natural Earth / 연결 경로는 가상',noc:'기존 관제실 재사용 / 화면과 HUD는 동일 상태',campus:'직접 제작한 시설 배치 / 실제 울산 설계 아님',hall:'기존 24랙·장비·가상 센서 재사용'};
function button(text,handler,primary=false,id){const b=document.createElement('button');b.textContent=text;b.className=primary?'primary':'';if(id)b.id=id;b.addEventListener('click',handler);return b;}
function navigate(route){if(store.navigate(route)){if(location.hash!==`#${route}`)location.hash=route;}}
document.querySelectorAll('[data-route]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.route)));
$('back').addEventListener('click',()=>{const p=LOCATIONS[store.state.navigation.route].parent;if(p)navigate(p);});
window.addEventListener('hashchange',()=>{const route=location.hash.slice(1);if(!store.navigate(route)){history.replaceState(null,'','#world');store.navigate('world');}});
$('help-open').addEventListener('click',()=>$('help').showModal());$('help-close').addEventListener('click',()=>$('help').close());
$('perf-toggle').addEventListener('click',()=>{perfOpen=!perfOpen;$('perf-panel').hidden=!perfOpen;$('perf-toggle').setAttribute('aria-expanded',String(perfOpen));});
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>scene.view(b.dataset.camera)));
$('focus-rack').addEventListener('click',()=>scene.focus());
document.querySelectorAll('[data-layer]').forEach(b=>b.addEventListener('click',()=>{const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));scene.setLayer(b.dataset.layer,on);}));

function contextPanel(){
  const state=store.state,route=state.navigation.route,root=$('context-panel');root.replaceChildren();
  if(route==='world'){
    const title=document.createElement('h2');title.textContent=COUNTRIES[state.navigation.country].name;root.append(title);
    const countries=document.createElement('div');countries.className='countries';
    for(const [id,c]of Object.entries(COUNTRIES)){const b=button(id,()=>store.selectCountry(id),id===state.navigation.country);b.dataset.country=id;b.setAttribute('aria-label',`${c.name} 선택`);countries.append(b);}root.append(countries);
    const p=document.createElement('p');p.textContent=state.navigation.country==='SG'?'새 고객 요청 1건이 울산 AIDC에 도착했습니다.':state.navigation.country==='KR'?'고객 작업을 처리하는 울산 운영 거점입니다.':'이 국가에는 활성 요청이 없습니다. 이번 시연은 싱가포르 한 건만 제공합니다.';root.append(p);
    root.append(button('울산 관제실 진입',()=>navigate('noc'),false,'enter-noc'));
    root.append(button('선택 거점 가까이 보기',()=>scene.focusWorld(state.navigation.country),false,'focus-country'));
  }else if(route==='noc'){
    root.innerHTML=`<h2>울산 AIDC 관제실</h2><p>한 요청의 접수부터 결과까지 확인하는 운영 거점입니다.</p><div class="inbox-row"><span>요청함</span><strong>SG · 1건 · ${PHASES[state.request.phase]}</strong></div>`;
    root.append(button('연결 시설 살펴보기',()=>navigate('campus'),false,'enter-campus'));
  }else if(route==='campus'){
    const list=document.createElement('div');list.className='facility-list';
    for(const [id,f]of Object.entries(FACILITIES)){const b=button(f.name,()=>store.selectFacility(id),id===state.navigation.facility);b.dataset.facility=id;list.append(b);}root.append(list);
    const f=FACILITIES[state.navigation.facility],heading=document.createElement('h2');heading.textContent=f.name;root.append(heading);const p=document.createElement('p');p.textContent=f.description;root.append(p);
    root.append(button('선택 시설 가까이 보기',()=>scene.focusWorld(state.navigation.facility),false,'focus-facility'));
    if(f.target)root.append(button(f.target==='hall'?'서버동 01 진입':'관제실로 이동',()=>navigate(f.target),false,'enter-building'));
  }else{
    root.innerHTML='<h2>서버실 01</h2><p>싱가포르 요청의 목적지는 랙 D-06입니다. 실제 3D 장비를 클릭하거나 아래 목록에서 선택하세요.</p>';
    const label=document.createElement('label');label.textContent='장비 선택';const select=document.createElement('select');select.id='equipment-select';select.setAttribute('aria-label','장비 선택');
    for(const a of state.facility.assets){const o=document.createElement('option');o.value=a.id;o.textContent=a.name;select.append(o);}select.value=state.facility.selectedId;select.addEventListener('change',()=>store.selectRack(select.value));label.append(select);root.append(label);
    root.append(button('요청 랙 D-06 찾기',()=>{store.selectRack(FIXTURE.rackId);scene.focus();},false,'locate-rack'));
  }
}
function render(){
  const state=store.state,route=state.navigation.route,r=state.request;
  if(scene&&lastRoute!==route){scene.setLocation(route,lastRoute===null);lastRoute=route;}
  $('scene-eyebrow').textContent=LOCATIONS[route].subtitle;$('scene-title').textContent=LOCATIONS[route].title;$('scene-description').textContent=descriptions[route];
  $('scene-code').textContent=({world:'GLOBAL / 01',noc:'NOC / 01',campus:'ULSAN / 01',hall:'HALL / 01'})[route];$('scene-footnote').textContent=notes[route];
  $('hall-tools').hidden=route!=='hall';$('map-legend').hidden=route!=='world';$('back').disabled=route==='world';
  $('breadcrumbs').replaceChildren(...breadcrumbs(route).map(x=>{const b=button(x.title,()=>navigate(x.id));b.dataset.crumb=x.id;if(x.id===route)b.setAttribute('aria-current','location');return b;}));
  document.querySelectorAll('[data-route],[data-step]').forEach(b=>b.classList.toggle('active',(b.dataset.route||b.dataset.step)===route));
  document.querySelectorAll('[data-request-id]').forEach(x=>x.textContent=r.id);document.querySelectorAll('[data-customer-id]').forEach(x=>x.textContent=r.customerId);
  document.querySelectorAll('[data-term]').forEach(x=>x.textContent=r.terms[x.dataset.term]);
  $('request-workload').textContent=r.workload;$('terms-note').textContent=`${r.terms.mode} 모드 · ${r.terms.deadline}`;$('request-location').textContent=`${r.facilityId} / ${r.buildingId} / ${r.rackId}`;
  $('phase-chip').textContent=PHASES[r.phase];$('phase-chip').dataset.phase=r.phase;
  $('progress-value').textContent=`${r.progress}%`;$('progress-bar').style.width=`${r.progress}%`;$('progress-text').textContent=PHASES[r.phase];$('step-count').textContent=`${r.steps}회`;
  $('link-status').textContent=['fault','repairing'].includes(r.phase)?'업링크 단절':r.phase==='awaiting'?'복구 / 확인 대기':'정상';$('link-status').dataset.bad=['fault','repairing'].includes(r.phase);
  $('gpu-online').textContent=`${totals(state.facility).gpu} / 192`;
  contextPanel();renderRequestActions();$('action-feedback').textContent=state.notice;
  const a=state.facility.assets.find(a=>a.id===state.facility.selectedId),v=readings(a);$('asset-panel').hidden=route!=='hall';
  $('asset-panel').innerHTML=`<div class="panel-label">ASSET INSPECTOR</div><h3>${a.name}</h3><div class="asset-chip" data-state="${a.state}">${STATES[a.state]}</div><p>${a.id===r.rackId?`관련 요청 ${r.id} / ${PHASES[r.phase]}`:'이 장비에는 이번 시연 요청이 배정되지 않았습니다.'}</p><div class="asset-readings"><div><span>GPU 부하</span><strong>${v.gpu}%</strong></div><div><span>소비 전력</span><strong>${v.power.toFixed(1)} kW</strong></div><div><span>유입 온도</span><strong>${v.temp.toFixed(1)} °C</strong></div><div><span>네트워크</span><strong>${v.network} Gbps</strong></div></div>`;
}
// Result summary is derived only from the recorded request history; nothing is scored or saved.
function resultCard(r){
  const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const card=el('section','result-box');card.id='demo-result';card.append(el('div','result-title','처리 결과 · 가상 시연'));
  const rows=el('dl','result-rows');
  for(const [k,v]of [['요청 / 고객',`${r.id} / ${r.customerId}`],['처리 위치',`${r.facilityId} / ${r.buildingId} / ${r.rackId}`],['원래 조건',`GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps · ${r.terms.mode} (변경 없음)`],['진행',`${r.progress}% · 시연 조작 ${r.steps}회`]]){rows.append(el('dt','',k),el('dd','',v));}
  card.append(rows,el('div','result-subtitle','처리 이력'));
  const list=el('ol','result-timeline');for(const h of r.history)list.append(el('li',`phase-${h.phase}`,`${PHASES[h.phase]} · ${h.progress}%`));card.append(list);
  card.append(el('p','result-note','점수·게임 시계·자원 원장과 연결되지 않은 가상 결과입니다.'));
  return card;
}
function renderRequestActions(){
  const state=store.state,route=state.navigation.route,step=nextDemoStep(state),root=$('request-actions');root.replaceChildren();
  if(!step){
    $('step-note').textContent='싱가포르 요청의 처리와 사후 확인을 마쳤습니다. 세계지도와 시설을 자유롭게 살펴보세요.';
    $('objective').textContent='싱가포르 요청 시연 완료';$('objective-detail').textContent='동일 요청·고객·랙의 처리 결과가 모든 공간에 유지됩니다.';
    const card=resultCard(state.request);root.append(card);
    if(route!=='world')root.append(button('세계지도에서 결과 보기',()=>navigate('world'),true,'result-world'));
    // Bring the result into view once per space; later re-renders keep the viewer's own scroll position.
    if(resultScrolledFor!==route){resultScrolledFor=route;requestAnimationFrame(()=>card.scrollIntoView({block:'nearest'}));}
    return;
  }
  $('step-note').textContent=step.note;$('objective').textContent=step.objective;$('objective-detail').textContent=step.note;
  if(route!==step.route){
    const next=step.route==='hall'&&route!=='campus'?'campus':step.route;
    const label=next==='world'?'세계지도에서 싱가포르 확인':next==='noc'?'관제실에서 계속':next==='campus'?'시설 지도로 요청 추적':'서버동 01 진입';
    root.append(button(label,()=>navigate(next),true,'continue-demo'));
  }else{
    if(route==='world'&&state.navigation.country!=='SG')root.append(button('싱가포르 고객 선택',()=>store.selectCountry('SG'),true,'select-sg'));
    if(route==='hall'&&state.facility.selectedId!==state.request.rackId)root.append(button('요청 랙 D-06 선택',()=>{store.selectRack(FIXTURE.rackId);scene.focus();},true,'select-request-rack'));
    const b=button(step.label,()=>store.act(step.id),true,'demo-action');b.dataset.action=step.id;b.disabled=!!demoBlocker(state,step.id);root.append(b);
  }
  if(['running','fault','repairing','awaiting','recovered'].includes(state.request.phase)&&route==='hall')root.append(button('관제실에서 같은 상태 확인',()=>navigate('noc'),false,'inspect-noc'));
}
store.subscribe(render);
try{
  scene=createScene($('viewport'),store.state.facility,id=>store.selectRack(id),{worldMode:true,getState:()=>store.state,onPick:id=>{const [type,key]=id.split(':');if(type==='country')store.selectCountry(key);if(type==='facility')store.selectFacility(key);}});
  const hash=location.hash.slice(1);if(hash&&!store.navigate(hash))history.replaceState(null,'','#world');render();$('loading').hidden=true;
  window.worldQA=Object.freeze({snapshot:()=>({state:store.snapshot(),domain:store.domainSnapshot(),renderer:scene.snapshot(),stats:{...stats},heap:performance.memory?{used:performance.memory.usedJSHeapSize,total:performance.memory.totalJSHeapSize}:null,visuals:scene.visuals(),worldMarkers:{SG:scene.worldMarker('SG'),JP:scene.worldMarker('JP')}}),projectAsset:id=>scene.projectAsset(id),projectWorld:id=>scene.projectWorld(id)});
  function animate(now){const dt=Math.min((now-lastTime)/1000,.1),raw=now-lastTime;lastTime=now;
    if(!document.hidden){visualSeconds+=dt;scene.pollGpuTimer();const timed=frame%30===0;if(timed)scene.beginGpuTimer();scene.animate(dt);if(timed)scene.endGpuTimer();const gpu=scene.pollGpuTimer();if(timed&&gpu!==null){gpuTimes.push(gpu);if(gpuTimes.length>60)gpuTimes.shift();}frameTimes.push(raw);if(frameTimes.length>300)frameTimes.shift();frame++;
      if(now-lastPerf>1000){const sorted=[...frameTimes].sort((a,b)=>a-b);stats={fps:1000/(frameTimes.reduce((s,x)=>s+x,0)/frameTimes.length),p95FrameMs:sorted[Math.floor(sorted.length*.95)],gpuMs:gpuTimes.length?gpuTimes.reduce((s,x)=>s+x,0)/gpuTimes.length:null};const s=scene.snapshot(),heap=performance.memory?performance.memory.usedJSHeapSize/1048576:null;$('performance').textContent=`${stats.fps.toFixed(0)} FPS / ${s.width}×${s.height} / HIGH`;$('perf-panel').textContent=`${s.quality}\n${s.renderer}\nFPS ${stats.fps.toFixed(1)} / p95 ${stats.p95FrameMs.toFixed(2)} ms / GPU ${stats.gpuMs?.toFixed(2)??'미측정'} ms\nJS heap ${heap?.toFixed(1)??'미측정'} MiB / calls ${s.calls} / triangles ${s.triangles}\nGeometries ${s.geometries} / textures ${s.textures}\nGPU 전체 점유·VRAM은 외부 NVIDIA-SMI 별도 계측\n시연 상태는 버튼 클릭으로만 변경됩니다.`;lastPerf=now;}
    }requestAnimationFrame(animate);
  }document.addEventListener('visibilitychange',()=>{lastTime=performance.now();});requestAnimationFrame(animate);
}catch(e){$('loading').hidden=true;$('fatal').hidden=false;$('fatal').textContent=`3D 초기화 실패: ${e.message}`;console.error(e);}
