// Issue #8 (Phase 7) browser QA: incident-response shifts A -> B -> C played through the real 3D UI in Chrome
// (Playwright CDP mouse / keyboard / select on the menu, talk box, monitor tabs, incident card, facility interiors,
// 3D racks, time buttons). Isolated stack: Python engine on a temporary save folder + its own Vite port and cache.
// The API and the save files are only READ (window.worldQA, node:sqlite read-only, file hashes); nothing is set directly.
// Preconditions played through the real UI as well: story chapters 1 -> 5 (graduation) and global shifts 1 -> 3.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawn,execFileSync} from 'node:child_process';
import {DatabaseSync} from 'node:sqlite';
import {startStack,settle,CHROME,tempSaveDir,python,ROOT} from './qa-lib.mjs';
import * as P6 from './phase6-ui.mjs';
import * as U from './phase7-ui.mjs';
import * as story5 from './campaign-flows.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)??'../../docs/3d-world-expansion/qa/phase7');await mkdir(out,{recursive:true});
const only=process.argv.find(x=>x.startsWith('--only='))?.slice(7);
const report={issue:8,mode:'Chrome headed / Playwright CDP / isolated contexts / isolated engine+saves (temporary)',checks:[],errors:[],consoleErrors:[],crashes:[],screenshots:[],
  shifts:[],incidents:[],wrong:[],resumes:[],engineTruth:[],consistency:[],performance:[],resources:[],layout:[],startedAt:new Date().toISOString()};
let browser,stack,currentPage=null;
async function check(name,fn){if(only&&!name.includes(only))return;const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){
  const shotName=`fail-${report.checks.length+1}.png`;let state=null;try{await currentPage?.screenshot({path:resolve(out,shotName)});const s=await currentPage.evaluate(()=>worldQA.snapshot());state={screen:s.screens.open,clock:s.game?.clock?.label,route:s.state.navigation.route,incidents:s.game?.incident?.records?.map(r=>[r.id,r.state]),actions:await currentPage.evaluate(()=>worldQA.actions().slice(-8))};}catch{}
  report.checks.push({name,pass:false,error:e.stack?.split('\n').slice(0,5).join(' | '),failShot:shotName,state});console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`);}}
async function open({width=1920,height=1080,dpr=1,reducedMotion=false}={}){
  const ctx=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:reducedMotion?'reduce':'no-preference'});
  await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');}catch{}});
  const page=await ctx.newPage();currentPage=page;page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  page.on('crash',()=>report.crashes.push(new Date().toISOString()));page.on('dialog',d=>d.accept());
  await page.goto(stack.url,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1200);
  const shot=async name=>{await page.screenshot({path:resolve(out,name)});report.screenshots.push(name);};
  return {ctx,page,shot};
}
const sha=async p=>createHash('sha256').update(await readFile(p)).digest('hex');
const savePath=id=>join(stack.saveDir,`${id}.db`);
// The engine's own incident records of a save, read-only (single source of truth for the result screen).
function engineIncidents(id){const db=new DatabaseSync(savePath(id),{readOnly:true});try{
  const sim=JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);
  const reqs=Object.fromEntries(db.prepare('SELECT id,status FROM customer_requests').all().map(r=>[r.id,r.status]));
  return {sim,reqs};}finally{db.close();}}
// Game records of a save (read-only): every table plus the payload without the display-only 'result seen' flag.
function records(id){const db=new DatabaseSync(savePath(id),{readOnly:true});try{const payload=JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);
  if(payload.global)delete payload.global.seen;
  const tables=Object.fromEntries(db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name<>'simulation_state'").all().map(t=>[t.name,db.prepare(`SELECT * FROM ${t.name}`).all()]));
  return JSON.stringify({payload,tables});}finally{db.close();}}
async function perf(page,label){await page.waitForTimeout(1300);const s=await U.S(page);report.performance.push({label,fps:+s.stats.fps.toFixed(1),p95:+(s.stats.p95FrameMs??0).toFixed(2),heapMiB:s.heap?+(s.heap.used/1048576).toFixed(1):null,geometries:s.renderer.geometries,textures:s.renderer.textures,calls:s.renderer.calls});}
async function resumeAfterRestart(ctx,page,label){
  const before=await U.G(page),id=before.id;await ctx.close();
  await stack.restartEngine();
  const {ctx:ctx2,page:page2,shot}=await open();
  if(!(await page2.evaluate(()=>!document.querySelector('#menu').hidden)))await U.click(page2,'#menu-open');
  await page2.waitForSelector(`[data-resume="${id}"]`);await U.click(page2,`[data-resume="${id}"]`);await page2.waitForTimeout(800);
  const after=await U.G(page2);
  for(const k of ['clock','requests','servers','datacenter','global','incident'])assert.deepEqual(after[k],before[k],`${label}: ${k} kept after engine restart`);
  report.resumes.push({label,id,clock:after.clock.label,incidents:after.incident.records.map(r=>[r.id,r.state,r.evidence.length,r.actions.length])});
  return {ctx:ctx2,page:page2,shot};
}

// ---------------- Phase 6 global shifts (same decisions as the Phase 6 QA, real clicks) ----------------
const ORDER={
  1:{0:[['start','KR-SEL','performance'],['start','US-SFO','performance']],30:[['start','DE-FRA','performance']],40:[['wait','US-SEA']],60:[['start','JP-OSA','performance']],70:[['start','US-SEA','performance']]},
  2:{0:[['propose','US-IAD',false],['start','US-IAD','performance'],['propose','IN-BLR',true],['start','IN-BLR','economy']],20:[['wait','KR-PUS']],50:[['wait','GB-LON']],
     80:[['start','GB-LON','performance'],['start','NL-AMS','performance']],90:[['wait','TW-TPE']],100:[['start','TW-TPE','performance']],120:[['start','KR-PUS','performance']]},
  3:{0:[['propose','KR-DJN',true],['propose','AU-SYD',true],['start','KR-DJN','economy'],['start','AU-SYD','economy']],20:[['start','SG-SIN','performance']],40:[['wait','IN-BOM']],
     60:[['start','US-NYC','economy']],90:[['start','FR-PAR','performance']],120:[['start','IN-BOM','performance']]},
};
async function globalShift(page,number){
  const g0=await U.G(page);const start0=g0.clock.minute;
  for(let i=0;i<40;i++){
    const g=await U.G(page),t=g.clock.minute-start0;
    for(const [kind,site,arg] of ORDER[number][t]||[]){const id=await P6.rid(page,site);
      if(kind==='start')await P6.start(page,id,arg);else if(kind==='wait')await P6.wait(page,id);else if(kind==='propose'){const p=await P6.negotiate(page,id);assert.equal(p.status,arg?'accepted':'rejected');}}
    if((await U.G(page)).global.done)break;
    const screen=await P6.advance(page,10);if(screen&&screen!=='job-done')break;
  }
  await page.waitForSelector('#screen-dialog[open]');const g=await U.G(page);assert.ok(g.global.done&&g.global.result.cleared,`global shift ${number} cleared`);
  report.shifts.push({kind:'global',save:g.id,shift:number,cleared:true,success:g.global.result.success,total:g.global.result.total});
}

// ---------------- incident scripts: what an operator does, step by step (wrong steps are deliberate checks) ----------------
// step: ['ack'] | ['notify'] | ['obs',probe,expect?] | ['hyp',cause,verdict] | ['act',action,result|[results]] | ['wait','approved:team'|'free'] | ['each',action]
const SCRIPTS={
  dns:[['hook','A1-alert'],['ack'],['obs','ping','ok'],['hyp','dns','insufficient'],['obs','link_stats','ok'],['hyp','transit','refuted'],['obs','dns','bad'],['hyp','dns','confirmed'],['hook','A1-diag'],
       ['act','restart_service','none'],['notify'],['wait','free'],['act','dns_failover','fix']],
  gpu_health:[['ack'],['obs','job_log','bad'],['obs','dcgm','bad'],['hyp','gpu_oom','refuted'],['hyp','gpu_health','confirmed'],['act','isolate_migrate',['isolate_move','refused']],['fallback','gpu_repair'],['hook','A2-iso']],
  storage_full:[['ack'],['obs','storage_space','bad'],['hyp','storage_full','confirmed'],['act','delete_data','refused'],['act','cleanup_temp','fix']],
  tor_uplink:[['ack'],['notify'],['obs','tor_port','bad'],['obs','ping','bad'],['obs','dns','ok'],['hyp','dns','refuted'],['hyp','tor_uplink','confirmed'],['hook','B1-site'],['act','reroute_uplink',['fix','refused']],['fallback','escalate_network']],
  cooling:[['ack'],['notify'],['obs','cooling','bad'],['hyp','cooling','confirmed'],['act','standby_pump','refused'],['act','escalate_facility','call'],['wait','approved:facility'],['act','standby_pump','fix'],['hook','B2-site']],
  ups:[['ack'],['notify'],['obs','ups','bad'],['hyp','ups','confirmed'],['hook','B3-site'],['act','ups_bypass','refused'],['act','escalate_facility','fix'],['each','planned_pause']],
  congestion:[['hook','C-overlap'],['ack'],['obs','storage_latency','ok'],['obs','storage_space','ok'],['hyp','storage_latency','refuted'],['obs','link_stats','bad'],['hyp','congestion','confirmed'],['act','reroute_backup','none'],['wait','free'],['act','qos_adjust','fix']],
  storage_latency:[['ack'],['obs','storage_latency','bad'],['obs','storage_space','ok'],['hyp','storage_full','refuted'],['hyp','storage_latency','confirmed'],['act','cleanup_temp','none'],['wait','free'],['act','storage_path','fix']],
  gpu_oom:[['ack'],['obs','job_log','bad'],['obs','dcgm','ok'],['hyp','gpu_health','refuted'],['hyp','gpu_oom','confirmed'],['act','reduce_batch','refused'],['act','ask_consent','consent'],['oom']],
  crashloop:[['ack'],['obs','service_events','bad'],['obs','job_log','bad'],['hyp','crashloop','confirmed'],['act','restart_service','none'],['wait','free'],['act','escalate_platform','call'],['wait','approved:platform'],['act','rollback_deploy','fix']],
};
const ptr={};let HOOKS={};
const P=()=>currentPage;
async function runScript(rec,typeOf){
  const steps=SCRIPTS[typeOf]||[];ptr[rec.id]??=0;
  while(ptr[rec.id]<steps.length){
    const page=P(),[k,a,b]=steps[ptr[rec.id]],cur=await U.inc(page,rec.id);
    if(k==='hook'){if(HOOKS[a])await HOOKS[a](page,cur);}
    else if(k==='wait'){if(a==='free'&&cur.busyUntil)return;if(a.startsWith('approved:')&&!Object.values(cur.escalations).some(e=>e.ready))return;}
    else if(k==='ack')await U.ack(page,rec.id);
    else if(k==='notify'){const n=await U.notify(page,rec.id);assert.ok(n.length>=1);}
    else if(k==='obs'){const e=await U.observe(page,rec.id,a);if(b)assert.equal(e.status,b,`${rec.id} ${a} reading`);report.incidents.push({id:rec.id,step:`observe ${a}`,status:e.status,summary:e.summary,at:e.location});
      if(typeOf==='congestion'&&a==='storage_latency')assert.ok(e.lines.some(l=>l.includes('무관')),'overlap: the other incident is named and separated');}
    else if(k==='hyp'){const h=await U.hypothesis(page,rec.id,a);assert.equal(h.verdict,b,`${rec.id} hypothesis ${a}`);if(b==='refuted')report.wrong.push({id:rec.id,kind:'hypothesis',cause:a,reason:h.reason});}
    else if(k==='act'){const r=await U.act(page,rec.id,a);const want=[b].flat();assert.ok(r&&want.includes(r.result),`${rec.id} ${a} -> ${r?.result} (want ${want})`);
      if(['none','refused'].includes(r.result))report.wrong.push({id:rec.id,kind:'action',action:a,result:r.result,text:r.text});
      if(r.result==='refused'||r.result==='isolate_move'||r.result==='fix'){rec._last=r.result;}}
    else if(k==='fallback'){if(rec._last==='refused'){const r=await U.act(page,rec.id,a);assert.ok(r&&['fix','isolate_repair','call'].includes(r.result),`${rec.id} fallback ${a}`);}}
    else if(k==='each'){const scope=(await U.inc(page,rec.id)).scope.jobs;for(const j of scope){const r=await U.act(page,rec.id,a,j.rid);assert.ok(r&&['pause','move'].includes(r.result),`${rec.id} ${a} #${j.rid}`);}}
    else if(k==='oom'){const c=(await U.inc(page,rec.id)).consent;
      if(c==='accepted'){const r=await U.act(page,rec.id,'reduce_batch');assert.equal(r.result,'fix');}
      else{steps.splice(ptr[rec.id]+1,0,['act','escalate_platform','call'],['wait','approved:platform'],['act','memory_saving','fix']);}}
    ptr[rec.id]++;
  }
}
async function closeOut(rec){
  const page=P(),cur=await U.inc(page,rec.id);
  if(cur.state!=='monitoring'||(cur.verifyBlocker||'').includes('10분'))return;
  for(const p of cur.verifyProbes)await U.observe(page,rec.id,p);
  const v=await U.verify(page,rec.id);assert.equal(v.state,'verified',`${rec.id} verified`);
  const r=await U.report(page,rec.id);assert.equal(r.state,'closed',`${rec.id} closed`);
}
const TYPE={'INC-A1':'dns','INC-A2':'gpu_health','INC-A3':'storage_full','INC-B1':'tor_uplink','INC-B2':'cooling','INC-B3':'ups','INC-C1':'congestion','INC-C2':'storage_latency','INC-C3':'gpu_oom','INC-C4':'crashloop'};
// One incident shift: start every arrived request (performance first, economy if the customer allows), handle alerts with
// the scripts (hook steps check other places / restart the engine), re-check and report after recovery, advance 10 minutes.
async function incidentShift(){
  for(let i=0;i<60;i++){
    let g=await U.G(P());
    for(const r of g.requests.filter(x=>x.stage==='incoming'&&g.global.requestIds.includes(x.id))){
      const page=P();await U.read(page,r.id);await U.tab(page,'plan');await page.waitForSelector('[data-plan-list]');
      const mode=(await page.locator('[data-plan-option^="performance"]').count())?'performance':(await page.locator('[data-plan-option^="economy"]').count())?'economy':null;
      if(mode){await U.choose(page,r.id,mode,0);await U.startHall(page,r.id);report.incidents.push({rid:r.id,step:`start ${mode}`,clock:(await U.G(page)).clock.label});}
    }
    g=await U.G(P());
    for(const rec of g.incident.records.filter(x=>!['armed','closed','failed','void'].includes(x.state))){await runScript(rec,TYPE[rec.id]);await closeOut(rec);}
    if((await U.G(P())).global.done)break;
    const scr=await U.advance(P(),10);if(scr&&scr.startsWith('incident'))break;
  }
  await P().waitForSelector('#screen-dialog[open]');const g=await U.G(P());assert.ok(g.global.done,'the engine closed the incident shift');
  return g.global.result;
}
function truth(id,result,label){
  const e=engineIncidents(id),recs=e.sim.incident.records.filter(r=>r.shift===e.sim.global.shift),rows=[];
  for(const row of result.incidents){const r=recs.find(x=>x.id===row.id);assert.ok(r,`${label} ${row.id} saved`);
    assert.equal(r.outcome??'open',row.outcome,`${label} ${row.id} outcome`);assert.equal(r.type,row.type,`${label} ${row.id} type`);
    assert.equal(r.evidence.length,row.evidence,`${label} ${row.id} evidence count`);assert.equal(e.reqs[r.rid],'completed',`${label} #${r.rid} request closed`);
    rows.push({id:row.id,type:r.type,outcome:r.outcome,evidence:r.evidence.length,hypotheses:r.hypotheses.map(h=>`${h.cause}:${h.verdict}`),actions:r.actions.map(a=>`${a.action}:${a.result}`),downtime:r.downtime,slow:r.slow_minutes});}
  assert.equal(e.sim.global.result?.cleared??null,result.cleared,`${label} cleared flag saved`);
  report.engineTruth.push({label,save:id,rows});
}

try{
  const seedDir=process.argv.includes('--seed')?tempSaveDir():undefined;   // DEVELOPMENT shortcut only, never the reported run
  if(seedDir){report.graduated=execFileSync(python(),['-m','engine.tests.seed_campaign',seedDir],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}).trim().split(/\s+/).at(-1);report.seeded=true;}
  stack=await startStack({enginePort:8798,vitePort:5198,...(seedDir?{saveDir:seedDir}:{})});report.url=stack.url;
  browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();
  let careerGlobal=null,incidentId=null;

  await check('incident shifts locked before global shift 3; per-cause practice open, labelled by symptom (menu)',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-new=incident]');
    assert.equal(await page.locator('[data-new=incident]').isDisabled(),true);assert.match(await page.locator('[data-mode-card=incident]').textContent(),/교대 3/);
    assert.equal(await page.locator('[data-new=incident_practice]').isDisabled(),false);
    const labels=await page.locator('[data-incident-practice] option').allTextContents();assert.equal(labels.length,10);
    for(const l of labels)assert.doesNotMatch(l,/DNS|UPS|냉각|GPU|ToR|OOM|CrashLoop/,'practice list never names the cause');
    await shot('p7-menu-locked.png');await ctx.close();
  });
  if(!report.seeded)await check('precondition: story chapters 1 -> 5 cleared through the real UI (graduation)',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=story]');await story5.click(page,'[data-new=story]');await page.waitForTimeout(800);
    await story5.chapter1(page);await story5.startNext(page,'2');await story5.chapter2(page);await story5.startNext(page,'3');await story5.chapter3(page);
    await story5.startNext(page,'3b');await story5.chapter4(page);await story5.startNext(page,'lab');await story5.chapter5(page);
    assert.equal((await U.S(page)).screens.open,'graduation');report.graduated=(await U.G(page)).id;await ctx.close();
  });
  await check('precondition: global shifts 1 -> 3 cleared through the real UI (Phase 6 decisions)',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=global]:not([disabled])');await U.click(page,'[data-new=global]');await page.waitForTimeout(700);
    await P6.briefing(page);await globalShift(page,1);await U.click(page,'#screen-dialog[open] [data-next=next-shift]');await page.waitForTimeout(500);
    await P6.briefing(page);await globalShift(page,2);await U.click(page,'#screen-dialog[open] [data-next=next-shift]');await page.waitForTimeout(500);
    await P6.briefing(page);await globalShift(page,3);careerGlobal=(await U.G(page)).id;await ctx.close();
  });
  let A=null;
  await check('shift A (with the senior): DNS, GPU device, storage full — evidence before cause, wrong hypotheses/actions recorded, map never blames the subsea path',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-new=incident]:not([disabled])');await shot('p7-menu-unlocked.png');
    await U.click(page,'[data-new=incident]');await page.waitForTimeout(700);
    // Before the briefing: viewing is allowed, game-changing actions are locked by the engine.
    const g0=await U.G(page);assert.equal(g0.canAdvance,false);assert.ok(await page.locator('[data-advance="10"]').isDisabled());
    await shot('p7-A-briefing.png');const pages=await U.talkThrough(page);assert.equal(pages,3,'full coaching: three senior pages');
    incidentId=(await U.G(page)).id;
    HOOKS={
      'A1-alert':async(page,rec)=>{const g=await U.G(page),path=g.world.paths.find(p=>p.rid===rec.rid);
        assert.equal(path.link,'incident');assert.deepEqual(new Set(Object.values(path.segments)),new Set(['ok']),'no hop blamed before diagnosis');
        assert.equal(rec.cause,null);assert.equal(rec.causeLabel,null);
        await U.incidentTab(page,rec.id);await shot('p7-A1-alert.png');
        await U.places(page,'world');const net=(await U.S(page)).network;report.consistency.push({at:'A1 alert',world:{lit:net.lit,faultKind:net.faultKind,cause:net.cause,hop:net.hop}});
        assert.notEqual(net.faultKind,'degraded');assert.equal(net.cause,'incident');await shot('p7-A1-world-symptom.png');},
      'A1-diag':async(page,rec)=>{const g=await U.G(page),path=g.world.paths.find(p=>p.rid===rec.rid);
        assert.equal(path.link,'internal');assert.equal(path.segments.sea,'ok');assert.equal(path.segments.aidc,'incident');
        await U.places(page,'world');const net=(await U.S(page)).network;report.consistency.push({at:'A1 diagnosed',world:{lit:net.lit,faultKind:net.faultKind,cause:net.cause,aidcMarker:net.aidcMarker}});await shot('p7-A1-world-internal.png');},
      'A2-iso':async(page,rec)=>{const g=await U.G(page);const iso=g.servers.find(s=>s.state!=='HEALTHY');assert.ok(iso,'isolated server is in the engine ledger');
        await U.places(page,'hall');await U.click(page,'[data-camera=overview]');await page.waitForTimeout(900);await shot('p7-A2-hall-isolated.png');
        report.consistency.push({at:'A2 isolated',server:iso.key,state:iso.state,rack:iso.rack,asset:(await U.S(page)).state.facility.assets.find(a=>a.id===iso.rack)?.state});},
    };
    A=await incidentShift();await page.waitForTimeout(400);await shot('p7-A-result.png');
    assert.equal(A.cleared,true,A.feedback.join(' / '));assert.equal(A.resolved,3);
    truth(incidentId,A,'shift A');report.shifts.push({kind:'incident',shift:'A',save:incidentId,cleared:A.cleared,resolved:A.resolved,success:A.success,feedback:A.feedback});
    await U.click(page,'#screen-dialog[open] [data-next=next-incident]');await page.waitForTimeout(600);await ctx.close();
  });
  await check('shift B (team coordination): ToR uplink, cooling, UPS — customer notice before recovery, approvals, facility interiors show engine state, engine restart mid-incident',async()=>{
    let {ctx,page,shot}=await open();if(!(await page.evaluate(()=>!document.querySelector('#menu').hidden)))await U.click(page,'#menu-open');
    await page.waitForSelector(`[data-resume="${incidentId}"]`);await U.click(page,`[data-resume="${incidentId}"]`);await page.waitForTimeout(700);
    assert.equal((await U.G(page)).global.shift,2);assert.equal(await U.talkThrough(page),2,'short coaching: two pages');
    let restarted=false;
    HOOKS={
      'B1-site':async(page,rec)=>{await U.places(page,'campus');await page.locator('[data-facility=NETWORK]').click();await settle(page);await U.click(page,'#enter-building');await page.waitForTimeout(1100);
        const v=(await U.S(page)).interior;assert.ok(v.engine&&v.uplinkDown.length>=1,'network room shows the engine port DOWN');report.consistency.push({at:'B1 network room',interior:v});await shot('p7-B1-network-room.png');
        await U.places(page,'hall');await U.click(page,'[data-camera=overview]');await page.waitForTimeout(900);
        const rack=({A:'A-01',B:'B-01',C:'C-01',D:'D-01'})[v.uplinkDown[0][0]];const asset=(await U.S(page)).state.facility.assets.find(a=>a.id===rack);
        assert.equal(`${asset.state}/${asset.fault}`,'fault/network','the same port is red at the rack');await shot('p7-B1-hall-rack.png');},
      'B2-site':async(page,rec)=>{await U.places(page,'campus');await page.locator('[data-facility=COOLING]').click();await settle(page);await U.click(page,'#enter-building');await page.waitForTimeout(1100);
        const v=(await U.S(page)).interior;assert.ok(v.engine&&Object.values(v.zones).includes('recovering')&&v.standby,'cooling room: standby pump running');report.consistency.push({at:'B2 cooling room',interior:v});await shot('p7-B2-cooling-room.png');
        if(!restarted){restarted=true;await U.places(page,'noc');const r=await resumeAfterRestart(ctx,page,'shift B: cooling recovery in progress');ctx=r.ctx;shot=r.shot;currentPage=r.page;}},
      'B3-site':async(page,rec)=>{await U.places(page,'campus');await page.locator('[data-facility=UPS]').click();await settle(page);await U.click(page,'#enter-building');await page.waitForTimeout(1100);
        const v=(await U.S(page)).interior;assert.ok(v.engine&&Object.values(v.modes).includes('battery'),'UPS room shows battery mode');report.consistency.push({at:'B3 ups room',interior:v});await shot('p7-B3-ups-room.png');
        const g=await U.G(page);assert.ok(g.datacenter,'datacenter totals still present');report.consistency.push({at:'B3 gpu free vs power',healthyFreeGpu:g.datacenter.healthyFreeGpu,ups:g.incident.facilities.ups});},
    };
    const B=await incidentShift();page=currentPage;await page.waitForTimeout(400);await shot('p7-B-result.png');
    assert.equal(B.cleared,true,B.feedback.join(' / '));assert.ok(B.incidents.every(r=>r.notifiedBeforeRecovery),'every customer heard before recovery');
    truth(incidentId,B,'shift B');report.shifts.push({kind:'incident',shift:'B',save:incidentId,cleared:B.cleared,resolved:B.resolved,success:B.success,feedback:B.feedback});
    await U.click(page,'#screen-dialog[open] [data-next=next-incident]');await page.waitForTimeout(600);await ctx.close();
  });
  await check('shift C (independent, overlapping symptoms): congestion + I/O latency at once, OOM + CrashLoop — no senior hints, scope kept apart, consent before condition change',async()=>{
    const {ctx,page,shot}=await open();if(!(await page.evaluate(()=>!document.querySelector('#menu').hidden)))await U.click(page,'#menu-open');
    await page.waitForSelector(`[data-resume="${incidentId}"]`);await U.click(page,`[data-resume="${incidentId}"]`);await page.waitForTimeout(700);
    assert.equal((await U.G(page)).global.shift,3);assert.equal(await U.talkThrough(page),1,'no coaching: one system line');
    HOOKS={'C-overlap':async(page,rec)=>{const g=await U.G(page),c2=g.incident.records.find(r=>r.id==='INC-C2');
        assert.equal(c2.detected,rec.detected,'two alerts at the same minute');assert.equal(rec.hint,null,'no senior hint in shift C');
        await U.incidentTab(page,rec.id);await shot('p7-C-overlap.png');report.consistency.push({at:'C overlap',c1:rec.detected,c2:c2.detected,rids:[rec.rid,c2.rid]});}};
    const C=await incidentShift();await page.waitForTimeout(400);await shot('p7-C-result.png');
    assert.equal(C.cleared,true,C.feedback.join(' / '));assert.equal(C.resolved,4);
    truth(incidentId,C,'shift C');report.shifts.push({kind:'incident',shift:'C',save:incidentId,cleared:C.cleared,resolved:C.resolved,success:C.success,feedback:C.feedback});
    assert.equal((await U.S(page)).screens.open,'incident-complete');await ctx.close();
    const kinds=new Set(report.wrong.map(w=>`${w.kind}:${w.cause||w.action}`));assert.ok(kinds.size>=5,`at least five different wrong hypotheses/actions (${[...kinds]})`);
  });
  await check('failure -> new slot retry: UPS battery runs out without mitigation, job fails, source save unchanged',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-incident-practice]');await page.selectOption('[data-incident-practice]','ups');await U.click(page,'[data-new=incident_practice]');await page.waitForTimeout(700);
    await U.talkThrough(page);const rid=(await U.G(page)).requests[0].id;await U.startJob(page,rid,'performance');
    await U.until(page,g=>g.incident.records[0].state!=='armed');const id=(await U.incs(page))[0].id;
    await U.ack(page,id);await U.observe(page,id,'ups');await U.hypothesis(page,id,'ups');await U.act(page,id,'escalate_facility');
    await U.until(page,g=>g.incident.records[0].state==='failed',4);await shot('p7-fail-ups.png');
    await U.until(page,g=>g.global.done,10);await page.waitForSelector('#screen-dialog[open]');assert.equal((await U.S(page)).screens.open,'incident-failed');await shot('p7-fail-result.png');
    const src=(await U.G(page)).id,before=records(src);
    await U.click(page,'#screen-dialog[open] [data-next=retry-incident]');await page.waitForTimeout(900);
    const g2=await U.G(page);assert.notEqual(g2.id,src);assert.equal(g2.incident.practice,'ups');assert.equal(records(src),before,'source game records unchanged (only the display-only "result seen" flag may be added)');
    report.resumes.push({label:'retry after failure',source:src,newSlot:g2.id});await ctx.close();
  });
  await check('practice save -> engine restart -> resume at alert, mid-recovery and after close (same evidence, timers, ledger)',async()=>{
    let {ctx,page}=await open();await page.waitForSelector('[data-incident-practice]');await page.selectOption('[data-incident-practice]','crashloop');await U.click(page,'[data-new=incident_practice]');await page.waitForTimeout(700);
    await U.talkThrough(page);const rid=(await U.G(page)).requests[0].id;await U.startJob(page,rid,'performance');
    await U.until(page,g=>g.incident.records[0].state!=='armed');const id=(await U.incs(page))[0].id;
    ({ctx,page}=await resumeAfterRestart(ctx,page,'practice: at the alert'));
    await U.ack(page,id);await U.observe(page,id,'service_events');await U.observe(page,id,'job_log');await U.hypothesis(page,id,'crashloop');
    await U.act(page,id,'escalate_platform');await U.advance(page,10);await U.act(page,id,'rollback_deploy');
    ({ctx,page}=await resumeAfterRestart(ctx,page,'practice: recovery in progress'));
    await U.until(page,g=>g.incident.records[0].state==='monitoring',4);await U.advance(page,10);
    for(const p of (await U.inc(page,id)).verifyProbes)await U.observe(page,id,p);await U.verify(page,id);await U.report(page,id);
    ({ctx,page}=await resumeAfterRestart(ctx,page,'practice: incident closed'));assert.equal((await U.inc(page,id)).state,'closed');await ctx.close();
  });
  await check('duplicate run and port conflict are refused (the same save cannot open twice; a used port fails with exit code 2)',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-incident-practice]');await page.selectOption('[data-incident-practice]','dns');await U.click(page,'[data-new=incident_practice]');await page.waitForTimeout(700);
    const id=(await U.G(page)).id;let dup=null,clash=null;
    try{
      dup=spawn(python(),['-m','engine.server','--port','8799','--save-dir',stack.saveDir],{cwd:ROOT,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
      let ok=false;for(let i=0;i<40&&!ok;i++){try{ok=(await fetch('http://127.0.0.1:8799/api/health')).ok;}catch{}await new Promise(r=>setTimeout(r,250));}
      assert.ok(ok,'second engine on another port is up');
      const second=await (await fetch(`http://127.0.0.1:8799/api/games/${id}`)).json();
      assert.equal(second.ok,false,'the second engine cannot open a save the first one holds');assert.match(second.message,/사용 중/);
      let err='';clash=spawn(python(),['-m','engine.server','--port','8799','--save-dir',stack.saveDir],{cwd:ROOT,env:{...process.env,PYTHONIOENCODING:'utf-8'}});clash.stderr.on('data',d=>{err+=d;});
      const code=await new Promise(r=>{clash.once('exit',r);setTimeout(()=>r('timeout'),10000);});
      assert.equal(code,2,'a used port is an error, not a silent second listener');assert.match(err,/already in use/);
      report.resumes.push({label:'duplicate/port',save:id,second:second.message,clashExit:code,clashMessage:err.trim().slice(0,160)});
    }finally{dup?.kill();clash?.kill();await ctx.close();}
  });
  await check('layout: incident card buttons and the senior/briefing box visible without page scroll at 1366x768, 1366x768@150% and 1920x1080@150%; tutorial/story too',async()=>{
    for(const [w,h,dpr,label]of [[1366,768,1,'1366x768'],[911,512,1.5,'1366x768 at 150% (emulated)'],[1280,720,1.5,'1920x1080 at 150% (emulated)']]){
      const {ctx,page,shot}=await open({width:w,height:h,dpr});
      const topmost=async sel=>page.evaluate(s=>{const e=document.querySelector(s);if(!e)return 'missing';const r=e.getBoundingClientRect();if(r.bottom>innerHeight+1||r.right>innerWidth+1||r.top<0)return 'outside';const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return t===e||e.contains(t)?'ok':`covered by ${t?.id||t?.className}`;},sel);
      const row={label};
      await page.waitForSelector('[data-incident-practice]');await page.selectOption('[data-incident-practice]','dns');await U.click(page,'[data-new=incident_practice]');await page.waitForTimeout(700);
      row.talk=await topmost('#talk:not([hidden]) #coach-start');await U.talkThrough(page);
      const rid=(await U.G(page)).requests[0].id;await U.startJob(page,rid,'performance');await U.until(page,g=>g.incident.records[0].state!=='armed');
      await U.incidentTab(page,(await U.incs(page))[0].id);row.ack=await topmost('[data-incident-ack]');row.tab=await topmost('[data-ws-tab=incident]');row.time=await topmost('[data-advance="10"]');
      row.pageScroll=await page.evaluate(()=>document.scrollingElement.scrollHeight>innerHeight+2);await shot(`p7-layout-${w}x${h}@${dpr}.png`);
      for(const k of ['talk','ack','tab','time'])assert.equal(row[k],'ok',`${label} ${k}: ${row[k]}`);assert.equal(row.pageScroll,false,`${label} page does not scroll`);
      await U.click(page,'#menu-open');await page.waitForSelector('[data-new=tutorial]');await U.click(page,'[data-new=tutorial]');await page.waitForTimeout(800);
      row.tutorialStart=await topmost('#talk:not([hidden]) #coach-start, #talk:not([hidden]) #talk-next');
      await U.click(page,'#menu-open');await U.click(page,'[data-new=story]');await page.waitForTimeout(800);
      row.storyTalk=await topmost('#talk:not([hidden]) #talk-next, #talk:not([hidden]) #coach-start, #talk:not([hidden]) #talk-done');await shot(`p7-layout-story-${w}x${h}@${dpr}.png`);
      assert.equal(row.tutorialStart,'ok',`${label} tutorial talk`);assert.equal(row.storyTalk,'ok',`${label} story talk`);
      report.layout.push(row);await ctx.close();
    }
  });
  await check('performance and WebGL stability: 10 cycles over world, campus, NOC, hall and four facility interiors; reduced motion',async()=>{
    const {ctx,page}=await open({reducedMotion:true});await page.waitForSelector('[data-incident-practice]');await page.selectOption('[data-incident-practice]','cooling');await U.click(page,'[data-new=incident_practice]');await page.waitForTimeout(700);
    await U.talkThrough(page);await perf(page,'incident practice · NOC');
    for(let i=0;i<10;i++){for(const r of ['world','campus','noc','hall'])await U.places(page,r);
      for(const f of ['COOLING','UPS','NETWORK','POWER']){await U.places(page,'campus');await page.locator(`[data-facility=${f}]`).click();await settle(page);await U.click(page,'#enter-building');await page.waitForTimeout(500);}
      const s=await U.S(page);report.resources.push({cycle:i+1,geometries:s.renderer.geometries,textures:s.renderer.textures,heapMiB:s.heap?+(s.heap.used/1048576).toFixed(1):null});}
    const geo=report.resources.map(r=>r.geometries),tex=report.resources.map(r=>r.textures);
    assert.ok(Math.max(...geo.slice(1))-Math.min(...geo.slice(1))<=2,`geometries ${geo}`);assert.ok(Math.max(...tex.slice(1))-Math.min(...tex.slice(1))<=2,`textures ${tex}`);
    await U.places(page,'hall');await perf(page,'hall after 10 cycles');await U.places(page,'world');await perf(page,'world after 10 cycles');
    assert.equal(report.crashes.length,0,'no renderer crash');await ctx.close();
  });
  await check('no page errors / console errors / target crashes during the whole run',async()=>{
    assert.deepEqual(report.errors,[]);assert.deepEqual(report.crashes,[]);
    const bad=report.consoleErrors.filter(x=>!/favicon|status of 4\d\d/.test(x));assert.deepEqual(bad,[]);
  });
}finally{
  report.finishedAt=new Date().toISOString();report.summary={pass:report.checks.filter(c=>c.pass).length,total:report.checks.length};
  await writeFile(resolve(out,'phase7-qa.json'),JSON.stringify(report,null,2));
  console.log(`\nPhase 7 QA ${report.summary.pass}/${report.summary.total}`);
  try{await browser?.close();}catch{}try{await stack?.stop();}catch{}
}

