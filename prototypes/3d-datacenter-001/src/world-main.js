import './world.css';
import {createScene} from './scene.js';
import {createWorldStore,LOCATIONS,COUNTRIES,FACILITIES,FIXTURE,PHASES,breadcrumbs} from './world-store.js';
import {readings,totals,STATES} from './model.js';
import {nextDemoStep,demoBlocker} from './demo-actions.js';
import {COOLING,coolingView,powerView,upsView,networkView,hallView} from './facility-ops.js';
import {OPENING,OPENING_SECONDS,OPENING_STORAGE_KEY} from './opening.js';

document.querySelector('#app').innerHTML=`
<header class="topbar"><a class="brand" href="#noc"><span class="brand-icon">▤</span><span>SERVER ROOM<span class="brand-sub">SURVIVAL / ULSAN AIDC</span></span></a><div class="mode-badge">시연 모드 · 가상 요청 데이터</div><div class="top-right"><span>ULSAN · AIDC</span><button id="opening-replay">오프닝 다시 보기</button><button id="help-open">플레이 안내</button></div></header>
<div class="routebar"><button id="back" aria-label="상위 공간으로 복귀">상위 공간</button><nav id="breadcrumbs" aria-label="현재 위치"></nav><span class="route-note">탐색은 작업을 진행하지 않습니다</span></div>
<main>
<section id="viewport" aria-label="3D 세계 탐색"><div class="scene-heading"><div id="scene-eyebrow" class="eyebrow"></div><h1 id="scene-title"></h1><p id="scene-description"></p></div>
<nav id="places" aria-label="공간 이동"><button data-route="world">세계지도</button><button data-route="campus">울산 캠퍼스</button><button data-route="noc">관제동 · 내 자리</button><button data-route="hall">서버동 01</button></nav>
<div id="map-legend"><span><i></i>울산 AIDC (남구 황성동·용연 권역)</span><span><i class="sg"></i>싱가포르 요청</span><span>연결선·패킷은 교육용 가상 회선입니다</span></div>
<div id="noc-tools" hidden><button data-noc-view="desk">내 자리</button><button data-noc-view="overview">관제실 전체</button></div>
<div id="hall-tools" hidden><button data-camera="overview">서버동 전체</button><button data-camera="hall">랙 보기</button><button data-camera="aisle">통로</button><button id="focus-rack">선택 장비 보기</button><div class="layer-tools"><button data-layer="network" aria-pressed="true">네트워크</button><button data-layer="cooling" aria-pressed="true">냉각</button><button data-layer="power" aria-pressed="true">전력</button></div></div>
<section id="workstation" aria-label="내 모니터" hidden></section>
<div id="transit" hidden aria-live="polite"></div>
<div id="hover-label" hidden></div><div id="loading">3D 세계 준비 중…</div><div id="fatal" role="alert" hidden></div>
<div class="scene-caption"><b id="scene-code"></b><span id="scene-footnote"></span><span class="caption-line"></span><span>DESKTOP HIGH</span></div>
<div class="camera-help"><kbd>드래그</kbd> 회전 <kbd>우클릭</kbd> 이동 <kbd>휠</kbd> 확대 <kbd>W A S D</kbd> 이동 <kbd>F</kbd> 초점</div></section>
<aside id="panel" aria-label="현재 공간과 고객 요청"><div class="panel-label"><span id="panel-eyebrow">OPERATIONS</span><span id="request-counter">1 REQUEST</span></div><div id="context-panel"></div>
<section class="request-card"><div class="request-card-top"><span>SG / SINGAPORE</span><span id="phase-chip" class="chip"></span></div><h2>싱가포르 고객 요청</h2><div class="identity"><strong data-request-id></strong><span data-customer-id></span></div><p class="workload" id="request-workload"></p><div class="original-label">원래 요청 조건 · 시연 전용</div><div class="terms"><div><strong data-term="gpu"></strong><span>가상 GPU</span></div><div><strong><b data-term="powerKW"></b><small>kW</small></strong><span>가상 전력</span></div><div><strong><b data-term="networkGbps"></b><small>Gbps</small></strong><span>필요 대역폭</span></div></div><p class="terms-note" id="terms-note"></p><div class="assigned"><span>처리 위치</span><strong id="request-location"></strong></div>
<div class="progress-label"><span id="progress-text">접수 전</span><strong id="progress-value">0%</strong></div><div class="progress-track"><i id="progress-bar"></i></div>
<div class="step-note" id="step-note"></div><div id="request-actions"></div><div id="action-feedback" role="status" aria-live="polite"></div></section>
<section id="asset-panel" hidden></section><section class="mini-status"><div><span>링크 상태</span><strong id="link-status">정상</strong></div><div><span>보조 냉각</span><strong id="cooling-status"></strong></div><div><span>가상 GPU 온라인</span><strong id="gpu-online">192 / 192</strong></div><div><span>시연 진행</span><strong id="step-count">0회</strong></div></section><p class="panel-note">가상 요청을 사용하는 독립 시연입니다. 이동·대기·카메라 조작으로 작업이 진행되지 않습니다. Python 게임·SQLite와 연결되지 않았습니다.</p></aside>
<section class="mission-strip"><div class="mission-title"><span class="eyebrow">MY SHIFT / ONE REQUEST</span><strong id="objective"></strong><p id="objective-detail"></p></div><div class="flow"><span data-step="world">세계지도</span><i></i><span data-step="campus">울산 캠퍼스</span><i></i><span data-step="noc">관제동 · 내 자리</span><i></i><span data-step="hall">서버동 01</span></div><div class="mission-id"><strong data-request-id></strong><span>가상 고객 요청 1건</span></div></section>
</main><footer><span><b>WORLD / PHASE 3.1</b> · 기존 엔진 미연결</span><span id="performance">성능 측정 중…</span><button id="perf-toggle" aria-expanded="false">성능 상세</button><a href="./lab.html">기존 3D 실험실</a></footer><div id="perf-panel" hidden></div>
<div id="opening" hidden><div id="opening-fade"></div><div class="opening-top"><span class="mode-badge">시연 모드 · 가상 데이터</span><button id="opening-skip">건너뛰기 · Esc</button></div><div class="opening-caption"><span id="opening-step"></span><h2 id="opening-title"></h2><p id="opening-sub"></p><div class="opening-progress"><i id="opening-bar"></i></div></div></div>
<dialog id="help"><button id="help-close" aria-label="안내 닫기">닫기</button><span class="eyebrow">시연 플레이 안내</span><h2>울산 AIDC에 출근해 내 자리에서 한 요청을 처리합니다.</h2><ol><li>관제동 내 자리의 모니터에서 싱가포르 요청을 확인합니다. 필요하면 세계지도에서 고객 위치와 가상 회선을 봅니다.</li><li>내 모니터에서 배정 검토(서버동 01 · 랙 D-06)를 보고 접수합니다.</li><li>연결 통로를 지나 별도 건물인 서버동 01로 이동해 랙 D-06에서 작업을 시작합니다.</li><li>장애·복구·사후 확인을 진행하고, 네트워크동에서 장애 원인을 조회해 봅니다.</li><li>내 자리로 돌아와 결과를 확인합니다.</li><li>캠퍼스의 각 건물(냉각·전력·UPS·네트워크)을 클릭해 상태를 보고 조작해 보세요. 보조 냉각 켜기·끄기·경고는 교육용 시연입니다.</li></ol><p>모든 진행은 명시적 클릭으로만 일어납니다. 새로고침하면 이 시연만 초기화됩니다. 오프닝은 처음 한 번만 자동 재생되며 상단에서 다시 볼 수 있습니다.</p><p>3D 화면에 포커스를 둔 뒤 W/A/S/D로 이동, Q/E로 높이 조절, F로 초점을 맞출 수 있습니다. 카메라 충돌 판정은 없습니다.</p></dialog>`;

const $=id=>document.getElementById(id),store=createWorldStore();
let scene,lastViewKey=null,resultScrolledFor=null,frame=0,lastTime=performance.now(),lastPerf=0,perfOpen=false;
let openingActive=false,openingStart=0,openingResult=null,openingLocation=null,transitTimer=0;
const frameTimes=[],gpuTimes=[];let stats={fps:0,p95FrameMs:0,gpuMs:null};
const descriptions={world:'세계의 고객, 그리고 울산의 하나의 데이터센터.',campus:'관제동·서버동·냉각·전력·네트워크. 건물을 눌러 상태를 확인하세요.',noc:'내 자리에서 요청을 받고, 시설을 감시하고, 결과를 확인합니다.',hall:'현장 공간. 요청 랙을 직접 확인하고 작업합니다.'};
const notes={world:'Made with Natural Earth / 연결 경로는 가상',noc:'기존 관제실 재사용 / 내 자리·모니터는 동일 상태',campus:'자체 제작 캠퍼스·산단 재구성 / 실제 부지·조감도 아님',hall:'기존 24랙·장비·가상 센서 재사용 / 관제동과 별도 건물'};
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
function button(text,handler,primary=false,id){const b=el('button',primary?'primary':'',text);if(id)b.id=id;b.addEventListener('click',handler);return b;}
function navigate(route){
  const from=store.state.navigation.route;
  if(store.navigate(route)){if(location.hash!==`#${route}`)history.replaceState(null,'',`#${route}`);if((from==='noc'&&route==='hall')||(from==='hall'&&route==='noc'))showTransit(from,route);}
}
function showTransit(from,to){
  const t=$('transit');t.replaceChildren();
  const path=el('div','transit-path');for(const [k,label]of [[from,from==='noc'?'관제동':'서버동 01'],['link','연결 통로'],[to,to==='noc'?'관제동 · 내 자리':'서버동 01']]){path.append(el('span',k==='link'?'link':'',label));}
  t.append(el('span','eyebrow','이동 · 별도 건물'),path,el('p','',to==='hall'?'현장 공간: 랙을 직접 확인하고 작업합니다.':'운영 공간: 내 모니터에서 요청과 시설을 관리합니다.'));
  t.hidden=false;clearTimeout(transitTimer);transitTimer=setTimeout(()=>{t.hidden=true;},1400);
}
document.querySelectorAll('[data-route]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.route)));
document.querySelectorAll('[data-noc-view]').forEach(b=>b.addEventListener('click',()=>store.setNocView(b.dataset.nocView)));
$('back').addEventListener('click',()=>{const p=LOCATIONS[store.state.navigation.route].parent;if(p)navigate(p);});
window.addEventListener('hashchange',()=>{const route=location.hash.slice(1);if(!store.navigate(route)){history.replaceState(null,'','#noc');store.navigate('noc');}});
$('help-open').addEventListener('click',()=>$('help').showModal());$('help-close').addEventListener('click',()=>$('help').close());
$('perf-toggle').addEventListener('click',()=>{perfOpen=!perfOpen;$('perf-panel').hidden=!perfOpen;$('perf-toggle').setAttribute('aria-expanded',String(perfOpen));});
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>scene.view(b.dataset.camera)));
$('focus-rack').addEventListener('click',()=>scene.focus());
document.querySelectorAll('[data-layer]').forEach(b=>b.addEventListener('click',()=>{const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));scene.setLayer(b.dataset.layer,on);}));
$('opening-skip').addEventListener('click',()=>finishOpening('skipped'));$('opening-replay').addEventListener('click',()=>startOpening());
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&openingActive){e.preventDefault();finishOpening('skipped');}});

// ---------- shared widgets (all read the single store) ----------
function coolingBadge(v,compact=false){
  const b=el('div',`cool-badge${compact?' compact':''}`);b.dataset.mode=v.mode;b.setAttribute('role','status');
  const leds=el('span','cool-leds');for(let i=0;i<3;i++)leds.append(el('i'));
  const text=el('span','cool-text');text.append(el('strong','cool-label',`보조 냉각 ${v.label}`));if(!compact)text.append(el('small','',v.summary));
  b.append(el('span','cool-icon',v.icon),leds,text);return b;
}
function sparkline(values){
  const min=Math.min(...values)-.2,max=Math.max(...values)+.2,w=280,h=56;
  const pts=values.map((y,i)=>`${(i/(values.length-1)*w).toFixed(1)},${(h-(y-min)/(max-min)*h).toFixed(1)}`).join(' ');
  const wrap=el('div','spark');wrap.innerHTML=`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
  wrap.append(el('span','',`${values[0].toFixed(1)} → ${values.at(-1).toFixed(1)} °C`));return wrap;
}
function readingsGrid(rows){const g=el('dl','ops-readings');for(const [k,v]of rows)g.append(el('dt','',k),el('dd','',v));return g;}
function checkResult(c){if(!c)return null;const box=el('div','ops-result');box.append(el('strong','',c.title),el('p','',c.detail),el('small','',`조회 시점 요청 단계: ${PHASES[c.phase]} · 기록 #${c.seq}`));return box;}
function opsButton(action,label,primary=false){const b=button(label,()=>store.ops(action),primary);b.dataset.ops=action;return b;}
const COOLING_LABELS={'cooling-off':'보조 냉각 끄기','cooling-on':'보조 냉각 켜기','cooling-warn':'경고 시나리오 · 유량 저하','cooling-reset':'유량 점검 완료 · 재가동'};

function facilityPanel(id,state){
  const root=el('div','facility-panel');root.dataset.panel=id;
  if(id==='COOLING'){
    const v=coolingView(state);root.append(coolingBadge(v));
    const actions=el('div','ops-actions');for(const a of v.actions)actions.append(opsButton(a,COOLING_LABELS[a],a==='cooling-on'||a==='cooling-reset'));root.append(actions);
    root.append(readingsGrid([['냉각수 유량',`${v.flow} L/min`],['공급 / 환수',`${v.supply??'—'} / ${v.ret??'—'} °C`],['팬 속도',`${v.fan}%`],['서버동 평균 유입',`${v.hallInlet} °C`],['보조 냉각 전력',`${v.loadKW} kW`]]));
    root.append(el('div','ops-sub','서버동 01 평균 유입 온도 추세 · 조작 기준(실시간 아님)'),sparkline(v.trend));
    if(v.mode==='warn')root.append(checkResult({title:'진단: 냉각수 유량 저하',detail:`유량 ${v.flow} L/min (정상 ${COOLING.on.flow}) · 공급 ${v.supply} °C ↑ · 조치: 유량 점검 후 재가동`,phase:state.request.phase,seq:state.ops.log.length}));
    root.append(el('p','ops-note','교육용 보조 냉각 계통(AUX-C1) 시연입니다. 주 냉각 계통은 계속 운전한다고 가정하며, 물리 열모델이나 Python 게임 판정은 없습니다. 실제 운영에서 직원이 냉각을 임의로 끄는 절차를 뜻하지 않습니다.'));
  }else if(id==='POWER'){
    const p=powerView(state);root.append(readingsGrid([['수전',p.feeds],['IT 부하',`${p.itLoadKW} kW`],['보조 냉각 부하',`${p.coolingLoadKW} kW`],['합계 / 가상 용량',`${p.totalKW} / ${p.capacityKW} kW`]]));
    root.append(opsButton('power-check','전력 계통 점검 실행'));const r=checkResult(state.ops.checks.power);if(r)root.append(r);
  }else if(id==='UPS'){
    const u=upsView(state);root.append(readingsGrid([['배터리',`${u.battery}%`],['운전 상태',u.mode],['예비 시간',u.runtime]]));
    root.append(opsButton('ups-test','UPS 자가진단 실행'));const r=checkResult(state.ops.checks.ups);if(r)root.append(r);
  }else if(id==='NETWORK'){
    const n=networkView(state),table=el('div','link-table');
    table.append(el('div','link-row head'));table.lastChild.append(el('span','','회선'),el('span','','지연(가상)'),el('span','','상태'));
    for(const l of n.links){const row=el('div',`link-row${l.status==='정상'?'':' bad'}`);row.dataset.link=l.id;row.append(el('span','',`${l.name}${l.active?' · 요청 중':''}`),el('span','',`${l.latencyMs} ms`),el('span','',l.status));table.append(row);}
    root.append(readingsGrid([['서버동 01 업링크',n.uplink]]),table,opsButton('network-lookup','장애 원인 조회'));
    const c=state.ops.checks.network,r=checkResult(c);if(r){root.append(r);if(c.target==='hall')root.append(button('서버동 01로 이동',()=>navigate('hall'),false,'network-to-hall'));}
  }else if(id==='HALL-01'){
    const h=hallView(state);root.append(readingsGrid([['랙 / 가상 GPU 온라인',`${h.racks} / ${h.gpuOnline}`],['요청 랙',`${h.requestRack} · ${STATES[h.requestRackState]}`],['활성 장애',`${h.faults}건`],['평균 유입 온도',`${h.inlet} °C`]]));
  }else if(id==='NOC'){
    root.append(readingsGrid([['운영석','6석 · 근무 5명 (가상)'],['내 자리','2F 운영석 03'],['내 요청함',`SG · 1건 · ${PHASES[state.request.phase]}`]]));
    root.append(button('내 자리로 가기',()=>{store.setNocView('desk');navigate('noc');},true,'go-desk'));
  }
  return root;
}

function contextPanel(){
  const state=store.state,route=state.navigation.route,root=$('context-panel');root.replaceChildren();
  if(route==='world'){
    root.append(el('h2','',COUNTRIES[state.navigation.country].name));
    const countries=el('div','countries');
    for(const [id,c]of Object.entries(COUNTRIES)){const b=button(id,()=>store.selectCountry(id),id===state.navigation.country);b.dataset.country=id;b.setAttribute('aria-label',`${c.name} 선택`);countries.append(b);}root.append(countries);
    root.append(el('p','',state.navigation.country==='SG'?'새 고객 요청 1건이 울산 AIDC로 가상 회선을 따라 들어왔습니다.':state.navigation.country==='KR'?'울산 남구 황성동·용연 권역의 미래 가상 AIDC입니다. 지도 정밀도는 설명용입니다.':'이 국가에는 활성 요청이 없습니다. 이번 시연은 싱가포르 한 건만 제공합니다.'));
    root.append(button('관제동 · 내 자리로',()=>{store.setNocView('desk');navigate('noc');},false,'enter-noc'));
    root.append(button('선택 거점 가까이 보기',()=>scene.focusWorld(state.navigation.country),false,'focus-country'));
  }else if(route==='noc'){
    root.append(el('h2','','관제동 · 내 자리'),el('p','','원격 운영 공간입니다. 요청 접수·시설 감시·결과 확인은 내 모니터에서 합니다.'));
    const row=el('div','inbox-row');row.append(el('span','','요청함'),el('strong','',`SG · 1건 · ${PHASES[state.request.phase]}`));root.append(row);
    root.append(button(state.navigation.nocView==='desk'?'관제실 전체 보기':'내 자리로 돌아가기',()=>store.setNocView(state.navigation.nocView==='desk'?'overview':'desk'),false,'toggle-noc-view'));
    root.append(button('캠퍼스 시설 살펴보기',()=>navigate('campus'),false,'enter-campus'));
  }else if(route==='campus'){
    const list=el('div','facility-list');
    for(const [id,f]of Object.entries(FACILITIES)){const b=button(f.name,()=>{store.selectFacility(id);scene.focusWorld(id);},id===state.navigation.facility);b.dataset.facility=id;list.append(b);}root.append(list);
    const f=FACILITIES[state.navigation.facility];root.append(el('h2','',f.name),el('p','',f.description),facilityPanel(state.navigation.facility,state));
    root.append(button('선택 시설 가까이 보기',()=>scene.focusWorld(state.navigation.facility),false,'focus-facility'));
    if(f.target)root.append(button(f.target==='hall'?'서버동 01 진입':'관제동 · 내 자리로',()=>{if(f.target==='noc')store.setNocView('desk');navigate(f.target);},false,'enter-building'));
  }else{
    root.append(el('h2','','서버동 01'),el('p','','관제동과 연결 통로로 이어진 별도 건물입니다. 요청 랙 D-06을 3D에서 클릭하거나 목록에서 선택하세요.'));
    const label=el('label','','장비 선택'),select=el('select');select.id='equipment-select';select.setAttribute('aria-label','장비 선택');
    for(const a of state.facility.assets){const o=el('option','',a.name);o.value=a.id;select.append(o);}select.value=state.facility.selectedId;select.addEventListener('change',()=>store.selectRack(select.value));label.append(select);root.append(label);
    root.append(button('요청 랙 D-06 찾기',()=>{store.selectRack(FIXTURE.rackId);scene.focus();},false,'locate-rack'),coolingBadge(coolingView(state),true));
  }
}

// ---------- My monitor: the work entry point at my desk ----------
function renderWorkstation(){
  const state=store.state,r=state.request,step=nextDemoStep(state),ws=$('workstation');
  ws.hidden=!(state.navigation.route==='noc'&&state.navigation.nocView==='desk')||openingActive;if(ws.hidden)return;ws.replaceChildren();
  const bar=el('div','ws-titlebar');bar.append(el('span','','SRS-OPS · 운영석 03 · 내 모니터'),el('span','ws-shift','근무 중 · 주간 A조 (가상)'));
  const body=el('div','ws-body');
  // Me + what to do now
  const me=el('section','ws-me');me.append(el('div','ws-role','운영 엔지니어 (신입) · 울산 AIDC 관제동 2F'),el('div','ws-label','지금 할 일'));
  const todo=el('strong','ws-todo',step?step.objective:'오늘의 요청 처리 완료');todo.id='ws-todo';me.append(todo,el('p','ws-note',step?step.note:'결과를 확인했습니다. 캠퍼스 시설을 살펴보거나 오프닝을 다시 볼 수 있습니다.'));
  const actions=el('div','ws-actions');
  if(step&&(step.routes||[step.route]).includes('noc')){const b=button(step.label,()=>store.act(step.id),true);b.dataset.wsAction=step.id;b.disabled=!!demoBlocker(state,step.id);actions.append(b);}
  else if(step&&step.route==='hall'){const b=button('서버동 01로 이동 · 연결 통로',()=>navigate('hall'),true);b.dataset.wsAction='go-hall';actions.append(b);}
  me.append(actions);
  // Inbox and request detail (single source: store.state.request)
  const inbox=el('section','ws-inbox');inbox.append(el('div','ws-label','고객 요청함 · 1건'));
  const row=el('div','ws-request');row.dataset.phase=r.phase;row.append(el('strong','',r.id),el('span','',`${r.customerName} · ${r.customerId}`),el('span','chip',PHASES[r.phase]));row.lastChild.dataset.phase=r.phase;inbox.append(row);
  inbox.append(readingsGrid([['작업',r.workload],['원래 조건',`GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps`],['모드 / 기한',`${r.terms.mode} · ${r.terms.deadline}`],['배정 검토',`${r.buildingId} · 랙 ${r.rackId} · 가상 GPU 8 여유 ✓`],['진행',`${r.progress}%`]]));
  const worldBtn=button('세계지도에서 고객·가상 회선 보기',()=>{store.selectCountry('SG');navigate('world');});worldBtn.dataset.wsAction='open-world';inbox.append(worldBtn);
  if(!step)inbox.append(resultCard(r,'ws-result'));
  // Facility watch: every tile opens the facility panel on the campus map
  const watch=el('section','ws-watch');watch.append(el('div','ws-label','시설 감시'));
  const h=hallView(state),n=networkView(state),p=powerView(state),c=coolingView(state);
  const tile=(id,title,value,bad)=>{const t=button('',()=>{store.selectFacility(id);navigate('campus');scene.focusWorld(id);});t.className=`ws-tile${bad?' bad':''}`;t.dataset.wsTile=id;t.append(el('span','',title),el('strong','',value));return t;};
  watch.append(tile('HALL-01','서버동 01',`GPU ${h.gpuOnline}/192 · 장애 ${h.faults}`,h.faults>0),tile('NETWORK','네트워크 업링크',n.uplink,n.down));
  const coolTile=tile('COOLING','',``,c.mode==='warn');coolTile.replaceChildren(coolingBadge(c,true));watch.append(coolTile);
  watch.append(tile('POWER','전력 · UPS',`${p.totalKW} kW · UPS 대기`,false));
  const alerts=el('ul','ws-alerts');for(const e of state.facility.events.slice(0,2))alerts.append(el('li','',e.text));for(const l of state.ops.log.slice(-2).reverse())alerts.append(el('li','',l.text));watch.append(alerts);
  body.append(me,inbox,watch);ws.append(bar,body);
}

function render(){
  const state=store.state,route=state.navigation.route,r=state.request,viewKey=`${route}:${state.navigation.nocView}`;
  if(scene&&!openingActive&&lastViewKey!==viewKey){scene.setLocation(route,lastViewKey===null,state.navigation.nocView);lastViewKey=viewKey;}
  $('scene-eyebrow').textContent=LOCATIONS[route].subtitle;$('scene-title').textContent=LOCATIONS[route].title;$('scene-description').textContent=descriptions[route];
  $('scene-code').textContent=({world:'GLOBAL / 01',noc:'NOC / 01',campus:'ULSAN / 01',hall:'HALL / 01'})[route];$('scene-footnote').textContent=notes[route];
  $('hall-tools').hidden=route!=='hall';$('noc-tools').hidden=route!=='noc';$('map-legend').hidden=route!=='world';$('back').disabled=route==='world';
  document.querySelectorAll('[data-noc-view]').forEach(b=>b.classList.toggle('active',b.dataset.nocView===state.navigation.nocView));
  $('breadcrumbs').replaceChildren(...breadcrumbs(route).map(x=>{const b=button(x.title,()=>navigate(x.id));b.dataset.crumb=x.id;if(x.id===route)b.setAttribute('aria-current','location');return b;}));
  document.querySelectorAll('[data-route],[data-step]').forEach(b=>b.classList.toggle('active',(b.dataset.route||b.dataset.step)===route));
  document.querySelectorAll('[data-request-id]').forEach(x=>x.textContent=r.id);document.querySelectorAll('[data-customer-id]').forEach(x=>x.textContent=r.customerId);
  document.querySelectorAll('[data-term]').forEach(x=>x.textContent=r.terms[x.dataset.term]);
  $('request-workload').textContent=r.workload;$('terms-note').textContent=`${r.terms.mode} 모드 · ${r.terms.deadline}`;$('request-location').textContent=`${r.facilityId} / ${r.buildingId} / ${r.rackId}`;
  $('phase-chip').textContent=PHASES[r.phase];$('phase-chip').dataset.phase=r.phase;
  $('progress-value').textContent=`${r.progress}%`;$('progress-bar').style.width=`${r.progress}%`;$('progress-text').textContent=PHASES[r.phase];$('step-count').textContent=`${r.steps}회`;
  $('link-status').textContent=networkView(state).down?'업링크 단절':r.phase==='awaiting'?'복구 / 확인 대기':'정상';$('link-status').dataset.bad=networkView(state).down;
  const cv=coolingView(state);$('cooling-status').textContent=`${cv.icon} ${cv.label}`;$('cooling-status').dataset.mode=cv.mode;
  $('gpu-online').textContent=`${totals(state.facility).gpu} / 192`;
  contextPanel();renderRequestActions();renderWorkstation();$('action-feedback').textContent=state.notice;
  const a=state.facility.assets.find(a=>a.id===state.facility.selectedId),v=readings(a),delta=COOLING[state.ops.cooling.mode].inletDelta;$('asset-panel').hidden=route!=='hall';
  $('asset-panel').innerHTML=`<div class="panel-label">ASSET INSPECTOR</div><h3>${a.name}</h3><div class="asset-chip" data-state="${a.state}">${STATES[a.state]}</div><p>${a.id===r.rackId?`관련 요청 ${r.id} / ${PHASES[r.phase]}`:'이 장비에는 이번 시연 요청이 배정되지 않았습니다.'}</p><div class="asset-readings"><div><span>GPU 부하</span><strong>${v.gpu}%</strong></div><div><span>소비 전력</span><strong>${v.power.toFixed(1)} kW</strong></div><div><span>유입 온도${delta?` (보조 냉각 ${COOLING[state.ops.cooling.mode].label} +${delta})`:''}</span><strong>${(v.temp+delta).toFixed(1)} °C</strong></div><div><span>네트워크</span><strong>${v.network} Gbps</strong></div></div>`;
}
// Result summary is derived only from the recorded request history; nothing is scored or saved.
function resultCard(r,id='demo-result'){
  const card=el('section','result-box');card.id=id;card.append(el('div','result-title','처리 결과 · 가상 시연'));
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
    if(resultScrolledFor!==route){resultScrolledFor=route;requestAnimationFrame(()=>card.scrollIntoView({block:'nearest'}));}
    return;
  }
  $('step-note').textContent=step.note;$('objective').textContent=step.objective;$('objective-detail').textContent=step.note;
  if(!(step.routes||[step.route]).includes(route)){
    const next=step.route,label=next==='noc'?'관제동 · 내 자리로':next==='hall'?'서버동 01로 이동':'세계지도에서 확인';
    root.append(button(label,()=>{if(next==='noc')store.setNocView('desk');navigate(next);},true,'continue-demo'));
  }else{
    if(route==='world'&&state.navigation.country!=='SG')root.append(button('싱가포르 고객 선택',()=>store.selectCountry('SG'),true,'select-sg'));
    if(route==='hall'&&state.facility.selectedId!==state.request.rackId)root.append(button('요청 랙 D-06 선택',()=>{store.selectRack(FIXTURE.rackId);scene.focus();},true,'select-request-rack'));
    const b=button(step.label,()=>store.act(step.id),true,'demo-action');b.dataset.action=step.id;b.disabled=!!demoBlocker(state,step.id);root.append(b);
  }
  if(['running','fault','repairing','awaiting','recovered'].includes(state.request.phase)&&route==='hall')root.append(button('내 자리에서 같은 상태 확인',()=>{store.setNocView('desk');navigate('noc');},false,'inspect-noc'));
}

// ---------- Opening (skippable, once per browser unless replayed) ----------
function openingSeen(){try{return localStorage.getItem(OPENING_STORAGE_KEY)==='1';}catch{return false;}}
function startOpening(){
  if(openingActive||!scene)return;
  openingActive=true;openingStart=performance.now();openingLocation=null;document.body.classList.add('cinematic');$('opening').hidden=false;$('workstation').hidden=true;
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
  scene=createScene($('viewport'),store.state.facility,id=>store.selectRack(id),{worldMode:true,getState:()=>store.state,onPick:id=>{const [type,key]=id.split(':');if(type==='country')store.selectCountry(key);if(type==='facility'){store.selectFacility(key);scene.focusWorld(key);}}});
  const hash=location.hash.slice(1);if(hash&&!store.navigate(hash))history.replaceState(null,'','#noc');render();$('loading').hidden=true;
  if(!openingSeen())startOpening();
  window.worldQA=Object.freeze({snapshot:()=>({state:store.snapshot(),domain:store.domainSnapshot(),renderer:scene.snapshot(),stats:{...stats},heap:performance.memory?{used:performance.memory.usedJSHeapSize,total:performance.memory.totalJSHeapSize}:null,visuals:scene.visuals(),worldMarkers:{SG:scene.worldMarker('SG'),JP:scene.worldMarker('JP')},cooling:scene.coolingVisual(),deskScreen:scene.deskScreenKey(),opening:{active:openingActive,state:scene.cinematicState(),result:openingResult,seconds:OPENING_SECONDS}}),projectAsset:id=>scene.projectAsset(id),projectWorld:id=>scene.projectWorld(id)});
  function animate(now){const dt=Math.min((now-lastTime)/1000,.1),raw=now-lastTime;lastTime=now;
    if(!document.hidden){scene.pollGpuTimer();const timed=frame%30===0;if(timed)scene.beginGpuTimer();scene.animate(dt);if(timed)scene.endGpuTimer();const gpu=scene.pollGpuTimer();if(timed&&gpu!==null){gpuTimes.push(gpu);if(gpuTimes.length>60)gpuTimes.shift();}frameTimes.push(raw);if(frameTimes.length>300)frameTimes.shift();frame++;
      if(openingActive)$('opening-bar').style.width=`${(openingProgress()*100).toFixed(1)}%`;
      if(now-lastPerf>1000){const sorted=[...frameTimes].sort((a,b)=>a-b);stats={fps:1000/(frameTimes.reduce((s,x)=>s+x,0)/frameTimes.length),p95FrameMs:sorted[Math.floor(sorted.length*.95)],gpuMs:gpuTimes.length?gpuTimes.reduce((s,x)=>s+x,0)/gpuTimes.length:null};const s=scene.snapshot(),heap=performance.memory?performance.memory.usedJSHeapSize/1048576:null;$('performance').textContent=`${stats.fps.toFixed(0)} FPS / ${s.width}×${s.height} / HIGH`;$('perf-panel').textContent=`${s.quality}\n${s.renderer}\nFPS ${stats.fps.toFixed(1)} / p95 ${stats.p95FrameMs.toFixed(2)} ms / GPU ${stats.gpuMs?.toFixed(2)??'미측정'} ms\nJS heap ${heap?.toFixed(1)??'미측정'} MiB / calls ${s.calls} / triangles ${s.triangles}\nGeometries ${s.geometries} / textures ${s.textures}\nGPU 전체 점유·VRAM은 외부 NVIDIA-SMI 별도 계측\n시연 상태는 버튼 클릭으로만 변경됩니다.`;lastPerf=now;}
    }requestAnimationFrame(animate);
  }document.addEventListener('visibilitychange',()=>{lastTime=performance.now();});requestAnimationFrame(animate);
}catch(e){$('loading').hidden=true;$('fatal').hidden=false;$('fatal').textContent=`3D 초기화 실패: ${e.message}`;console.error(e);}
