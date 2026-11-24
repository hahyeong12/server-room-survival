import './world.css';
import './game.css';
import {createScene} from './scene.js';
import {createWorldStore,LOCATIONS,COUNTRIES,FACILITIES,breadcrumbs} from './world-store.js';
import {readings,STATES} from './model.js';
import {COOLING,coolingView,powerView,upsView,networkView,hallView} from './facility-ops.js';
import {OPENING,OPENING_SECONDS,OPENING_STORAGE_KEY} from './opening.js';
import {createEngineClient} from './api.js';
import {focusRequest,requestById,isOpen,STAGE_LABEL,MODE_NAMES,COUNTRY_NAMES,serverOfRack,termsLine,allowedLine,engineTotals,storyGoal,freeGoal,planRacks} from './game-view.js';
import {focusPath,activePaths} from './network-data.js';
import {createCoach} from './coach.js';
import {createScreens} from './screens.js';

document.querySelector('#app').innerHTML=`
<header class="topbar"><a class="brand" href="#noc"><span class="brand-icon">▤</span><span>SERVER ROOM<span class="brand-sub">SURVIVAL / ULSAN AIDC</span></span></a>
<div class="mode-badge" id="mode-badge">게임 선택 전</div>
<div id="clock" aria-label="가상 시각과 시간 진행"><span class="clock-label">가상 시각</span><strong id="clock-time">—</strong><span class="time-btns"><button data-advance="10" title="가상 시간 10분 진행">⏩ +10분</button><button data-advance="30">+30분</button><button data-advance="60">+60분</button></span></div>
<div class="top-right"><button id="menu-open">메뉴 · 모드</button><button id="opening-replay">오프닝 다시 보기</button><button id="help-open">플레이 안내</button></div></header>
<div class="routebar"><button id="back" aria-label="상위 공간으로 복귀">← 상위 공간</button><nav id="breadcrumbs" aria-label="현재 위치"></nav><span class="route-note">이동·카메라·조회는 시간·자원·점수를 바꾸지 않습니다</span></div>
<main>
<section id="viewport" aria-label="3D 세계 탐색"><div class="scene-heading"><div id="scene-eyebrow" class="eyebrow"></div><h1 id="scene-title"></h1><p id="scene-description"></p></div>
<nav id="places" aria-label="공간 이동"><button data-route="world">세계지도</button><button data-route="campus">울산 캠퍼스</button><button data-route="noc">관제동 · 내 자리</button><button data-route="hall">서버동 01</button></nav>
<div id="map-legend"><span><i></i>울산 AIDC (남구 황성동·용연 권역)</span><span><i class="sg"></i>도착한 요청의 경로만 점등</span><span><i class="dim"></i>기타 국제망 · 어둡게</span><span class="legend-note">현실 기반 가상 경로입니다. 실제 케이블 좌표·소유가 아닙니다.</span><button id="motion-toggle" aria-pressed="false">움직임 줄이기</button></div>
<div id="route-chain" hidden></div>
<div id="noc-tools" hidden><button data-noc-view="desk">내 자리</button><button data-noc-view="overview">관제실 전체</button></div>
<div id="hall-tools" hidden><button data-camera="overview">서버동 전체</button><button data-camera="hall">랙 보기</button><button data-camera="aisle">통로</button><button id="focus-rack">선택 랙 보기</button><button id="ceiling-toggle" aria-pressed="false">천장 설비 보기</button><div class="layer-tools"><button data-layer="network" aria-pressed="true">네트워크</button><button data-layer="cooling" aria-pressed="true">냉각</button><button data-layer="power" aria-pressed="true">전력</button></div></div>
<section id="workstation" aria-label="내 모니터" hidden></section>
<div id="transit" hidden aria-live="polite"></div><div id="toast" hidden role="status" aria-live="polite"></div>
<div id="hover-label" hidden></div><div id="coach-ring" hidden aria-hidden="true"></div><div id="loading">3D 세계 준비 중…</div><div id="fatal" role="alert" hidden></div>
<div class="scene-caption"><b id="scene-code"></b><span id="scene-footnote"></span><span class="caption-line"></span><span>DESKTOP HIGH</span></div>
<div class="camera-help"><kbd>드래그</kbd> 회전 <kbd>우클릭</kbd> 이동 <kbd>휠</kbd> 확대 <kbd>W A S D</kbd> 이동 <kbd>F</kbd> 초점</div>
<section id="talk" hidden aria-live="polite" aria-label="선배와의 대화"></section></section>
<aside id="panel" aria-label="현재 목표와 작업">
  <section class="goal-head"><div class="goal-top"><span id="goal-step"></span><span id="goal-pips" aria-hidden="true"></span></div><h2 id="goal-title"></h2><p id="goal-hint"></p><p id="goal-why"></p><p id="goal-where"></p></section>
  <section id="coach" hidden aria-label="선배의 튜토리얼 안내" aria-live="polite"></section>
  <section id="panel-body">
    <div class="req-summary" id="req-summary"></div>
    <div id="context-card"></div>
    <details id="detail"><summary>자세히 보기 · 원래 조건 · 서버 원장 · 기록</summary><div id="detail-body"></div></details>
  </section>
  <section class="panel-action"><div id="action-feedback" role="status" aria-live="polite"></div></section>
</aside>
<section class="mission-strip"><div class="mission-title"><span class="eyebrow" id="strip-eyebrow">MY SHIFT</span><strong id="objective"></strong></div><ol id="stepper"></ol><div class="mission-id"><strong id="strip-id"></strong><span id="strip-sub"></span></div></section>
</main><footer><span><b>WORLD / PHASE 4</b> · <span id="engine-status">Python 엔진 확인 중…</span></span><span id="performance">성능 측정 중…</span><button id="perf-toggle" aria-expanded="false">성능 상세</button><a href="./lab.html">기존 3D 실험실</a></footer><div id="perf-panel" hidden></div>
<div id="coach-tag" hidden aria-hidden="true"></div>
<div id="menu" hidden role="dialog" aria-label="모드 선택"></div>
<div id="opening" hidden><div id="opening-fade"></div><div class="opening-top"><span class="mode-badge">가상 세계 · 실제 회선 아님</span><button id="opening-skip">건너뛰기 · Esc</button></div><div class="opening-caption"><span id="opening-step"></span><h2 id="opening-title"></h2><p id="opening-sub"></p><div class="opening-progress"><i id="opening-bar"></i></div></div></div>
<dialog id="screen-dialog"><div id="screen-slot"></div></dialog>
<dialog id="help"><button id="help-close" aria-label="안내 닫기">닫기</button><span class="eyebrow">플레이 안내</span><h2>모든 진행은 화면 속 실제 조작으로 합니다.</h2><ol><li>요청은 <b>내 모니터</b>(관제동 · 내 자리)의 요청함에 도착합니다. 세계지도에는 실제로 도착한 요청의 경로만 빛납니다.</li><li>[배정 계획]에서 고객 조건에 맞는 배정안을 고르고, <b>서버동 01</b>에서 그 배정안의 서버 랙(A-01~D-01)을 골라 시작합니다.</li><li>위쪽 시계 옆 [⏩] 버튼이 가상 시간을 진행합니다. 장애가 나면 [장비 진단]으로 근거를 보고 대응합니다.</li><li>캠퍼스 건물: 한 번 클릭 = 정보, 두 번 클릭(또는 Enter) = 내부. [← 상위 공간]으로 돌아옵니다.</li></ol><p>규칙(시간·GPU/전력·고객 동의·기한·점수·장애)은 기존 Python 게임 엔진이 계산합니다. 3D 화면은 그 결과를 보여 줍니다. 고객·회선·수치는 교육용 가상 데이터입니다.</p><p>3D 화면: 드래그 회전 · 우클릭 이동 · 휠 확대 · W/A/S/D 이동 · F 초점.</p></dialog>`;

const $=id=>document.getElementById(id),store=createWorldStore(),api=createEngineClient();
const GAME_KEY='srs3d.game.v1';
let scene,lastViewKey=null,frame=0,lastTime=performance.now(),lastPerf=0,perfOpen=false,reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
let openingActive=false,openingStart=0,openingResult=null,openingLocation=null,transitTimer=0,toastTimer=0;
let gameId=null,engine={online:null,message:''},pending=0;
const ui={tab:'inbox',plans:{},diagnosis:{},conversation:{},talkPage:0,talkKey:'',talkClosed:''};
const actionLog=[];
const frameTimes=[],gpuTimes=[];let stats={fps:0,p95FrameMs:0,gpuMs:null};
const descriptions={world:'한국을 중심으로 본 가상 국제망. 실제로 도착한 요청의 경로만 빛납니다.',campus:'건물을 한 번 누르면 정보, 두 번 누르면 내부로 들어갑니다.',noc:'요청을 받고, 배정을 계획하고, 장애를 진단하고, 결과를 확인하는 내 자리.',hall:'배정한 엔진 서버(1번 열 A-01~D-01)를 직접 찾아 작업을 시작하는 현장.',room:'시설의 기능을 보는 작은 작업 공간 (교육용 모식).'};
const notes={world:'Natural Earth 육지 + 직접 만든 가상 망 / 실제 케이블 데이터 아님',noc:'기존 관제실 재사용 / 내 모니터 = Python 엔진 상태',campus:'자체 제작 캠퍼스·산단 재구성 / 실제 부지·조감도 아님',hall:'엔진 서버 A~D = 랙 A-01~D-01 · 나머지 20개는 장식',room:'교육용 시설 내부 모식 / 게임 규칙 미연결 시연'};
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
function button(text,handler,cls='',attrs={}){const b=el('button',cls,text);b.addEventListener('click',handler);for(const [k,v]of Object.entries(attrs))b.setAttribute(k,v);return b;}
const game=()=>store.state.game;
function routeTitle(route){return route==='room'?`${FACILITIES[store.state.navigation.room].name} 내부`:LOCATIONS[route].title;}

// ---------- talking to the engine ----------
function logAction(action,res){actionLog.push({t:Math.round(performance.now()),clock:res?.game?.clock?.label??null,action,ok:!!res?.ok,message:res?.message||'',hint:res?.hint||'',step:res?.game?.journey?.current?.id??null});if(actionLog.length>400)actionLog.shift();}
async function send(action,{quiet=false}={}){
  if(!gameId)return null;
  pending++;renderBusy();
  const before=game(),res=await api.act(gameId,action);pending--;
  logAction(action,res);
  if(res.offline){setEngine(false,res.message);renderBusy();return res;}
  if(res.game){store.setGame(res.game);}
  if(!res.ok){toast(res.message+(res.hint?` · ${res.hint}`:''),'hint');store.setNotice(res.message);}
  else{if(res.hint)toast(res.hint,'hint');else if(res.message&&!quiet)toast(res.message);if(res.message||res.hint)store.setNotice(res.hint||res.message);}
  screens.afterAction(before,game(),action,res);coach.afterAction(action,res);renderBusy();
  return res;
}
function setEngine(online,message=''){engine={online,message};$('engine-status').textContent=online?'Python 엔진 연결됨 (session.GameSession)':`엔진 미연결 · ${message||'npm run play 로 실행'}`;$('engine-status').dataset.online=String(!!online);}
function renderBusy(){document.body.classList.toggle('engine-busy',pending>0);}
async function openGame(snapshotOrId){
  const res=typeof snapshotOrId==='string'?await api.load(snapshotOrId):{ok:true,game:snapshotOrId};
  if(!res.ok){toast(res.message||'게임을 열 수 없습니다.','hint');try{sessionStorage.removeItem(GAME_KEY);}catch{}return false;}
  // Switching modes saves and releases the previous engine file (it stays on disk for 이어하기).
  if(gameId&&gameId!==res.game.id)api.close(gameId);
  gameId=res.game.id;try{sessionStorage.setItem(GAME_KEY,gameId);}catch{/* reload resume is a convenience only */}
  ui.plans={};ui.diagnosis={};ui.conversation={};ui.tab='inbox';ui.talkPage=0;ui.talkClosed='';
  screens.reset(res.game);store.setGame(res.game);
  // Restore the place the engine journey last recorded; restoring is not a new navigation.
  const route=res.game.journey?.route||'noc';store.state.navigation.nocView='desk';store.navigate(route);history.replaceState(null,'',`#${route}`);
  menu.hide();return true;
}
async function newGame(mode){const res=await api.create(mode);if(!res.ok){toast(res.message||'새 게임을 시작할 수 없습니다.','hint');if(res.offline)setEngine(false,res.message);return false;}return openGame(res.game);}

// ---------- navigation (view-only locally, reported to the journey) ----------
function navigate(route,via='tab',building){
  const from=store.state.navigation.route;
  if(!store.navigate(route))return;
  if(location.hash!==`#${route}`)history.replaceState(null,'',`#${route}`);
  if((from==='noc'&&route==='hall')||(from==='hall'&&route==='noc'))showTransit(from,route);
  send({type:'navigate',route,via,...(building?{building}:{})},{quiet:true});
}
function enterFacility(id,via){if(!store.enterFacility(id))return;const r=store.state.navigation.route;if(location.hash!==`#${r}`)history.replaceState(null,'',`#${r}`);send({type:'navigate',route:r,via,building:id},{quiet:true});}
function selectFacility(id,via){if(store.selectFacility(id))send({type:'select_facility',id,via},{quiet:true});}
function selectCountry(id){if(store.selectCountry(id))send({type:'select_country',id});}
function selectRack(id){if(store.selectRack(id)&&gameId)send({type:'inspect_rack',rack:id},{quiet:true});}
function showTransit(from,to){
  const t=$('transit');t.replaceChildren();const path=el('div','transit-path');
  for(const [k,label]of [[from,from==='noc'?'관제동':'서버동 01'],['link','연결 통로'],[to,to==='noc'?'관제동 · 내 자리':'서버동 01']])path.append(el('span',k==='link'?'link':'',label));
  t.append(el('span','eyebrow','이동 · 별도 건물'),path,el('p','',to==='hall'?'현장: 배정한 서버 랙을 직접 찾아 작업합니다.':'운영: 내 모니터에서 요청과 시설을 관리합니다.'));
  t.hidden=false;clearTimeout(transitTimer);transitTimer=setTimeout(()=>{t.hidden=true;},1400);
}
function toast(text,tone='ok'){if(!text)return;const t=$('toast');t.textContent=text;t.dataset.tone=tone;t.hidden=false;t.classList.remove('pop');void t.offsetWidth;t.classList.add('pop');clearTimeout(toastTimer);toastTimer=setTimeout(()=>{t.hidden=true;},tone==='hint'?4200:2800);}

document.querySelectorAll('#places [data-route]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.route==='noc')store.setNocView('desk');navigate(b.dataset.route,'tab');}));
document.querySelectorAll('[data-noc-view]').forEach(b=>b.addEventListener('click',()=>store.setNocView(b.dataset.nocView)));
$('back').addEventListener('click',()=>{const p=LOCATIONS[store.state.navigation.route].parent;if(p)navigate(p,'back');});
window.addEventListener('hashchange',()=>{const route=location.hash.slice(1);if(Object.hasOwn(LOCATIONS,route)&&route!==store.state.navigation.route)navigate(route,'history');else history.replaceState(null,'',`#${store.state.navigation.route}`);});
$('help-open').addEventListener('click',()=>$('help').showModal());$('help-close').addEventListener('click',()=>$('help').close());
$('menu-open').addEventListener('click',()=>menu.show());
$('perf-toggle').addEventListener('click',()=>{perfOpen=!perfOpen;$('perf-panel').hidden=!perfOpen;$('perf-toggle').setAttribute('aria-expanded',String(perfOpen));});
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>scene.view(b.dataset.camera)));
$('focus-rack').addEventListener('click',()=>scene.focus());
$('ceiling-toggle').addEventListener('click',e=>{const on=e.currentTarget.getAttribute('aria-pressed')!=='true';e.currentTarget.setAttribute('aria-pressed',String(on));e.currentTarget.textContent=on?'천장 설비 숨기기':'천장 설비 보기';scene.setCeiling?.(on);});
$('motion-toggle').addEventListener('click',e=>{reducedMotion=!reducedMotion;e.currentTarget.setAttribute('aria-pressed',String(reducedMotion));});
document.querySelectorAll('[data-layer]').forEach(b=>b.addEventListener('click',()=>{const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));scene.setLayer(b.dataset.layer,on);}));
document.querySelectorAll('[data-advance]').forEach(b=>b.addEventListener('click',()=>send({type:'advance_time',minutes:Number(b.dataset.advance)})));
$('opening-skip').addEventListener('click',()=>finishOpening('skipped'));$('opening-replay').addEventListener('click',()=>startOpening());
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&openingActive){e.preventDefault();finishOpening('skipped');return;}
  // Keyboard alternative to double-click: Enter on the 3D view enters the selected building.
  if(e.key==='Enter'&&!openingActive&&store.state.navigation.route==='campus'&&document.activeElement===scene?.renderer.domElement){e.preventDefault();enterFacility(store.state.navigation.facility,'key');}
});

// ---------- shared widgets ----------
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
function readingsGrid(rows,cls='ops-readings'){const g=el('dl',cls);for(const [k,v]of rows)g.append(el('dt','',k),el('dd','',v));return g;}
function checkResult(c){if(!c)return null;const box=el('div','ops-result');box.append(el('strong','',c.title),el('p','',c.detail),el('small','',`조회 시점: ${STAGE_LABEL[c.phase]||'요청 없음'} · 기록 #${c.seq}`));return box;}
function opsButton(action,label,primary=false){const b=button(label,()=>{const r=store.ops(action);if(r.ok)toast(OPS_FEEDBACK[action]);else toast(r.reason,'hint');},primary?'primary':'');b.dataset.ops=action;return b;}
const COOLING_LABELS={'cooling-off':'보조 냉각 끄기','cooling-on':'보조 냉각 켜기','cooling-warn':'경고 시나리오 · 유량 저하','cooling-reset':'유량 점검 완료 · 재가동'};
const OPS_FEEDBACK={'cooling-off':'보조 냉각 꺼짐 · 팬 정지, 냉각수 흐름 중단','cooling-on':'보조 냉각 켜짐 · 팬 회전, 냉각수 순환','cooling-warn':'경고 · 냉각수 유량이 12 L/min으로 떨어졌습니다','cooling-reset':'점검 완료 · 보조 냉각이 정상 재가동됐습니다','power-check':'전력 계통 점검 완료','ups-test':'UPS 자가진단 정상','network-lookup':'경로 상태 조회 완료'};
const FACILITY_ROLE={NOC:'운영 건물 · 내 자리와 업무 모니터','HALL-01':'현장 건물 · 엔진 서버 A~D',POWER:'A/B 이중 수전과 배전',UPS:'정전 순간을 버티는 예비 전원',COOLING:'교육용 보조 냉각 계통 AUX-C1',NETWORK:'국제 가상 회선과 서버동 업링크'};
const chip=(text,tone)=>{const c=el('span','chip',text);if(tone)c.dataset.tone=tone;return c;};
const STAGE_TONE={incoming:'new',running:'ok',hw_fault:'fault',hw_repair:'recover',migration:'recover',net_fault:'fault',recovering:'recover',done:'done',failed:'fault',rejected:'muted'};

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
    root.append(el('p','ops-note','보조 냉각 조작은 3D 시설 시연이며 게임 규칙(시간·자원·점수)과 연결되지 않습니다.'));
  }else if(id==='POWER'){
    const p=powerView(state);root.append(readingsGrid([['수전',p.feeds],['부하 합계',`${p.totalKW} / ${p.capacityKW} kW`],...(full?[['IT 부하',`${p.itLoadKW} kW`],['보조 냉각',`${p.coolingLoadKW} kW`]]:[])]));
    const t=engineTotals(state.game);if(t)root.append(el('p','card-line',`엔진 전력 원장: 사용 ${t.power} 단위 (게임 규칙의 전력은 이 값입니다)`));
    actions.append(opsButton('power-check','전력 계통 점검'));root.append(actions);const r=checkResult(state.ops.checks.power);if(r)root.append(r);
  }else if(id==='UPS'){
    const u=upsView(state);root.append(readingsGrid([['배터리',`${u.battery}%`],['상태',u.mode],...(full?[['예비 시간',u.runtime]]:[])]));
    actions.append(opsButton('ups-test','UPS 자가진단'));root.append(actions);const r=checkResult(state.ops.checks.ups);if(r)root.append(r);
  }else if(id==='NETWORK'){
    const n=networkView(state);root.append(readingsGrid([['서버동 01 업링크',n.uplink],['도착한 요청 경로',`${activePaths(state).length}개`]]));
    if(full){const table=el('div','link-table');for(const l of n.links){const row=el('div',`link-row${l.status==='대역폭 부족'?' bad':''}`);row.dataset.link=l.id;row.append(el('span','',`${l.name}${l.active?' · 요청 중':''}`),el('span','',`${l.latencyMs} ms (가상)`),el('span','',l.status));table.append(row);}root.append(table);}
    actions.append(opsButton('network-lookup','경로 상태 조회'));root.append(actions);
    const c=state.ops.checks.network,r=checkResult(c);if(r){root.append(r);if(c.target){const go=button(c.target==='hall'?'서버동 01로 이동':'내 자리로 이동',()=>{if(c.target==='noc')store.setNocView('desk');navigate(c.target,'button');},'',{id:'network-go'});root.append(go);}}
  }else if(id==='HALL-01'){
    const h=hallView(state);root.append(readingsGrid([['엔진 서버',`A~D · GPU ${h.gpuUsed}/${h.gpuTotal} 사용`],['장애·복구 중 서버',`${h.faults}대`],['랙',`엔진 4 (A-01~D-01) · 장식 20`]]));
  }else if(id==='NOC'){
    const open=(state.game?.requests??[]).filter(isOpen).length;root.append(readingsGrid([['운영석','6석 · 근무 5명 (가상)'],['내 요청함',state.game?`열린 요청 ${open}건`:'게임 시작 전']]));
  }
  return root;
}

// ---------- right panel ----------
function goalHead(){
  const g=game(),j=g?.journey,cur=j?.current;let step='',title='',hint='',why='',where='',pips=[];
  if(!g){step='게임 선택 전';title=engine.online===false?'Python 엔진이 꺼져 있습니다':'모드를 고르세요';hint=engine.online===false?'npm run play 로 엔진을 실행한 뒤 새로고침하세요. 3D 공간은 둘러볼 수 있습니다.':'위쪽 [메뉴 · 모드]에서 튜토리얼 / 스토리 도전 / 자유·연습을 시작합니다.';}
  else if(j?.kind==='tutorial'&&!j.skipped&&!j.completed&&cur){step=`튜토리얼 · 목표 ${cur.goalIndex}/${j.total}`;title=`${cur.goalTitle} — ${cur.title}`;hint=cur.what;why=`왜: ${cur.why}`;where=`어디서: ${cur.where}`;pips=j.goals.map(x=>x.done?'done':x.current?'now':'');}
  else if(j?.kind==='tutorial'){step=j.completed?'튜토리얼 · 실습 완료':'튜토리얼 · 안내 끔';title=j.completed?'실습을 모두 마쳤습니다':'안내 없이 자유롭게 진행 중';hint=j.completed?'[메뉴 · 모드]에서 스토리 도전을 시작하세요.':'엔진 상태는 그대로입니다. 완료하려면 실제 업무를 끝내세요.';}
  else{const sg=storyGoal(g)||freeGoal(g);if(sg){step=sg.label;title=sg.title;hint=sg.what;why=sg.mentor?`선배: ${sg.mentor}`:'';}}
  $('goal-step').textContent=step;$('goal-title').textContent=title;$('goal-hint').textContent=hint;$('goal-why').textContent=why;$('goal-where').textContent=where;
  $('goal-why').hidden=!why;$('goal-where').hidden=!where;
  $('goal-pips').replaceChildren(...pips.map(c=>{const p=el('i');p.className=c;return p;}));
}
function requestSummary(){
  const root=$('req-summary'),g=game(),r=focusRequest(g);root.replaceChildren();
  if(!g){root.append(el('p','card-line','게임을 시작하면 Python 엔진의 실제 요청·자원·시각이 여기에 표시됩니다.'));return;}
  if(!r){root.append(el('p','card-line','아직 도착한 요청이 없습니다.'));return;}
  const row=el('div','req-row');row.append(el('span','flag',r.code),el('strong','',`요청 #${r.id} · ${r.company}`),chip(STAGE_LABEL[r.stage],STAGE_TONE[r.stage]));root.append(row);
  root.append(el('div','req-terms',termsLine(r)));
  const track=el('div','progress-track'),bar=el('i');bar.style.width=`${r.progress}%`;track.append(bar);root.append(track);
  const t=engineTotals(g),fault=(g.servers||[]).find(s=>s.state!=='HEALTHY');
  const chips=el('div','status-chips');
  chips.append(el('span','',`진행 ${Math.round(r.progress)}%`),el('span','',`GPU ${t.gpu} · 전력 ${t.power}`),el('span',fault?'bad':'',fault?`Server ${fault.key} ${fault.state}`:'서버 정상'));root.append(chips);
}
function contextCard(){
  const state=store.state,nav=state.navigation,route=nav.route,root=$('context-card'),g=game();root.replaceChildren();
  if(route==='world'){
    const chips=el('div','chip-row');for(const [id,c]of Object.entries(COUNTRIES)){const b=button(id,()=>selectCountry(id),id===nav.country?'active':'',{'data-country':id,'aria-label':`${c.name} 선택`});chips.append(b);}root.append(chips);
    const fp=focusPath(state);root.append(el('p','card-line',fp?fp.message:g?'지금 열린 요청이 없습니다. 모든 고객 경로가 어둡습니다.':'게임을 시작하면 도착한 요청의 경로만 빛납니다.'));
    if(nav.country&&nav.country!=='KR'){const live=activePaths(state).find(p=>p.code===nav.country);root.append(el('p','card-sub',live?`${COUNTRY_NAMES[nav.country]} · 요청 #${live.rid} 경로 점등 중`:`${COUNTRY_NAMES[nav.country]} · 지금 도착한 요청 없음`));}
  }else if(route==='campus'){
    const chips=el('div','chip-row facilities');for(const [id,f]of Object.entries(FACILITIES)){const b=button(f.name,()=>selectFacility(id,'chip'),id===nav.facility?'active':'',{'data-facility':id});chips.append(b);}root.append(chips);
    root.append(facilityCard(nav.facility,state));
    const enter=button(nav.facility==='NOC'?'내 자리로 들어가기':nav.facility==='HALL-01'?'서버동 01로 들어가기':'내부로 들어가기',()=>enterFacility(nav.facility,'button'),'',{id:'enter-building',title:'건물을 두 번 클릭하거나 3D 화면에서 Enter'});root.append(enter,el('p','card-tip','팁: 건물을 두 번 클릭(또는 Enter)하면 내부로 들어갑니다.'));
  }else if(route==='noc'){
    root.append(el('p','card-line','내 모니터: 요청함 · 배정 계획 · 장비 진단 · 결과. 시간은 위쪽 시계 옆 [⏩]로 진행합니다.'));
    const t=el('div','chip-row');t.append(button('내 자리',()=>store.setNocView('desk'),nav.nocView==='desk'?'active':'',{'data-noc-view':'desk'}),button('관제실 전체',()=>store.setNocView('overview'),nav.nocView==='overview'?'active':'',{'data-noc-view':'overview'}));root.append(t);
  }else if(route==='hall'){
    root.append(rackCard());
  }else if(route==='room'){
    root.append(facilityCard(nav.room,state,true));
  }
}
// Rack card: engine server data for A-01..D-01; decoration racks say so. Start / re-check are real actions.
function rackCard(){
  const state=store.state,g=game(),a=state.facility.assets.find(x=>x.id===state.facility.selectedId),root=el('div','rack-card'),server=serverOfRack(a.id),r=focusRequest(g);
  const head=el('div','fc-head');head.append(el('strong','',server?`Server ${server} · 랙 ${a.id}`:`랙 ${a.id}`),el('span',`asset-chip`,server?'엔진 서버':'장식 랙'));root.append(head);
  if(!server){root.append(el('p','card-line','교육 범위 밖의 장식 랙입니다. 게임 자원은 1번 열의 엔진 서버 A~D(A-01~D-01)만 사용합니다.'));}
  else if(!g){root.append(el('p','card-line','게임을 시작하면 이 서버의 GPU 슬롯·전력·건강 상태가 표시됩니다.'));}
  else{
    const s=g.servers.find(x=>x.key===server);
    const slots=el('div','gpu-slots');s.slots.forEach((owner,i)=>{const d=el('span',owner?'used':'',owner?`#${owner}`:'빈');d.title=`GPU 슬롯 ${i}`;slots.append(d);});
    root.append(readingsGrid([['상태',s.state==='HEALTHY'?'정상 (HEALTHY)':s.state==='FAULT'?`장애 (FAULT) · ${s.reason||''}`:`복구 중 · ${s.repairLeft}분 남음`],['GPU',`${s.usedGpu}/${s.gpu} 사용`],['전력',`${s.usedPower}/${s.power} 단위`]]),slots);
    if(r){
      const inSel=r.selection?.slices?.find(p=>p.server===server),inAlloc=r.allocation?.find(p=>p.server===server);
      if(isOpen(r)&&r.stage==='incoming'&&r.selection){
        if(inSel){root.append(el('p','card-line ok',`배정안 포함 · 요청 #${r.id} · GPU ${inSel.gpu} / 전력 ${inSel.power} 예정`));root.append(button('이 배정으로 작업 시작',()=>send({type:'start_job',rid:r.id,rack:a.id}),'primary big',{'data-start-job':a.id}));}
        else root.append(el('p','card-line',`요청 #${r.id}의 배정안에는 이 서버가 없습니다. 배정안: ${r.selection.slices.map(p=>`${p.server}(${p.rack})`).join(' · ')}`));
      }else if(isOpen(r)&&r.stage==='incoming')root.append(el('p','card-line','아직 고른 배정안이 없습니다. 내 모니터 [배정 계획]에서 먼저 고르세요.'));
      if(inAlloc){root.append(el('p','card-line',`요청 #${r.id} 실행 위치 · GPU 슬롯 ${inAlloc.gpuSlots.join(',')} · 전력 ${inAlloc.power}`));root.append(button('상태 재확인',()=>send({type:'verify',rid:r.id,rack:a.id}),'',{'data-verify':a.id}));}
    }
  }
  const label=el('label','select-line','랙 선택 (키보드)'),select=el('select');select.id='equipment-select';select.setAttribute('aria-label','랙 선택');
  for(const x of state.facility.assets.filter(x=>x.kind==='rack')){const sv=serverOfRack(x.id);const o=el('option','',sv?`${x.id} · Server ${sv}`:`${x.id} · 장식`);o.value=x.id;select.append(o);}
  select.value=a.kind==='rack'?a.id:'A-01';select.addEventListener('change',()=>{selectRack(select.value);scene.focus();});label.append(select);root.append(label);
  return root;
}
function detailBody(){
  const g=game(),r=focusRequest(g),root=$('detail-body');root.replaceChildren();
  if(!g||!r){root.append(el('p','ops-note','게임을 시작하면 엔진 기록이 표시됩니다.'));return;}
  const plans=r.conditions?.plans||{};
  root.append(readingsGrid([['요청 / 고객',`#${r.id} / ${r.company} (${COUNTRY_NAMES[r.code]||r.country})`],['작업',r.title],
    ...Object.entries(plans).map(([k,p])=>[MODE_NAMES[k],`GPU ${p.gpu} · 전력 ${p.power} · 네트워크 ${p.network}`]),
    ['허용 모드',allowedLine(r)],['기한',`접수 ${r.terms.received} · 완료 기한 ${r.terms.due} · 최종 접수 ${r.terms.expires}`],
    ['실행',r.planLabel?`${r.planLabel} · GPU ${r.gpu} / 전력 ${r.power}`:'미배정'],['위치',r.allocation.length?r.allocation.map(p=>`${p.server}(${p.rack}) GPU${p.gpu}/전력${p.power}`).join(' · '):'—']]));
  const list=el('ol','result-timeline');for(const line of r.log.slice(-6))list.append(el('li','',line));root.append(list);
  root.append(el('p','ops-note','모든 값은 Python 엔진(session.GameSession)의 실제 상태입니다. 고객·수치는 교육용 가상 데이터입니다.'));
}

// ---------- my monitor ----------
const TABS=[['inbox','요청함'],['plan','배정 계획'],['diagnosis','장비 진단'],['result','결과']];
function openTab(tab){
  ui.tab=tab;const r=focusRequest(game());
  if(tab==='plan'&&r&&r.stage==='incoming')send({type:'view_plans',rid:r.id},{quiet:true}).then(res=>{if(res?.ok){ui.plans[r.id]={...res.result.plans,clock:res.game.clock.label};render();}});
  else if(tab==='diagnosis'&&r&&r.allocation.length)send({type:'diagnose',rid:r.id},{quiet:true}).then(res=>{if(res?.ok){ui.diagnosis[r.id]={...res.result.diagnosis,clock:res.game.clock.label,stage:requestById(res.game,r.id)?.stage};render();}});
  render();
}
function renderWorkstation(){
  const state=store.state,ws=$('workstation'),g=game();
  ws.hidden=!(state.navigation.route==='noc'&&state.navigation.nocView==='desk')||openingActive||!g;if(ws.hidden)return;
  const active=document.activeElement,focusKey=active?.dataset?.focusKey;ws.replaceChildren();
  const bar=el('div','ws-titlebar');bar.append(el('span','','SRS-OPS · 운영석 03 · 내 모니터'),el('span','ws-shift',`${g.modeLabel} · ${g.clock.label}`));
  const tabs=el('div','ws-tabs');tabs.setAttribute('role','tablist');
  const r=focusRequest(g);
  for(const [id,label]of TABS){
    const badge=id==='inbox'?(g.requests.filter(x=>x.unread).length||''):id==='diagnosis'&&r&&['hw_fault','net_fault'].includes(r.stage)?'!':id==='result'&&r&&!isOpen(r)&&!r.reported?'●':'';
    const b=button(badge?`${label} ${badge}`:label,()=>openTab(id),ui.tab===id?'active':'',{'data-ws-tab':id,role:'tab','aria-selected':String(ui.tab===id)});b.dataset.focusKey=`tab-${id}`;tabs.append(b);
  }
  const body=el('div','ws-pane');body.dataset.pane=ui.tab;
  ({inbox:paneInbox,plan:panePlan,diagnosis:paneDiagnosis,result:paneResult})[ui.tab](body,g,r);
  ws.append(bar,tabs,body);
  if(focusKey){const again=ws.querySelector(`[data-focus-key="${focusKey}"]`);again?.focus({preventScroll:true});}
}
function paneInbox(body,g,r){
  const list=el('div','ws-list');
  for(const x of [...g.requests].reverse()){const row=button('',()=>{if(x.id!==g.focus)send({type:'select_request',rid:x.id},{quiet:true});},x.id===r?.id?'ws-row active':'ws-row',{'data-request-row':String(x.id)});row.append(el('span','flag',x.code),el('strong','',`#${x.id} ${x.company}`),el('span','',x.title),chip(STAGE_LABEL[x.stage],STAGE_TONE[x.stage]));if(x.unread)row.append(el('i','dot'));list.append(row);}
  body.append(list);
  if(!r)return;
  const card=el('div','ws-card');
  card.append(el('div','ws-label',`요청 #${r.id} · ${COUNTRY_NAMES[r.code]||r.country} · ${r.terms.priority||''}`));
  const plans=r.conditions?.plans||{},table=el('table','terms-table');table.innerHTML='<thead><tr><th>모드</th><th>GPU</th><th>전력</th><th>네트워크</th><th>고객 허용</th></tr></thead>';
  const tb=el('tbody');for(const [k,p]of Object.entries(plans)){const tr=el('tr');const allowed=r.conditions.allowedModes.includes(k);tr.append(el('td','',`${MODE_NAMES[k]}${k===r.conditions.requestedMode?' (원래 요청)':''}`),el('td','',p.gpu),el('td','',p.power),el('td','',p.network),el('td',allowed?'ok':'warn',allowed?'허용':'동의 필요'));tb.append(tr);}table.append(tb);
  card.append(table,el('p','ws-note',`접수 ${r.terms.received} · 완료 기한 ${r.terms.due} · 미배정 시 최종 접수 종료 ${r.terms.expires}`));
  const conv=ui.conversation[r.id];
  if(conv){const box=el('div','ws-message');for(const [who,text]of conv)box.append(el('strong','',who),el('p','',text.replace(/^\[[^\]]+\]\s*/,'')));card.append(box);}
  const read=button(conv?'요청서 다시 읽기':'요청서 열기 · 고객 메시지 읽기',async()=>{const res=await send({type:'read_request',rid:r.id},{quiet:true});if(res?.ok){ui.conversation[r.id]=res.result.conversation;render();}},'primary',{'data-read-request':String(r.id)});read.dataset.focusKey='read';
  card.append(read);
  if(r.stage==='incoming')card.append(el('p','ws-tip','다음: [배정 계획] 탭에서 모드와 배정안을 비교하세요. 조회는 자원을 쓰지 않습니다.'));
  body.append(card);
}
function modeRow(r,row,res){
  const box=el('div',`mode-card${row.agreed?'':' blocked'}`);box.dataset.mode=row.key;
  const head=el('div','mode-head');head.append(el('strong','',row.label),chip(row.status,row.agreed?'ok':'warn'));box.append(head);
  box.append(el('p','ws-note',`GPU ${row.gpu} · 전력 ${row.power} · 지금 시작하면 ${row.minutes}분 → ${row.finish_label} 완료 (기한 ${row.due_label} ${row.on_time?'준수':'초과'})`));
  if(!row.agreed){box.append(el('p','ws-warn',row.reason||res?.reason||'지금 시작할 수 없습니다.'));
    if(r.proposal?.status==='pending')box.append(button('고객 답변 확인',()=>send({type:'check_reply',rid:r.id}),'',{'data-check-reply':String(r.id)}));
    else if(!r.proposal&&r.conditions?.type==='fixed')box.append(button('대안 제시 · 고객 동의 요청',()=>send({type:'propose_alternative',rid:r.id}),'',{'data-propose':String(r.id)}));
  }
  const options=res?.options||[];
  if(row.agreed&&res){
    if(!options.length)box.append(el('p','ws-warn',res.reason));
    const list=el('div','plan-options');
    options.forEach((parts,i)=>{const sel=r.selection&&r.selection.mode===row.key&&r.selection.index===i;
      const b=button('',()=>send({type:'select_plan',rid:r.id,mode:row.key,index:i}),`plan-option${sel?' selected':''}`,{'data-plan-option':`${row.key}:${i}`,'aria-pressed':String(!!sel)});
      b.append(el('strong','',`배정안 ${i+1}${sel?' · 선택됨':''}`));for(const p of parts)b.append(el('span','',`Server ${p.server} (${p.rack}) · GPU ${p.gpu} / 전력 ${p.power}`));list.append(b);});
    box.append(list);
  }else if(!row.agreed&&res){box.append(el('small','ws-note',`엔진 판정: ${res.reason}`));}
  return box;
}
function panePlan(body,g,r){
  if(!r){body.append(el('p','ws-note','요청이 없습니다.'));return;}
  if(r.stage!=='incoming'){body.append(el('p','ws-note',r.allocation.length?`요청 #${r.id}은 이미 배정되었습니다: ${r.planLabel} · ${r.allocation.map(p=>`${p.server}(${p.rack})`).join(' · ')}`:`요청 #${r.id}: ${STAGE_LABEL[r.stage]}`));return;}
  const res=ui.plans[r.id];
  const head=el('div','ws-label',`요청 #${r.id} 배정 계획 · ${allowedLine(r)}${res?` · 조회 ${res.clock}`:''}`);body.append(head);
  if(!res){body.append(el('p','ws-note','엔진에 배정안을 조회하는 중…'));return;}
  const list=el('div','mode-list');list.dataset.planList='';
  for(const row of r.modes)list.append(modeRow(r,row,res[row.key]));
  body.append(list);
  const foot=el('div','ws-foot');foot.append(button('다시 조회',()=>openTab('plan'),'link'));
  foot.append(el('span','ws-tip',r.selection?`선택: ${r.selection.label} 배정안 ${r.selection.index+1} → [서버동 01]에서 ${r.selection.slices.map(p=>p.rack).join('·')} 중 한 랙을 골라 시작`:'카드를 고르면 선택만 기억합니다. GPU·전력은 현장에서 시작할 때 점유됩니다.'));
  body.append(foot);
}
function paneDiagnosis(body,g,r){
  if(!r||!r.allocation.length){body.append(el('p','ws-note','실행 중인 작업이 없습니다. 작업을 시작한 뒤 진단할 수 있습니다.'));return;}
  const d=ui.diagnosis[r.id];
  body.append(el('div','ws-label',`요청 #${r.id} 장비 진단${d?` · 조회 ${d.clock}`:''} · 증상: ${STAGE_LABEL[r.stage]} · 진행률 ${Math.round(r.progress)}%`));
  if(!d){body.append(el('p','ws-note','엔진에 진단을 요청하는 중…'));return;}
  if(d.clock!==g.clock.label||d.stage!==r.stage)body.append(el('p','ws-warn',`진단 후 상태가 바뀌었습니다 (진단 ${d.clock} · 지금 ${g.clock.label} ${STAGE_LABEL[r.stage]}). 아래 [다시 진단]으로 최신 증거를 보세요.`));
  const grid=el('div','diag-grid');
  const ev=el('div','ws-card');ev.append(el('strong','','증거'));
  ev.append(readingsGrid([['서버',d.hardware],['네트워크',d.network],['작업 이전',d.migration.allowed?'가능':`불가 · ${d.migration.reason}`],['정상 서버 여유',`GPU ${d.free.gpu} · 전력 ${d.free.power}`]]));
  const servers=el('div','diag-servers');for(const s of d.servers)servers.append(chip(`${s.key}(${s.rack}) ${s.state}${s.repairLeft?` ${s.repairLeft}분`:''}`,s.state==='HEALTHY'?'ok':s.state==='FAULT'?'fault':'recover'));ev.append(servers);
  const acts=el('div','ws-card responses');acts.dataset.responses='';acts.append(el('strong','','대응 (엔진이 조건을 검사합니다)'));
  for(const s of d.servers)acts.append(button(`Server ${s.key} 장비 복구 시작 (20분)`,()=>send({type:'begin_repair',rid:r.id,server:s.key}),'',{'data-repair':s.key}));
  acts.append(button('작업 이전 (정상 서버로, 준비 10분)',()=>send({type:'migrate',rid:r.id,index:0}),'',{'data-migrate':String(r.id)}));
  for(const [k,label]of Object.entries(g.responses))acts.append(button(`네트워크 대응 · ${label}`,()=>send({type:'respond',rid:r.id,key:k}),'',{'data-respond':k}));
  if(r.canNotifyDelay)acts.append(button('고객에게 지연 안내',()=>send({type:'notify_delay',rid:r.id}),'',{'data-notify-delay':String(r.id)}));
  grid.append(ev,acts);body.append(grid);
  body.append(button('다시 진단',()=>openTab('diagnosis'),'link'));
}
function paneResult(body,g,r){
  const done=g.requests.filter(x=>!isOpen(x));
  if(!done.length){body.append(el('p','ws-note','아직 끝난 업무가 없습니다. 작업이 100%가 되면 엔진이 자원을 반환하고 결과를 기록합니다.'));return;}
  const target=r&&!isOpen(r)?r:done.at(-1),s=target.summary||{};
  const card=el('div','ws-card result-card');card.append(el('strong','',`요청 #${target.id} · ${target.company} · ${s.label||STAGE_LABEL[target.stage]}`));
  const orig=target.conditions?.plans?.[target.conditions.requestedMode];
  card.append(readingsGrid([['원래 조건',orig?`${MODE_NAMES[target.conditions.requestedMode]} · GPU ${orig.gpu} / 전력 ${orig.power} / 네트워크 ${orig.network}`:'—'],['실행 조건',s.mode?`${s.mode} · GPU ${s.gpu} / 전력 ${s.power}`:'미실행'],
    ['기한',s.due?`완료 ${s.completed} / 기한 ${s.due} · ${s.deadline}`:'—'],['자원',target.stage==='done'?`GPU ${target.gpu} · 전력 ${target.power} 반환됨`:'—'],['운영 점수',target.score!=null?`${target.score}점`:'—']]));
  const conv=ui.conversation[target.id];
  if(conv){const box=el('div','ws-message');for(const [who,text]of conv)box.append(el('strong','',who),el('p','',text.replace(/^\[[^\]]+\]\s*/,'')));card.append(box);}
  card.append(button(target.reported?'고객 회신 다시 읽기':'결과 확인 · 고객 회신 읽기',async()=>{const res=await send({type:'report',rid:target.id},{quiet:true});if(res?.ok){ui.conversation[target.id]=res.result.conversation;render();}},'primary',{'data-report':String(target.id)}));
  body.append(card);
}

// ---------- header / strip ----------
function renderHeader(){
  const g=game();$('mode-badge').textContent=g?`${g.mode==='tutorial'?g.story.chapter.heading:g.story?`${g.modeLabel} · ${g.story.chapter.heading}`:g.modeLabel} · 엔진 연결`:engine.online===false?'엔진 미연결':'게임 선택 전';$('mode-badge').dataset.mode=g?.mode||'';
  $('clock-time').textContent=g?.clock.label??'—';
  for(const b of document.querySelectorAll('[data-advance]')){b.disabled=!g||!g.canAdvance;b.title=!g?'게임을 시작하세요':!g.canAdvance?'진행 중인 작업이 없습니다 · 먼저 작업을 시작하세요':`가상 시간 ${b.dataset.advance}분 진행`;}
}
function renderStrip(){
  const g=game(),j=g?.journey;
  if(j?.kind==='tutorial'&&j.goals){$('strip-eyebrow').textContent='TUTORIAL · 실습';$('objective').textContent=j.completed?'실습 완료':j.current?`${j.current.goalIndex}/${j.total} ${j.current.goalTitle}`:'안내 끔';
    $('stepper').replaceChildren(...j.goals.map(x=>el('li',x.done?'done':x.current?'now':'',x.title)));}
  else if(g?.story){const st=g.story;$('strip-eyebrow').textContent=`STORY · ${st.chapter.heading}`;$('objective').textContent=st.done?`${st.chapter.label} 클리어`:storyGoal(g)?.what??'';
    $('stepper').replaceChildren(...Array.from({length:st.jobsTotal},(_,i)=>el('li',i<st.jobsDone?'done':i===st.jobsDone&&!st.done?'now':'',`업무 ${i+1}`)));}
  else if(g){$('strip-eyebrow').textContent='FREE · 자유 운영';$('objective').textContent=freeGoal(g)?.what??'';$('stepper').replaceChildren();}
  else{$('strip-eyebrow').textContent='MY SHIFT';$('objective').textContent='모드를 고르면 근무가 시작됩니다';$('stepper').replaceChildren();}
  const r=focusRequest(g);$('strip-id').textContent=r?`요청 #${r.id} · ${r.code}`:'—';$('strip-sub').textContent=g?`Python 엔진 · ${g.id}`:'엔진 저장 없음';
}
function renderRouteChain(state){
  const box=$('route-chain');box.hidden=state.navigation.route!=='world';if(box.hidden)return;
  const fp=focusPath(state);box.replaceChildren(el('span','eyebrow',fp?`요청 #${fp.rid} 경로 · ${COUNTRY_NAMES[fp.code]} → 울산 · 가상`:'도착한 요청 없음 · 모든 경로 소등'));
  const chain=el('div','chain');
  for(const [k,label]of [['sea','해저 구간'],['landing','부산 권역 육양국'],['backbone','국내 지상망'],['aidc','울산 AIDC · 서버동']]){const st=fp?.segments[k]||'off',bad=st!=='ok'&&st!=='off';const s=el('span',`hop${bad?' bad':''}${fp?' on':''}`,`${bad?'⚠ ':''}${label}`);s.dataset.hop=k;s.dataset.state=st;chain.append(s);}
  box.append(chain,el('small','',fp?fp.message:'해저 케이블은 해안 육양국에서 국내망으로 이어집니다. 건물에 직접 닿지 않습니다.'));
}

// ---------- senior dialogue (briefing). [다음] only turns the page; [근무 시작] is the real action. ----------
const TUTORIAL_BRIEFING=[['mentor','첫 출근을 환영해요!\n저는 오늘 교육을 맡은 선배 엔지니어예요.'],['player','잘 부탁드립니다.\n어디서부터 보면 될까요?'],['mentor','오늘은 실제 화면을 직접 눌러 보며 고객 요청 하나를 끝까지 처리해요.\n저는 어디를 보면 되는지만 알려 줄게요.'],['mentor','오른쪽 위 목표가 지금 할 일 하나예요.\n준비되면 [근무 시작]을 눌러요.']];
const SPEAKER={mentor:'교육 담당자 · 선배 엔지니어',player:'나 · 신입 엔지니어'};
function talkPages(){
  const g=game();if(!g)return null;
  if(g.journey?.kind==='tutorial'&&!g.journey.skipped&&g.journey.current?.id==='briefing')return {key:`${g.id}:tutorial`,pages:TUTORIAL_BRIEFING};
  if(g.mode==='story'&&g.story?.step==='arrival'&&g.story.pages.length)return {key:`${g.id}:story`,pages:g.story.pages};
  return null;
}
function renderTalk(){
  const box=$('talk'),t=talkPages();box.hidden=!t||openingActive||!menu.hidden();if(box.hidden)return;
  if(ui.talkKey!==t.key){ui.talkKey=t.key;ui.talkPage=0;}
  const i=Math.min(ui.talkPage,t.pages.length-1),[role,text]=t.pages[i],last=i===t.pages.length-1;
  box.replaceChildren();box.dataset.role=role;
  const who=el('div','talk-who');who.append(el('span',`portrait ${role}`,role==='mentor'?'선배':'나'),el('strong','',SPEAKER[role]||role));
  const p=el('p','talk-text');p.textContent=text;
  const row=el('div','talk-row');row.append(el('span','talk-count',`${i+1} / ${t.pages.length}`));
  if(i>0)row.append(button('이전',()=>{ui.talkPage=i-1;renderTalk();},'link'));
  if(!last)row.append(button('다음',()=>{ui.talkPage=i+1;renderTalk();},'primary',{id:'talk-next'}));
  else row.append(button('근무 시작',()=>send({type:'confirm_briefing'}),'primary',{id:'coach-start'}));
  box.append(who,p,row);
}

function render(){
  const state=store.state,nav=state.navigation,route=nav.route,viewKey=`${route}:${nav.nocView}:${nav.room}`;
  document.body.dataset.route=route;
  if(scene&&!openingActive&&lastViewKey!==viewKey){scene.setLocation(route,lastViewKey===null,nav.nocView,nav.room);lastViewKey=viewKey;}
  $('scene-eyebrow').textContent=LOCATIONS[route].subtitle;$('scene-title').textContent=routeTitle(route);$('scene-description').textContent=descriptions[route];
  $('scene-code').textContent=({world:'GLOBAL / KR-CENTRED',noc:'NOC / 01',campus:'ULSAN / 01',hall:'HALL / 01',room:`ROOM / ${nav.room}`})[route];$('scene-footnote').textContent=notes[route];
  $('hall-tools').hidden=route!=='hall';$('noc-tools').hidden=route!=='noc';$('map-legend').hidden=route!=='world';$('back').disabled=route==='world';
  document.querySelectorAll('#noc-tools [data-noc-view]').forEach(b=>b.classList.toggle('active',b.dataset.nocView===nav.nocView));
  $('breadcrumbs').replaceChildren(...breadcrumbs(route).map(x=>{const b=button(x.id==='room'?routeTitle('room'):x.title,()=>navigate(x.id,'crumb'));b.dataset.crumb=x.id;if(x.id===route)b.setAttribute('aria-current','location');return b;}));
  document.querySelectorAll('#places [data-route]').forEach(b=>b.classList.toggle('active',b.dataset.route===route||(route==='room'&&b.dataset.route==='campus')));
  $('action-feedback').textContent=state.notice;
  renderHeader();goalHead();requestSummary();contextCard();detailBody();renderStrip();renderRouteChain(state);renderWorkstation();renderTalk();coach.render();
}

// ---------- mode menu (title) ----------
const menu=(()=>{
  const box=$('menu');let shown=false;
  async function show(){
    shown=true;box.hidden=false;box.replaceChildren(el('div','menu-card',''));renderTalk();coach.render();
    const health=await api.health();setEngine(!!health.ok,health.message);
    const saves=health.ok?(await api.saves()).saves||[]:[];
    const card=el('div','menu-card');card.append(el('span','eyebrow','SERVER ROOM SURVIVAL · 3D'),el('h2','','모드를 고르세요'),el('p','menu-sub','튜토리얼은 선배와 함께하는 실습, 스토리 도전은 장 단위 본편, 자유·연습은 끝없는 근무입니다. 모든 규칙은 Python 게임 엔진이 계산합니다.'));
    if(!health.ok)card.append(el('p','menu-warn','Python 엔진에 연결할 수 없습니다. 터미널에서 npm run play (또는 python -m engine.server)를 실행한 뒤 이 창을 다시 여세요.'));
    const grid=el('div','mode-grid');
    for(const [mode,title,desc,icon]of [['tutorial','튜토리얼','선배가 실제 화면의 위치와 이유를 알려 줍니다. 요청 확인부터 장애 복구·결과 보고까지 직접 조작합니다.','🎓'],['story','스토리 도전','제1장 — 첫 근무. 세 고객의 업무를 정상 완료하면 장 클리어. 안내는 줄어듭니다.','📘'],['free','자유·연습','시간에 따라 요청이 계속 도착하고 네트워크 장애도 납니다. 끝이 없는 운영 연습입니다.','🛠']]){
      const c=el('section','mode-card-big');c.dataset.modeCard=mode;c.append(el('span','mode-icon',icon),el('h3','',title),el('p','',desc));
      c.append(button('새로 시작',async()=>{if(await newGame(mode))hide();},'primary',{'data-new':mode,...(health.ok?{}:{disabled:''})}));
      const mine=saves.filter(s=>s.kind===mode).slice(-3).reverse();
      for(const s of mine)c.append(button(`이어하기 · ${s.describe||s.id}${s.clock?` · ${s.clock}`:''}`,async()=>{if(await openGame(s.id))hide();},'link',{'data-resume':s.id}));
      grid.append(c);
    }
    card.append(grid);
    const foot=el('div','menu-foot');if(gameId)foot.append(button('현재 게임으로 돌아가기',hide,'',{id:'menu-close'}));foot.append(el('small','','3D 저장은 prototypes/3d-datacenter-001/saves/ 에만 새 파일로 만듭니다. 기존 Python 게임 저장은 열지 않습니다.'));card.append(foot);
    if(shown)box.replaceChildren(card);
  }
  function hide(){shown=false;box.hidden=true;render();}
  return {show,hide,hidden:()=>!shown};
})();

// ---------- opening (skippable, once per browser unless replayed). No game state is touched. ----------
function openingSeen(){try{return localStorage.getItem(OPENING_STORAGE_KEY)==='1';}catch{return false;}}
function startOpening(){
  if(openingActive||!scene)return;
  openingActive=true;openingStart=performance.now();openingLocation=null;document.body.classList.add('cinematic');$('opening').hidden=false;$('workstation').hidden=true;$('talk').hidden=true;coach.render();
  scene.playCinematic(OPENING,{onSegment:(i,k)=>{
    $('opening-step').textContent=`${String(i+1).padStart(2,'0')} / ${String(OPENING.length).padStart(2,'0')}`;$('opening-title').textContent=k.title;$('opening-sub').textContent=k.sub;
    if(openingLocation!==null&&openingLocation!==k.location){const f=$('opening-fade');f.classList.remove('cut');void f.offsetWidth;f.classList.add('cut');}openingLocation=k.location;
  },onDone:()=>finishOpening('completed')});
}
function finishOpening(how){
  if(!openingActive)return;scene.stopCinematic();openingActive=false;openingResult={how,seconds:+((performance.now()-openingStart)/1000).toFixed(2)};
  try{localStorage.setItem(OPENING_STORAGE_KEY,'1');}catch{/* private mode: replay simply stays available */}
  document.body.classList.remove('cinematic');$('opening').hidden=true;lastViewKey=null;store.setNocView('desk');
  const route=game()?store.state.navigation.route:'noc';store.navigate(route);render();
  if(!gameId)menu.show();
}
function openingProgress(){const c=scene.cinematicState();if(!c)return 0;return (OPENING.slice(0,c.index).reduce((s,k)=>s+k.duration,0)+c.t)/OPENING_SECONDS;}

const coach=createCoach({$,el,button,store,game,getScene:()=>scene,isBlocked:()=>openingActive||!menu.hidden(),send,toast});
const screens=createScreens({$,el,button,store,game,send,newGame,openGame,showMenu:()=>menu.show(),toast,ui,render});
store.subscribe(render);
try{
  scene=createScene($('viewport'),store.state.facility,id=>selectRack(id),{worldMode:true,getState:()=>store.state,reducedMotion:()=>reducedMotion,
    onPick:id=>{const [type,key]=id.split(':');if(type==='country')selectCountry(key);if(type==='facility')selectFacility(key,'pick');},
    onEnter:id=>{const [type,key]=id.split(':');if(type==='facility')enterFacility(key,'dblclick');}});
  const hash=location.hash.slice(1);if(hash&&!store.navigate(hash))history.replaceState(null,'','#noc');render();$('loading').hidden=true;
  (async()=>{
    const health=await api.health();setEngine(!!health.ok,health.message);
    let saved=null;try{saved=sessionStorage.getItem(GAME_KEY);}catch{}
    if(health.ok&&saved)await openGame(saved);
    if(!openingSeen())startOpening();else if(!gameId)menu.show();
    render();
  })();
  window.worldQA=Object.freeze({snapshot:()=>({state:store.snapshot(),game:store.snapshot().game,gameId,engine:{...engine},pending,ui:{tab:ui.tab,talkPage:ui.talkPage,menu:!menu.hidden()},renderer:scene.snapshot(),stats:{...stats},heap:performance.memory?{used:performance.memory.usedJSHeapSize,total:performance.memory.totalJSHeapSize}:null,visuals:scene.visuals(),worldMarkers:{SG:scene.worldMarker('SG'),JP:scene.worldMarker('JP'),US:scene.worldMarker('US'),KR:scene.worldMarker('KR')},cooling:scene.coolingVisual(),deskScreen:scene.deskScreenKey(),network:scene.networkVisual?.()??null,interior:scene.interiorVisual?.()??null,rack:scene.rackVisual?.()??null,opening:{active:openingActive,state:scene.cinematicState(),result:openingResult,seconds:OPENING_SECONDS},coach:coach.state(),screens:screens.state()}),
    actions:()=>actionLog.map(x=>({...x})),idle:()=>api.idle().then(()=>pending),projectAsset:id=>scene.projectAsset(id),projectWorld:id=>scene.projectWorld(id),projectPoint:p=>scene.projectPoint?.(p)??null,cameraState:()=>scene.cameraState()});
  function animate(now){const dt=Math.min((now-lastTime)/1000,.1),raw=now-lastTime;lastTime=now;
    if(!document.hidden){scene.pollGpuTimer();const timed=frame%30===0;if(timed)scene.beginGpuTimer();scene.animate(dt);if(timed)scene.endGpuTimer();const gpu=scene.pollGpuTimer();if(timed&&gpu!==null){gpuTimes.push(gpu);if(gpuTimes.length>60)gpuTimes.shift();}frameTimes.push(raw);if(frameTimes.length>300)frameTimes.shift();frame++;
      if(openingActive)$('opening-bar').style.width=`${(openingProgress()*100).toFixed(1)}%`;
      if(frame%6===0)coach.position();
      if(now-lastPerf>1000){const sorted=[...frameTimes].sort((a,b)=>a-b);stats={fps:1000/(frameTimes.reduce((s,x)=>s+x,0)/frameTimes.length),p95FrameMs:sorted[Math.floor(sorted.length*.95)],maxFrameMs:sorted.at(-1),gpuMs:gpuTimes.length?gpuTimes.reduce((s,x)=>s+x,0)/gpuTimes.length:null};const s=scene.snapshot(),heap=performance.memory?performance.memory.usedJSHeapSize/1048576:null;$('performance').textContent=`${stats.fps.toFixed(0)} FPS / ${s.width}×${s.height} / HIGH`;$('perf-panel').textContent=`${s.quality}\n${s.renderer}\nFPS ${stats.fps.toFixed(1)} / p95 ${stats.p95FrameMs.toFixed(2)} ms / GPU ${stats.gpuMs?.toFixed(2)??'미측정'} ms\nJS heap ${heap?.toFixed(1)??'미측정'} MiB / calls ${s.calls} / triangles ${s.triangles}\nGeometries ${s.geometries} / textures ${s.textures}\nGPU 전체 점유·VRAM은 외부 NVIDIA-SMI 별도 계측\n게임 상태는 Python 엔진이 계산합니다.`;lastPerf=now;}
    }requestAnimationFrame(animate);
  }document.addEventListener('visibilitychange',()=>{lastTime=performance.now();});requestAnimationFrame(animate);
}catch(e){$('loading').hidden=true;$('fatal').hidden=false;$('fatal').textContent=`3D 초기화 실패: ${e.message}`;console.error(e);}
