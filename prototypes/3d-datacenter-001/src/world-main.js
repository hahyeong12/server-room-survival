import './world.css';
import {createScene} from './scene.js';
import {createWorldStore,LOCATIONS,COUNTRIES,FACILITIES,PHASES,ROOMS,breadcrumbs} from './world-store.js';
import {readings,totals,STATES} from './model.js';
import {COOLING,coolingView,powerView,upsView,networkView,hallView} from './facility-ops.js';
import {OPENING,OPENING_SECONDS,OPENING_STORAGE_KEY} from './opening.js';
import {GOALS,goalOf,nextAction,feedbackFor,misclickHint} from './guide.js';

document.querySelector('#app').innerHTML=`
<header class="topbar"><a class="brand" href="#noc"><span class="brand-icon">▤</span><span>SERVER ROOM<span class="brand-sub">SURVIVAL / ULSAN AIDC</span></span></a><div class="mode-badge">시연 모드 · 가상 요청 데이터</div><div class="top-right"><button id="tutorial-replay">튜토리얼 다시 하기</button><button id="opening-replay">오프닝 다시 보기</button><button id="help-open">플레이 안내</button></div></header>
<div class="routebar"><button id="back" aria-label="상위 공간으로 복귀">← 상위 공간</button><nav id="breadcrumbs" aria-label="현재 위치"></nav><span class="route-note">이동·카메라 조작은 작업을 진행하지 않습니다</span></div>
<main>
<section id="viewport" aria-label="3D 세계 탐색"><div class="scene-heading"><div id="scene-eyebrow" class="eyebrow"></div><h1 id="scene-title"></h1><p id="scene-description"></p></div>
<nav id="places" aria-label="공간 이동"><button data-route="world">세계지도</button><button data-route="campus">울산 캠퍼스</button><button data-route="noc">관제동 · 내 자리</button><button data-route="hall">서버동 01</button></nav>
<div id="map-legend"><span><i></i>울산 AIDC (남구 황성동·용연 권역)</span><span><i class="sg"></i>요청 경로 · 점등</span><span><i class="dim"></i>기타 국제망 · 어둡게</span><span class="legend-note">현실 기반 가상 경로입니다. 실제 케이블 좌표·소유가 아닙니다.</span><button id="motion-toggle" aria-pressed="false">움직임 줄이기</button></div>
<div id="route-chain" hidden></div>
<div id="noc-tools" hidden><button data-noc-view="desk">내 자리</button><button data-noc-view="overview">관제실 전체</button></div>
<div id="hall-tools" hidden><button data-camera="overview">서버동 전체</button><button data-camera="hall">랙 보기</button><button data-camera="aisle">통로</button><button id="focus-rack">선택 랙 보기</button><button id="ceiling-toggle" aria-pressed="false">천장 설비 보기</button><div class="layer-tools"><button data-layer="network" aria-pressed="true">네트워크</button><button data-layer="cooling" aria-pressed="true">냉각</button><button data-layer="power" aria-pressed="true">전력</button></div></div>
<section id="workstation" aria-label="내 모니터" hidden></section>
<div id="transit" hidden aria-live="polite"></div><div id="toast" hidden role="status" aria-live="polite"></div>
<div id="hover-label" hidden></div><div id="loading">3D 세계 준비 중…</div><div id="fatal" role="alert" hidden></div>
<div class="scene-caption"><b id="scene-code"></b><span id="scene-footnote"></span><span class="caption-line"></span><span>DESKTOP HIGH</span></div>
<div class="camera-help"><kbd>드래그</kbd> 회전 <kbd>우클릭</kbd> 이동 <kbd>휠</kbd> 확대 <kbd>W A S D</kbd> 이동 <kbd>F</kbd> 초점</div></section>
<aside id="panel" aria-label="현재 목표와 작업">
  <section class="goal-head"><div class="goal-top"><span id="goal-step"></span><span id="goal-pips" aria-hidden="true"></span></div><h2 id="goal-title"></h2><p id="goal-hint"></p></section>
  <section id="panel-body">
    <div class="req-summary"><div class="req-row"><span class="flag">SG</span><strong data-request-id></strong><span id="phase-chip" class="chip"></span></div>
      <div class="req-terms" id="req-terms"></div><div class="progress-track"><i id="progress-bar"></i></div>
      <div class="status-chips"><span>업링크 <b id="link-status"></b></span><span>보조 냉각 <b id="cooling-status"></b></span><span>GPU <b id="gpu-online"></b></span></div></div>
    <div id="context-card"></div>
    <details id="detail"><summary>자세히 보기 · 원래 조건 · 처리 위치 · 이력</summary><div id="detail-body"></div></details>
  </section>
  <section class="panel-action"><div id="action-feedback" role="status" aria-live="polite"></div><button id="primary-action" class="primary big"></button><div id="secondary-actions"></div></section>
</aside>
<section class="mission-strip"><div class="mission-title"><span class="eyebrow">MY SHIFT · 첫 업무</span><strong id="objective"></strong></div><ol id="stepper"></ol><div class="mission-id"><strong data-request-id></strong><span>가상 고객 요청 1건</span></div></section>
</main><footer><span><b>WORLD / PHASE 3.2</b> · 기존 엔진 미연결</span><span id="performance">성능 측정 중…</span><button id="perf-toggle" aria-expanded="false">성능 상세</button><a href="./lab.html">기존 3D 실험실</a></footer><div id="perf-panel" hidden></div>
<div id="coach" hidden role="dialog" aria-label="튜토리얼"><span id="coach-step"></span><p id="coach-text"></p><div class="coach-row"><button id="coach-skip">튜토리얼 건너뛰기</button></div></div>
<div id="opening" hidden><div id="opening-fade"></div><div class="opening-top"><span class="mode-badge">시연 모드 · 가상 데이터</span><button id="opening-skip">건너뛰기 · Esc</button></div><div class="opening-caption"><span id="opening-step"></span><h2 id="opening-title"></h2><p id="opening-sub"></p><div class="opening-progress"><i id="opening-bar"></i></div></div></div>
<dialog id="result-dialog"><div id="result-slot"></div><button id="result-close" class="primary">닫고 둘러보기</button></dialog>
<dialog id="help"><button id="help-close" aria-label="안내 닫기">닫기</button><span class="eyebrow">시연 플레이 안내</span><h2>오른쪽 아래 큰 버튼 하나만 따라가면 첫 업무가 끝납니다.</h2><ol><li>위쪽의 <b>목표 n/5</b>가 지금 할 일입니다. 아래 큰 버튼이 다음 행동입니다.</li><li>세계지도에서 요청 국가와 경로를 보고, 내 자리에서 접수합니다.</li><li>서버동 01에서 금색 표시가 붙은 랙 D-06을 찾아 작업합니다.</li><li>장애가 나면 복구 → 사후 확인 → 완료 → 내 자리에서 결과 확인.</li><li>캠퍼스 건물: 한 번 클릭 = 정보와 작업, 두 번 클릭(또는 Enter) = 내부로 들어가기.</li></ol><p>모든 진행은 버튼 클릭으로만 일어납니다. 새로고침하면 시연만 처음으로 돌아갑니다. 보조 냉각·전력·UPS·네트워크 조작은 교육용 시연이며 실제 운영 절차가 아닙니다.</p><p>3D 화면: 드래그 회전 · 우클릭 이동 · 휠 확대 · W/A/S/D 이동 · F 초점. 카메라 충돌 판정은 없습니다.</p></dialog>`;

const $=id=>document.getElementById(id),store=createWorldStore();
const TUTORIAL_KEY='srs3d.tutorial.done.v1';
let scene,lastViewKey=null,frame=0,lastTime=performance.now(),lastPerf=0,perfOpen=false,reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
let openingActive=false,openingStart=0,openingResult=null,openingLocation=null,transitTimer=0,toastTimer=0,resultShown=false;
let tutorial={active:false,misclicks:0,hints:[]};
const frameTimes=[],gpuTimes=[];let stats={fps:0,p95FrameMs:0,gpuMs:null};
const descriptions={world:'한국을 중심으로 본 고객과 가상 국제망.',campus:'건물을 한 번 누르면 정보, 두 번 누르면 내부로 들어갑니다.',noc:'요청을 받고, 시설을 지켜보고, 결과를 확인하는 내 자리.',hall:'요청 랙을 직접 찾아 작업하는 현장.',room:'시설의 실제 기능을 보는 작은 작업 공간.'};
const notes={world:'Natural Earth 육지 + 직접 만든 가상 망 / 실제 케이블 데이터 아님',noc:'기존 관제실 재사용 / 내 자리·모니터는 동일 상태',campus:'자체 제작 캠퍼스·산단 재구성 / 실제 부지·조감도 아님',hall:'기존 24랙 재사용 / 천장 설비는 기본 숨김',room:'교육용 시설 내부 모식 / 실제 설비 설계 아님'};
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
function button(text,handler,primary=false,id){const b=el('button',primary?'primary':'',text);if(id)b.id=id;b.addEventListener('click',handler);return b;}
function routeTitle(route){return route==='room'?`${FACILITIES[store.state.navigation.room].name} 내부`:LOCATIONS[route].title;}
function navigate(route){
  const from=store.state.navigation.route;
  if(store.navigate(route)){if(location.hash!==`#${route}`)history.replaceState(null,'',`#${route}`);if((from==='noc'&&route==='hall')||(from==='hall'&&route==='noc'))showTransit(from,route);}
}
function enterFacility(id){if(store.enterFacility(id)){const r=store.state.navigation.route;if(location.hash!==`#${r}`)history.replaceState(null,'',`#${r}`);}}
function showTransit(from,to){
  const t=$('transit');t.replaceChildren();const path=el('div','transit-path');
  for(const [k,label]of [[from,from==='noc'?'관제동':'서버동 01'],['link','연결 통로'],[to,to==='noc'?'관제동 · 내 자리':'서버동 01']])path.append(el('span',k==='link'?'link':'',label));
  t.append(el('span','eyebrow','이동 · 별도 건물'),path,el('p','',to==='hall'?'현장: 랙을 직접 찾아 작업합니다.':'운영: 내 모니터에서 요청과 시설을 관리합니다.'));
  t.hidden=false;clearTimeout(transitTimer);transitTimer=setTimeout(()=>{t.hidden=true;},1400);
}
function toast(text,tone='ok'){if(!text)return;const t=$('toast');t.textContent=text;t.dataset.tone=tone;t.hidden=false;t.classList.remove('pop');void t.offsetWidth;t.classList.add('pop');clearTimeout(toastTimer);toastTimer=setTimeout(()=>{t.hidden=true;},2800);}
function hint(text){if(!text)return;toast(text,'hint');if(tutorial.active){tutorial.misclicks++;tutorial.hints.push(text);}}

document.querySelectorAll('[data-route]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.route==='noc')store.setNocView('desk');navigate(b.dataset.route);}));
document.querySelectorAll('[data-noc-view]').forEach(b=>b.addEventListener('click',()=>store.setNocView(b.dataset.nocView)));
$('back').addEventListener('click',()=>{const p=LOCATIONS[store.state.navigation.route].parent;if(p)navigate(p);});
window.addEventListener('hashchange',()=>{const route=location.hash.slice(1);if(!store.navigate(route)){history.replaceState(null,'','#noc');store.navigate('noc');}});
$('help-open').addEventListener('click',()=>$('help').showModal());$('help-close').addEventListener('click',()=>$('help').close());
$('result-close').addEventListener('click',()=>$('result-dialog').close());
$('perf-toggle').addEventListener('click',()=>{perfOpen=!perfOpen;$('perf-panel').hidden=!perfOpen;$('perf-toggle').setAttribute('aria-expanded',String(perfOpen));});
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>scene.view(b.dataset.camera)));
$('focus-rack').addEventListener('click',()=>scene.focus());
$('ceiling-toggle').addEventListener('click',e=>{const on=e.currentTarget.getAttribute('aria-pressed')!=='true';e.currentTarget.setAttribute('aria-pressed',String(on));e.currentTarget.textContent=on?'천장 설비 숨기기':'천장 설비 보기';scene.setCeiling?.(on);});
$('motion-toggle').addEventListener('click',e=>{reducedMotion=!reducedMotion;e.currentTarget.setAttribute('aria-pressed',String(reducedMotion));});
document.querySelectorAll('[data-layer]').forEach(b=>b.addEventListener('click',()=>{const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));scene.setLayer(b.dataset.layer,on);}));
$('opening-skip').addEventListener('click',()=>finishOpening('skipped'));$('opening-replay').addEventListener('click',()=>startOpening());
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&openingActive){e.preventDefault();finishOpening('skipped');return;}
  // Keyboard alternative to double-click: Enter on the 3D view enters the selected building.
  if(e.key==='Enter'&&!openingActive&&store.state.navigation.route==='campus'&&document.activeElement===scene?.renderer.domElement){e.preventDefault();enterFacility(store.state.navigation.facility);}
});

// ---------- shared widgets (all read the single store) ----------
function coolingBadge(v,compact=false){
  const b=el('div',`cool-badge${compact?' compact':''}`);b.dataset.mode=v.mode;b.setAttribute('role','status');
  const leds=el('span','cool-leds');for(let i=0;i<3;i++)leds.append(el('i'));
  const text=el('span','cool-text');text.append(el('strong','cool-label',`보조 냉각 ${v.label}`));if(!compact)text.append(el('small','',v.summary));
  b.append(el('span','cool-icon',v.icon),leds,text);return b;
}
function sparkline(values){
  const min=Math.min(...values)-.2,max=Math.max(...values)+.2,w=280,h=48;
  const pts=values.map((y,i)=>`${(i/(values.length-1)*w).toFixed(1)},${(h-(y-min)/(max-min)*h).toFixed(1)}`).join(' ');
  const wrap=el('div','spark');wrap.innerHTML=`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
  wrap.append(el('span','',`서버동 유입 온도 ${values[0].toFixed(1)} → ${values.at(-1).toFixed(1)} °C · 조작 기준`));return wrap;
}
function readingsGrid(rows){const g=el('dl','ops-readings');for(const [k,v]of rows)g.append(el('dt','',k),el('dd','',v));return g;}
function checkResult(c){if(!c)return null;const box=el('div','ops-result');box.append(el('strong','',c.title),el('p','',c.detail),el('small','',`조회 시점: ${PHASES[c.phase]} · 기록 #${c.seq}`));return box;}
function opsButton(action,label,primary=false){const b=button(label,()=>{const r=store.ops(action);if(r.ok)toast(OPS_FEEDBACK[action]);else toast(r.reason,'hint');},primary);b.dataset.ops=action;return b;}
const COOLING_LABELS={'cooling-off':'보조 냉각 끄기','cooling-on':'보조 냉각 켜기','cooling-warn':'경고 시나리오 · 유량 저하','cooling-reset':'유량 점검 완료 · 재가동'};
const OPS_FEEDBACK={'cooling-off':'보조 냉각 꺼짐 · 팬 정지, 냉각수 흐름 중단','cooling-on':'보조 냉각 켜짐 · 팬 회전, 냉각수 순환','cooling-warn':'경고 · 냉각수 유량이 12 L/min으로 떨어졌습니다','cooling-reset':'점검 완료 · 보조 냉각이 정상 재가동됐습니다','power-check':'전력 계통 점검 완료','ups-test':'UPS 자가진단 정상','network-lookup':'장애 원인 조회 완료'};
const FACILITY_ROLE={NOC:'운영 건물 · 내 자리와 업무 모니터','HALL-01':'현장 건물 · 24랙 서버실',POWER:'A/B 이중 수전과 배전',UPS:'정전 순간을 버티는 예비 전원',COOLING:'교육용 보조 냉각 계통 AUX-C1',NETWORK:'국제 가상 회선과 서버동 업링크'};

// Facility card: what it is / current status / what you can do here. full=true inside the building.
function facilityCard(id,state,full=false){
  const root=el('div','facility-card');root.dataset.panel=id;const f=FACILITIES[id];
  const head=el('div','fc-head');head.append(el('strong','',f.name),el('span','',FACILITY_ROLE[id]));root.append(head);
  const actions=el('div','ops-actions');
  if(id==='COOLING'){
    const v=coolingView(state);root.append(coolingBadge(v,!full));
    for(const a of v.actions)actions.append(opsButton(a,COOLING_LABELS[a],a==='cooling-on'||a==='cooling-reset'));root.append(actions);
    root.append(readingsGrid(full?[['냉각수 유량',`${v.flow} L/min`],['공급 / 환수',`${v.supply??'—'} / ${v.ret??'—'} °C`],['팬 속도',`${v.fan}%`],['서버동 평균 유입',`${v.hallInlet} °C`],['보조 냉각 전력',`${v.loadKW} kW`]]:[['냉각수 유량',`${v.flow} L/min`],['서버동 평균 유입',`${v.hallInlet} °C`]]));
    if(full)root.append(sparkline(v.trend));
    if(v.mode==='warn')root.append(checkResult({title:'진단: 냉각수 유량 저하',detail:`유량 ${v.flow} L/min (정상 ${COOLING.on.flow}) · 조치: 유량 점검 후 재가동`,phase:state.request.phase,seq:state.ops.log.length}));
  }else if(id==='POWER'){
    const p=powerView(state);root.append(readingsGrid([['수전',p.feeds],['부하 합계',`${p.totalKW} / ${p.capacityKW} kW`],...(full?[['IT 부하',`${p.itLoadKW} kW`],['보조 냉각',`${p.coolingLoadKW} kW`]]:[])]));
    actions.append(opsButton('power-check','전력 계통 점검'));root.append(actions);const r=checkResult(state.ops.checks.power);if(r)root.append(r);
  }else if(id==='UPS'){
    const u=upsView(state);root.append(readingsGrid([['배터리',`${u.battery}%`],['상태',u.mode],...(full?[['예비 시간',u.runtime]]:[])]));
    actions.append(opsButton('ups-test','UPS 자가진단'));root.append(actions);const r=checkResult(state.ops.checks.ups);if(r)root.append(r);
  }else if(id==='NETWORK'){
    const n=networkView(state);root.append(readingsGrid([['서버동 01 업링크',n.uplink],['싱가포르 회선',n.links.find(l=>l.id==='SG').status]]));
    if(full){const table=el('div','link-table');for(const l of n.links){const row=el('div',`link-row${l.status==='정상'?'':' bad'}`);row.dataset.link=l.id;row.append(el('span','',`${l.name}${l.active?' · 요청 중':''}`),el('span','',`${l.latencyMs} ms (가상)`),el('span','',l.status));table.append(row);}root.append(table);}
    actions.append(opsButton('network-lookup','장애 원인 조회'));root.append(actions);
    const c=state.ops.checks.network,r=checkResult(c);if(r){root.append(r);if(c.target==='hall'){const go=button('서버동 01로 이동',()=>navigate('hall'),false,'network-to-hall');root.append(go);}}
  }else if(id==='HALL-01'){
    const h=hallView(state);root.append(readingsGrid([['가상 GPU 온라인',`${h.gpuOnline} / 192`],['요청 랙',`${h.requestRack} · ${STATES[h.requestRackState]}`],['활성 장애',`${h.faults}건`]]));
  }else if(id==='NOC'){
    root.append(readingsGrid([['운영석','6석 · 근무 5명 (가상)'],['내 요청함',`SG · 1건 · ${PHASES[state.request.phase]}`]]));
  }
  return root;
}

function contextCard(){
  const state=store.state,nav=state.navigation,route=nav.route,root=$('context-card');root.replaceChildren();
  if(route==='world'){
    const chips=el('div','chip-row');for(const [id,c]of Object.entries(COUNTRIES)){const b=button(id,()=>{store.selectCountry(id);hint(misclickHint(store.state,'country',id));},id===nav.country);b.dataset.country=id;b.setAttribute('aria-label',`${c.name} 선택`);chips.append(b);}root.append(chips);
    const n=networkView(state);root.append(el('p','card-line',nav.country==='SG'?`싱가포르 → 부산 권역 육양국 → 국내망 → 울산 AIDC · ${n.down?'국제 구간 정상, AIDC 내부 업링크 장애':'경로 정상'}`:nav.country==='KR'?'울산 남구 황성동·용연 권역의 미래 가상 AIDC입니다.':'이 나라에는 지금 요청이 없습니다.'));
  }else if(route==='campus'){
    const chips=el('div','chip-row facilities');for(const [id,f]of Object.entries(FACILITIES)){const b=button(f.name,()=>store.selectFacility(id),id===nav.facility);b.dataset.facility=id;chips.append(b);}root.append(chips);
    root.append(facilityCard(nav.facility,state));
    const enter=button(nav.facility==='NOC'?'내 자리로 들어가기':nav.facility==='HALL-01'?'서버동 01로 들어가기':'내부로 들어가기',()=>enterFacility(nav.facility),false,'enter-building');enter.title='건물을 두 번 클릭하거나 3D 화면에서 Enter';root.append(enter,el('p','card-tip','팁: 건물을 두 번 클릭(또는 Enter)하면 내부로 들어갑니다.'));
  }else if(route==='noc'){
    root.append(el('p','card-line','내 모니터에 요청·조건·시설 상태가 있습니다. 진행은 아래 큰 버튼으로 합니다.'));
    const t=el('div','chip-row');t.append(button('내 자리',()=>store.setNocView('desk'),nav.nocView==='desk'),button('관제실 전체',()=>store.setNocView('overview'),nav.nocView==='overview'));t.children[0].dataset.nocView='desk';t.children[1].dataset.nocView='overview';root.append(t);
  }else if(route==='hall'){
    const a=state.facility.assets.find(a=>a.id===state.facility.selectedId),v=readings(a),delta=COOLING[state.ops.cooling.mode].inletDelta,isTarget=a.id===state.request.rackId;
    const head=el('div','fc-head');head.append(el('strong','',a.name),el('span',`asset-chip`,STATES[a.state]));head.lastChild.dataset.state=a.state;root.append(head);
    root.append(el('p','card-line',isTarget?`요청 랙 · ${state.request.id} · ${PHASES[state.request.phase]}`:'이 장비에는 이번 요청이 없습니다.'));
    root.append(readingsGrid([['GPU 부하 / 전력',`${v.gpu}% · ${v.power.toFixed(1)} kW`],['유입 온도 / 네트워크',`${(v.temp+delta).toFixed(1)} °C · ${v.network} Gbps`]]));
    const label=el('label','select-line','장비'),select=el('select');select.id='equipment-select';select.setAttribute('aria-label','장비 선택');
    for(const x of state.facility.assets){const o=el('option','',x.id===state.request.rackId?`${x.name} · 요청 랙`:x.name);o.value=x.id;select.append(o);}select.value=state.facility.selectedId;select.addEventListener('change',()=>{store.selectRack(select.value);hint(misclickHint(store.state,'rack',select.value));});label.append(select);root.append(label);
  }else if(route==='room'){
    root.append(facilityCard(nav.room,state,true));
  }
}
function detailBody(){
  const r=store.state.request,root=$('detail-body');root.replaceChildren();
  root.append(readingsGrid([['요청 / 고객',`${r.id} / ${r.customerId}`],['작업',r.workload],['원래 조건',`GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps`],['모드 / 기한',`${r.terms.mode} · ${r.terms.deadline}`],['처리 위치',`${r.facilityId} / ${r.buildingId} / ${r.rackId}`]]));
  if(r.history.length){const list=el('ol','result-timeline');for(const h of r.history)list.append(el('li',`phase-${h.phase}`,`${PHASES[h.phase]} · ${h.progress}%`));root.append(list);}
  root.append(el('p','ops-note','가상 요청을 쓰는 독립 시연입니다. Python 게임·SQLite와 연결되지 않았고 점수·게임 시계·자원 원장을 바꾸지 않습니다.'));
}

// ---------- the single primary action ----------
function runAction(a){
  if(a.kind==='navigate'){if(a.target==='noc')store.setNocView('desk');navigate(a.target);}
  else if(a.kind==='select-country'){store.selectCountry(a.target);}
  else if(a.kind==='select-rack'){store.selectRack(a.target);scene.focus();toast(`랙 ${a.target}을 선택했습니다 · 금색 표시를 확인하세요`);}
  else if(a.kind==='act'){const r=store.act(a.id);if(r.ok){toast(feedbackFor(a.id));if(a.id==='report')showResult();}else toast(r.reason,'hint');}
  else if(a.kind==='done'){store.setNocView('desk');navigate('noc');showResult();}
}
function renderAction(){
  const state=store.state,a=nextAction(state),g=goalOf(state.request.phase);
  $('goal-step').textContent=g.done?'첫 업무 완료':`목표 ${g.index}/${g.total}`;$('goal-title').textContent=g.title;$('goal-hint').textContent=a.hint;
  $('goal-pips').replaceChildren(...GOALS.map((x,i)=>{const p=el('i');p.className=i+1<g.index||g.done?'done':i+1===g.index?'now':'';return p;}));
  const b=$('primary-action');b.textContent=a.label;b.disabled=!!a.disabled;b.dataset.kind=a.kind;if(a.kind==='act')b.dataset.action=a.id;else delete b.dataset.action;b.dataset.target=a.target??'';
  b.onclick=()=>runAction(nextAction(store.state));
  const sec=$('secondary-actions');sec.replaceChildren();
  if(a.alt){const s=button(a.alt.label,()=>runAction(a.alt));s.dataset.action=a.alt.id;s.className='link';sec.append(s);}
  if(['fault','repairing'].includes(state.request.phase)&&state.navigation.route!=='campus'){const s=button('원인 보기 · 네트워크동',()=>{store.selectFacility('NETWORK');navigate('campus');});s.className='link';s.id='go-network';sec.append(s);}
  $('action-feedback').textContent=state.notice;
  // Mission stepper mirrors the five goals.
  $('objective').textContent=g.done?'첫 업무 완료 · 자유롭게 둘러보세요':`${g.index}/${g.total} ${g.title}`;
  $('stepper').replaceChildren(...GOALS.map((x,i)=>{const li=el('li',i+1<g.index||g.done?'done':i+1===g.index?'now':'',x.title);return li;}));
}
function showResult(){const slot=$('result-slot');slot.replaceChildren(resultCard(store.state.request));if(!$('result-dialog').open)$('result-dialog').showModal();resultShown=true;}

// ---------- My monitor (desk view): the request and the facility at a glance ----------
function renderWorkstation(){
  const state=store.state,r=state.request,a=nextAction(state),g=goalOf(r.phase),ws=$('workstation');
  ws.hidden=!(state.navigation.route==='noc'&&state.navigation.nocView==='desk')||openingActive;if(ws.hidden)return;ws.replaceChildren();
  const bar=el('div','ws-titlebar');bar.append(el('span','','SRS-OPS · 운영석 03 · 내 모니터'),el('span','ws-shift','근무 중 · 주간 A조 (가상)'));
  const body=el('div','ws-body');
  const me=el('section','ws-me');me.append(el('div','ws-label',g.done?'오늘의 업무':`지금 할 일 · 목표 ${g.index}/${g.total}`));
  const todo=el('strong','ws-todo',g.title);todo.id='ws-todo';me.append(todo,el('p','ws-note',a.hint),el('p','ws-pointer',`→ 오른쪽 아래 [${a.label}]`));
  const inbox=el('section','ws-inbox');inbox.append(el('div','ws-label','고객 요청함 · 1건'));
  const row=el('div','ws-request');row.dataset.phase=r.phase;row.append(el('strong','',r.id),el('span','',`${r.customerName}`),el('span','chip',PHASES[r.phase]));row.lastChild.dataset.phase=r.phase;inbox.append(row);
  inbox.append(readingsGrid([['원래 조건',`GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps`],['배정 검토',`서버동 01 · 랙 ${r.rackId} · 여유 있음 ✓`],['진행',`${r.progress}%`]]));
  const watch=el('section','ws-watch');watch.append(el('div','ws-label','시설 감시 · 누르면 캠퍼스에서 보기'));
  const h=hallView(state),n=networkView(state),p=powerView(state),c=coolingView(state);
  const tile=(id,title,value,bad)=>{const t=button('',()=>{store.selectFacility(id);navigate('campus');});t.className=`ws-tile${bad?' bad':''}`;t.dataset.wsTile=id;t.append(el('span','',title),el('strong','',value));return t;};
  watch.append(tile('HALL-01','서버동 01',`GPU ${h.gpuOnline}/192 · 장애 ${h.faults}`,h.faults>0),tile('NETWORK','네트워크 업링크',n.uplink,n.down));
  const coolTile=tile('COOLING','','',c.mode==='warn');coolTile.replaceChildren(coolingBadge(c,true));watch.append(coolTile,tile('POWER','전력 · UPS',`${p.totalKW} kW · UPS 대기`,false));
  body.append(me,inbox,watch);ws.append(bar,body);
}

function render(){
  const state=store.state,nav=state.navigation,route=nav.route,r=state.request,viewKey=`${route}:${nav.nocView}:${nav.room}`;
  if(scene&&!openingActive&&lastViewKey!==viewKey){scene.setLocation(route,lastViewKey===null,nav.nocView,nav.room);lastViewKey=viewKey;}
  $('scene-eyebrow').textContent=LOCATIONS[route].subtitle;$('scene-title').textContent=routeTitle(route);$('scene-description').textContent=descriptions[route];
  $('scene-code').textContent=({world:'GLOBAL / KR-CENTRED',noc:'NOC / 01',campus:'ULSAN / 01',hall:'HALL / 01',room:`ROOM / ${nav.room}`})[route];$('scene-footnote').textContent=notes[route];
  $('hall-tools').hidden=route!=='hall';$('noc-tools').hidden=route!=='noc';$('map-legend').hidden=route!=='world';$('back').disabled=route==='world';
  document.querySelectorAll('#noc-tools [data-noc-view]').forEach(b=>b.classList.toggle('active',b.dataset.nocView===nav.nocView));
  $('breadcrumbs').replaceChildren(...breadcrumbs(route).map(x=>{const b=button(x.id==='room'?routeTitle('room'):x.title,()=>navigate(x.id));b.dataset.crumb=x.id;if(x.id===route)b.setAttribute('aria-current','location');return b;}));
  document.querySelectorAll('#places [data-route]').forEach(b=>b.classList.toggle('active',b.dataset.route===route||(route==='room'&&b.dataset.route==='campus')));
  document.querySelectorAll('[data-request-id]').forEach(x=>x.textContent=r.id);
  $('req-terms').textContent=`${r.customerName} · GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps · ${r.terms.mode}`;
  $('phase-chip').textContent=`${PHASES[r.phase]} · ${r.progress}%`;$('phase-chip').dataset.phase=r.phase;$('progress-bar').style.width=`${r.progress}%`;
  const n=networkView(state);$('link-status').textContent=n.down?'단절':r.phase==='awaiting'?'확인 대기':'정상';$('link-status').dataset.bad=n.down;
  const cv=coolingView(state);$('cooling-status').textContent=`${cv.icon} ${cv.label}`;$('cooling-status').dataset.mode=cv.mode;
  $('gpu-online').textContent=`${totals(state.facility).gpu}/192`;
  renderRouteChain(state);contextCard();detailBody();renderAction();renderWorkstation();renderCoach();
}
function renderRouteChain(state){
  const box=$('route-chain');box.hidden=state.navigation.route!=='world';if(box.hidden)return;box.replaceChildren(el('span','eyebrow','싱가포르 요청 경로 · 가상'));
  const p=state.request.phase,active=!['new'].includes(p)||state.navigation.country==='SG',down=['fault','repairing'].includes(p),chain=el('div','chain');
  for(const [k,label,bad]of [['sea','해저 구간',false],['land','부산 권역 육양국',false],['backbone','국내 지상망',false],['aidc','울산 AIDC · 서버동 업링크',down]]){const s=el('span',`hop${bad?' bad':''}${active?' on':''}`,`${bad?'⚠ ':''}${label}`);s.dataset.hop=k;chain.append(s);}
  box.append(chain,el('small','',down?'국제 구간은 정상입니다. 문제는 AIDC 내부 랙 D-06의 업링크입니다.':'해저 케이블은 해안 육양국에서 국내망으로 이어집니다. 건물에 직접 닿지 않습니다.'));
}
// Result summary is derived only from the recorded request history; nothing is scored or saved.
function resultCard(r,id='demo-result'){
  const card=el('section','result-box');card.id=id;card.append(el('div','result-title','첫 업무 완료 · 처리 결과 (가상 시연)'));
  const cause=el('ol','result-cause');for(const t of ['싱가포르 요청이 가상 국제망 → 부산 육양국 → 울산 AIDC로 도착','내 자리에서 조건 확인 후 서버동 01 · 랙 D-06에 배정','D-06 업링크 장애 → 복구 → 사후 확인으로 정상 재개','작업 100% 완료, 고객 결과 확인'])cause.append(el('li','',t));card.append(cause);
  const rows=el('dl','result-rows');
  for(const [k,v]of [['요청 / 고객',`${r.id} / ${r.customerId}`],['처리 위치',`${r.facilityId} / ${r.buildingId} / ${r.rackId}`],['원래 조건',`GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps · ${r.terms.mode} (변경 없음)`],['진행',`${r.progress}% · 시연 조작 ${r.steps}회`]]){rows.append(el('dt','',k),el('dd','',v));}
  card.append(rows);const list=el('ol','result-timeline');for(const h of r.history)list.append(el('li',`phase-${h.phase}`,`${PHASES[h.phase]} · ${h.progress}%`));card.append(list);
  card.append(el('p','result-note','점수·게임 시계·자원 원장과 연결되지 않은 가상 결과입니다.'));
  return card;
}
function renderCoach(){}

// ---------- Opening (skippable, once per browser unless replayed) ----------
function openingSeen(){try{return localStorage.getItem(OPENING_STORAGE_KEY)==='1';}catch{return false;}}
function startOpening(){
  if(openingActive||!scene)return;
  openingActive=true;openingStart=performance.now();openingLocation=null;document.body.classList.add('cinematic');$('opening').hidden=false;$('workstation').hidden=true;$('coach').hidden=true;
  scene.playCinematic(OPENING,{onSegment:(i,k)=>{
    $('opening-step').textContent=`${String(i+1).padStart(2,'0')} / ${String(OPENING.length).padStart(2,'0')}`;$('opening-title').textContent=k.title;$('opening-sub').textContent=k.sub;
    if(openingLocation!==null&&openingLocation!==k.location){const f=$('opening-fade');f.classList.remove('cut');void f.offsetWidth;f.classList.add('cut');}openingLocation=k.location;
  },onDone:()=>finishOpening('completed')});
}
function finishOpening(how){
  if(!openingActive)return;scene.stopCinematic();openingActive=false;openingResult={how,seconds:+((performance.now()-openingStart)/1000).toFixed(2)};
  try{localStorage.setItem(OPENING_STORAGE_KEY,'1');}catch{/* private mode: replay simply stays available */}
  document.body.classList.remove('cinematic');$('opening').hidden=true;store.setNocView('desk');lastViewKey=null;navigate('noc');render();
}
function openingProgress(){const c=scene.cinematicState();if(!c)return 0;return (OPENING.slice(0,c.index).reduce((s,k)=>s+k.duration,0)+c.t)/OPENING_SECONDS;}

store.subscribe(render);
try{
  scene=createScene($('viewport'),store.state.facility,id=>{store.selectRack(id);hint(misclickHint(store.state,'rack',id));},{worldMode:true,getState:()=>store.state,reducedMotion:()=>reducedMotion,
    onPick:id=>{const [type,key]=id.split(':');if(type==='country'){store.selectCountry(key);hint(misclickHint(store.state,'country',key));}if(type==='facility')store.selectFacility(key);},
    onEnter:id=>{const [type,key]=id.split(':');if(type==='facility')enterFacility(key);}});
  const hash=location.hash.slice(1);if(hash&&!store.navigate(hash))history.replaceState(null,'','#noc');render();$('loading').hidden=true;
  if(!openingSeen())startOpening();
  window.worldQA=Object.freeze({snapshot:()=>({state:store.snapshot(),domain:store.domainSnapshot(),renderer:scene.snapshot(),stats:{...stats},heap:performance.memory?{used:performance.memory.usedJSHeapSize,total:performance.memory.totalJSHeapSize}:null,visuals:scene.visuals(),worldMarkers:{SG:scene.worldMarker('SG'),JP:scene.worldMarker('JP')},cooling:scene.coolingVisual(),deskScreen:scene.deskScreenKey(),network:scene.networkVisual?.()??null,interior:scene.interiorVisual?.()??null,opening:{active:openingActive,state:scene.cinematicState(),result:openingResult,seconds:OPENING_SECONDS},guide:{action:nextAction(store.state),goal:goalOf(store.state.request.phase)},tutorial:{...tutorial,hints:[...tutorial.hints]}}),projectAsset:id=>scene.projectAsset(id),projectWorld:id=>scene.projectWorld(id),projectPoint:p=>scene.projectPoint?.(p)??null});
  function animate(now){const dt=Math.min((now-lastTime)/1000,.1),raw=now-lastTime;lastTime=now;
    if(!document.hidden){scene.pollGpuTimer();const timed=frame%30===0;if(timed)scene.beginGpuTimer();scene.animate(dt);if(timed)scene.endGpuTimer();const gpu=scene.pollGpuTimer();if(timed&&gpu!==null){gpuTimes.push(gpu);if(gpuTimes.length>60)gpuTimes.shift();}frameTimes.push(raw);if(frameTimes.length>300)frameTimes.shift();frame++;
      if(openingActive)$('opening-bar').style.width=`${(openingProgress()*100).toFixed(1)}%`;
      if(now-lastPerf>1000){const sorted=[...frameTimes].sort((a,b)=>a-b);stats={fps:1000/(frameTimes.reduce((s,x)=>s+x,0)/frameTimes.length),p95FrameMs:sorted[Math.floor(sorted.length*.95)],gpuMs:gpuTimes.length?gpuTimes.reduce((s,x)=>s+x,0)/gpuTimes.length:null};const s=scene.snapshot(),heap=performance.memory?performance.memory.usedJSHeapSize/1048576:null;$('performance').textContent=`${stats.fps.toFixed(0)} FPS / ${s.width}×${s.height} / HIGH`;$('perf-panel').textContent=`${s.quality}\n${s.renderer}\nFPS ${stats.fps.toFixed(1)} / p95 ${stats.p95FrameMs.toFixed(2)} ms / GPU ${stats.gpuMs?.toFixed(2)??'미측정'} ms\nJS heap ${heap?.toFixed(1)??'미측정'} MiB / calls ${s.calls} / triangles ${s.triangles}\nGeometries ${s.geometries} / textures ${s.textures}\nGPU 전체 점유·VRAM은 외부 NVIDIA-SMI 별도 계측\n시연 상태는 버튼 클릭으로만 변경됩니다.`;lastPerf=now;}
    }requestAnimationFrame(animate);
  }document.addEventListener('visibilitychange',()=>{lastTime=performance.now();});requestAnimationFrame(animate);
}catch(e){$('loading').hidden=true;$('fatal').hidden=false;$('fatal').textContent=`3D 초기화 실패: ${e.message}`;console.error(e);}
