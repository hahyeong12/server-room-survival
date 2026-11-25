// Issue #7 (Phase 6) browser QA: global shifts played through the real 3D UI in Chrome (Playwright CDP mouse /
// keyboard on the menu, talk box, monitor tabs, inbox filter, plan cards, 3D racks and world cities, time buttons).
// Isolated stack: Python engine on a temporary save folder + its own Vite port and cache.
// The API and the save files are only READ (window.worldQA, node:sqlite read-only, file hashes); nothing is set directly.
// Precondition: a regular story save graduated (chapters 1 -> 5) through the real UI, as in the Phase 5 QA.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {startStack,settle,CHROME,tempSaveDir,python} from './qa-lib.mjs';
import {execFileSync} from 'node:child_process';
import {S,G,click,places,toastText,canvasClick,briefing,rid,req,tab,selectRow,read,planTab,choose,startHall,start,negotiate,wait,reject,drainJobs,advance} from './phase6-ui.mjs';
import * as story5 from './campaign-flows.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)||'../../docs/3d-world-expansion/qa/phase6');   // Phase 7: --out= keeps a regression run apartawait mkdir(out,{recursive:true});
const only=process.argv.find(x=>x.startsWith('--only='))?.slice(7);
const report={issue:7,mode:'Chrome headed / Playwright CDP / isolated contexts / isolated engine+saves (temporary)',checks:[],errors:[],consoleErrors:[],screenshots:[],shifts:[],requests:[],resumes:[],engineTruth:[],performance:[],resources:[],layout:[],startedAt:new Date().toISOString()};
let browser,stack,currentPage=null,careerId=null;
async function check(name,fn){if(only&&!name.includes(only))return;const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){
  const shotName=`fail-${report.checks.length+1}.png`;let state=null;try{await currentPage?.screenshot({path:resolve(out,shotName)});const s=await currentPage.evaluate(()=>worldQA.snapshot());state={screen:s.screens.open,clock:s.game?.clock?.label,route:s.state.navigation.route,global:s.game?.global&&{shift:s.game.global.shift,done:s.game.global.done},actions:await currentPage.evaluate(()=>worldQA.actions().slice(-8))};}catch{}
  report.checks.push({name,pass:false,error:e.stack?.split('\n').slice(0,5).join(' | '),failShot:shotName,state});console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`);}}
async function open({width=1920,height=1080,dpr=1,reducedMotion=false}={}){
  const ctx=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:reducedMotion?'reduce':'no-preference'});
  await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');}catch{}});
  const page=await ctx.newPage();currentPage=page;page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  page.on('dialog',d=>d.accept());
  await page.goto(stack.url,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1200);
  const shot=async name=>{await page.screenshot({path:resolve(out,name)});report.screenshots.push(name);};
  return {ctx,page,shot};
}
const sha=async p=>createHash('sha256').update(await readFile(p)).digest('hex');
// Game records of a save (read-only): every table plus the simulation payload without display-only flags.
function records(p){const db=new DatabaseSync(p,{readOnly:true});try{const payload=JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);
  if(payload.global)delete payload.global.seen;
  const tables=Object.fromEntries(db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name<>'simulation_state'").all().map(t=>[t.name,db.prepare(`SELECT * FROM ${t.name}`).all()]));
  return JSON.stringify({payload,tables});}finally{db.close();}}
const savePath=id=>join(stack.saveDir,`${id}.db`);
// The engine's own records of a save, read-only: request status, runtime terms/proposals/state, server allocations.
function engineRecords(id){const db=new DatabaseSync(savePath(id),{readOnly:true});try{
  const reqs=Object.fromEntries(db.prepare('SELECT id,status,rejection_reason FROM customer_requests').all().map(r=>[r.id,r]));
  const rt=Object.fromEntries(db.prepare('SELECT request_id,payload FROM request_runtime').all().map(r=>[r.request_id,JSON.parse(r.payload)]));
  const sim=JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);
  return {reqs,rt,sim};}finally{db.close();}}
// Every row of a shift result screen equals the engine's saved record (single source of truth).
function verifyAgainstEngine(id,result,label){
  const e=engineRecords(id),rows=[];
  for(const r of result.rows){const rec=e.reqs[r.rid],rt=e.rt[r.rid],prop=rt.proposals.at(-1);
    assert.equal(rec.status,r.outcome==='rejected'||r.outcome==='expired'?'rejected':'completed',`${label} #${r.rid} status`);
    assert.equal(rt.conditions.catalog.site,r.site,`${label} #${r.rid} site frozen in the save`);
    if(['on_time','late','expired'].includes(r.outcome))assert.equal(rt.terms.evaluation,r.score,`${label} #${r.rid} score`);
    assert.equal(prop?.status??null,r.proposal,`${label} #${r.rid} consent record`);
    if(r.mode)assert.equal({performance:'고성능 모드',economy:'절약형 모드'}[rt.state.plan],r.mode,`${label} #${r.rid} mode`);
    rows.push({rid:r.rid,site:r.site,client:r.client,job:r.job,outcome:r.outcome,score:r.score,mode:r.mode,consent:r.consent,proposal:r.proposal,engineStatus:rec.status,allocations:rt.server_allocations.length});}
  assert.equal(e.sim.global.result?.cleared??null,result.cleared,`${label} cleared flag saved`);
  report.engineTruth.push({label,save:id,rows});
}
async function perf(page,label){await page.waitForTimeout(1300);const s=await S(page);report.performance.push({label,fps:+s.stats.fps.toFixed(1),p95:+(s.stats.p95FrameMs??0).toFixed(2),heapMiB:s.heap?+(s.heap.used/1048576).toFixed(1):null,geometries:s.renderer.geometries,textures:s.renderer.textures,calls:s.renderer.calls});}
async function restartAndResume(ctx,page,label){
  const before=await G(page),id=before.id;await ctx.close();
  await stack.restartEngine();
  const {ctx:ctx2,page:page2,shot}=await open();
  if(!(await page2.evaluate(()=>!document.querySelector('#menu').hidden)))await click(page2,'#menu-open');
  await page2.waitForSelector(`[data-resume="${id}"]`);await click(page2,`[data-resume="${id}"]`);await page2.waitForTimeout(800);
  const after=await G(page2);
  for(const k of ['clock','requests','servers','datacenter','global'])assert.deepEqual(after[k],before[k],`${label}: ${k} kept after engine restart`);
  report.resumes.push({label,id,clock:after.clock.label,shift:after.global?.shift??null,requests:after.requests.length,open:after.requests.filter(r=>!['done','failed','rejected'].includes(r.stage)).length});
  return {ctx:ctx2,page:page2,shot};
}
const lit=async page=>(await S(page)).network?.lit??[];

// The decisions of each shift (minutes after the shift start). They are the same as tests/test_global_shifts.PLANS,
// but here each one is a real click sequence; hooks add the checks a player would see at that moment.
const ORDER={
  1:{0:[['start','KR-SEL','performance'],['start','US-SFO','performance']],30:[['start','DE-FRA','performance']],40:[['wait','US-SEA']],60:[['start','JP-OSA','performance']],70:[['start','US-SEA','performance']]},
  2:{0:[['propose','US-IAD',false],['start','US-IAD','performance'],['contention','IN-BLR'],['propose','IN-BLR',true],['start','IN-BLR','economy']],20:[['wait','KR-PUS']],50:[['wait','GB-LON']],
     80:[['start','GB-LON','performance'],['start','NL-AMS','performance']],90:[['wait','TW-TPE']],100:[['start','TW-TPE','performance']],120:[['start','KR-PUS','performance']]},
  3:{0:[['impossible','KR-DJN'],['propose','KR-DJN',true],['propose','AU-SYD',true],['start','KR-DJN','economy'],['start','AU-SYD','economy']],20:[['start','SG-SIN','performance']],40:[['wait','IN-BOM']],
     60:[['start','US-NYC','economy']],90:[['start','FR-PAR','performance']],120:[['start','IN-BOM','performance']]},
};
async function doAction(page,[kind,site,arg]){
  const id=await rid(page,site);
  if(kind==='start'){await start(page,id,arg);report.requests.push({site,rid:id,action:`start ${arg}`,clock:(await G(page)).clock.label});}
  else if(kind==='wait'){await wait(page,id);
    // waiting is a real choice: the engine has no plan to offer right now
    await planTab(page,id);const none=await page.locator('[data-plan-option]').count();report.requests.push({site,rid:id,action:'wait',optionsNow:none});}
  else if(kind==='propose'){const p=await negotiate(page,id);assert.equal(p.status,arg?'accepted':'rejected',`${site} customer reply`);report.requests.push({site,rid:id,action:'propose',reply:p.status});}
  else if(kind==='contention'){await read(page,id);await planTab(page,id);
    assert.equal(await page.locator('[data-plan-option^="performance"]').count(),0,'no option for the original plan that no longer fits');
    assert.match(await page.locator('.mode-card[data-mode=performance]').textContent(),/부족/);
    assert.equal(await page.locator('[data-plan-option^="economy"]').count(),0,'economy is not offered without the customer consent');
    report.requests.push({site,rid:id,action:'contention refused',reason:(await page.locator('.mode-card[data-mode=performance]').textContent()).slice(0,120)});}
  else if(kind==='impossible'){await read(page,id);await planTab(page,id);
    assert.equal(await page.locator('[data-plan-option^="performance"]').count(),0);
    assert.match(await page.locator('.mode-card[data-mode=performance]').textContent(),/서버별 GPU·전력 조합 불가/);
    report.requests.push({site,rid:id,action:'original condition refused by the server rule'});}
}
async function playShift(page,number,{hooks={},until=null}={}){
  const g0=await G(page);assert.equal(g0.global.shift,number);const start0=g0.clock.minute;
  for(let i=0;i<40;i++){
    const g=await G(page),t=g.clock.minute-start0;
    for(const a of ORDER[number][t]||[])await doAction(page,a);
    if(hooks[t])await hooks[t](page);
    if(until&&until===t)return null;
    if((await G(page)).global.done)break;
    const screen=await advance(page,10);if(screen&&screen!=='job-done')break;
  }
  await page.waitForSelector('#screen-dialog[open]');
  const g=await G(page);assert.ok(g.global.done,'the engine closed the shift');
  report.shifts.push({save:g.id,shift:number,title:g.global.result.title,cleared:g.global.result.cleared,success:g.global.result.success,total:g.global.result.total,average:g.global.result.average,from:g.global.result.started,to:g.global.result.finished,feedback:g.global.result.feedback});
  return g.global.result;
}

try{
  // --seed is a DEVELOPMENT shortcut only (graduation played through adapter actions). The reported run never uses it.
  const seedDir=process.argv.includes('--seed')?tempSaveDir():undefined;
  if(seedDir){report.graduated=execFileSync(python(),['-m','engine.tests.seed_campaign',seedDir],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}).trim().split(/\s+/).at(-1);report.seeded=true;}
  stack=await startStack({enginePort:8796,vitePort:5196,...(seedDir?{saveDir:seedDir}:{})});report.url=stack.url;
  browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();

  await check('neutral world before any game: 21 city markers and routes exist, nothing is lit, legacy markers neutral',async()=>{
    const {ctx,page,shot}=await open();await page.evaluate(()=>document.querySelector('#menu').hidden=true);await places(page,'world');
    const v=(await S(page)).network;assert.ok(v.sites>=20,`${v.sites} sites`);assert.equal(v.routes,v.sites+3,'one route per city + three legacy aliases');
    assert.deepEqual(v.lit,[]);assert.deepEqual(v.requestBadges,[]);assert.equal(v.packetsVisible,false);
    for(const [c,col]of Object.entries(v.markers))assert.equal(col,'#6d8ea3',`${c} neutral`);
    await shot('p6-world-neutral.png');report.world={sites:v.sites,routes:v.routes};await ctx.close();
  });
  if(!report.seeded)await check('global shifts locked before graduation; global free ops open (menu)',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-new=global]');
    assert.equal(await page.locator('[data-new=global]').isDisabled(),true);assert.match(await page.locator('[data-mode-card=global]').textContent(),/제5장/);
    assert.equal(await page.locator('[data-new=global_free]').isDisabled(),false);await shot('p6-menu-locked.png');await ctx.close();
  });
  if(!report.seeded)await check('precondition: regular story chapters 1 -> 5 cleared through the real UI (graduation)',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=story]');await story5.click(page,'[data-new=story]');await page.waitForTimeout(800);
    await story5.chapter1(page);await story5.startNext(page,'2');await story5.chapter2(page);await story5.startNext(page,'3');await story5.chapter3(page);
    await story5.startNext(page,'3b');await story5.chapter4(page);await story5.startNext(page,'lab');await story5.chapter5(page);
    assert.equal((await S(page)).screens.open,'graduation');report.graduated=(await G(page)).id;await ctx.close();
  });
  await check('shift 1 (intro): two US cities and a Seoul customer through the real UI, map lights only arrived cities, engine restart mid-shift',async()=>{
    let {ctx,page,shot}=await open();await page.waitForSelector('[data-new=global]:not([disabled])');await click(page,'[data-new=global]');await page.waitForTimeout(800);
    let g=await G(page);careerId=g.id;assert.equal(g.kind,'global');assert.equal(g.global.shift,1);
    assert.equal(await page.locator('[data-advance="10"]').isDisabled(),true,'time waits for the briefing');
    await shot('p6-s1-briefing.png');report.briefingPages=await briefing(page);
    await places(page,'world');assert.deepEqual((await lit(page)).sort(),['KR-SEL','US-SFO'],'only the two arrived cities are lit');
    // A click on the lit San Francisco badge selects that request in the engine.
    const sfo=await rid(page,'US-SFO');await canvasClick(page,'world','US-SFO');assert.equal((await G(page)).focus,sfo,'world click -> that city request');
    assert.match(await toastText(page),/샌프란시스코/);
    await click(page,'[data-site=KR-SEL]');assert.equal((await G(page)).focus,await rid(page,'KR-SEL'),'panel city chip -> that request');await shot('p6-s1-world-start.png');
    // A Seoul customer is domestic: its route is the domestic backbone only.
    assert.equal((await G(page)).world.paths.find(p=>p.code==='KR-SEL').domestic,true);
    await tab(page,'inbox');await shot('p6-s1-inbox.png');
    const hooks={
      40:async page=>{ // San Francisco still running, Seattle just arrived, Frankfurt running: three cities lit, Seoul (done) dark.
        await places(page,'world');const l=(await lit(page)).sort();assert.deepEqual(l,['DE-FRA','US-SEA','US-SFO']);
        const a=await page.evaluate(()=>worldQA.projectWorld('US-SFO')),b=await page.evaluate(()=>worldQA.projectWorld('US-SEA'));
        assert.ok(Math.hypot(a.x-b.x,a.y-b.y)>20,'two US cities are two badges, not one US pin');
        await canvasClick(page,'world','US-SEA');assert.equal((await G(page)).focus,await rid(page,'US-SEA'));
        await shot('p6-s1-world-three-cities.png');report.mapThree=l;
        ({ctx,page,shot}=await restartAndResume(ctx,page,'shift 1 middle (t+40)'));currentPage=page;pageRef.page=page;},
    };
    const pageRef={page};
    // playShift keeps using the resumed page through pageRef after the restart hook.
    const res=await (async()=>{const g0=await G(page);const start0=g0.clock.minute;
      for(let i=0;i<40;i++){const p=pageRef.page,gg=await G(p),t=gg.clock.minute-start0;for(const a of ORDER[1][t]||[])await doAction(p,a);if(hooks[t])await hooks[t](p);
        if((await G(pageRef.page)).global.done)break;const sc=await advance(pageRef.page,10);if(sc&&sc!=='job-done')break;}
      page=pageRef.page;await page.waitForSelector('#screen-dialog[open]');const r=(await G(page)).global.result;
      report.shifts.push({save:careerId,shift:1,title:r.title,cleared:r.cleared,success:r.success,total:r.total,average:r.average,from:r.started,to:r.finished,feedback:r.feedback});return r;})();
    assert.equal((await S(page)).screens.open,'shift-clear');assert.ok(res.cleared);assert.equal(res.success,5);
    await shot('p6-s1-result.png');verifyAgainstEngine(careerId,res,'shift 1');
    await places(page,'world').catch(()=>{});
    ({ctx,page,shot}=await restartAndResume(ctx,page,'shift 1 end'));currentPage=page;
    await page.waitForSelector('#screen-dialog[open] [data-next=next-shift]');assert.deepEqual(await lit(page),[],'all routes dark after the shift');
    await ctx.close();
  });
  await check('shift 2 (contention): engine refuses the plan that no longer fits, customer rejects one alternative and accepts another',async()=>{
    let {ctx,page,shot}=await open();await click(page,'#menu-open').catch(()=>{});await page.waitForSelector(`[data-resume="${careerId}"]`);await click(page,`[data-resume="${careerId}"]`);await page.waitForTimeout(600);
    // Closing the result screen another way never strands the save: the 결과 tab keeps the next-shift action.
    await page.waitForSelector('#screen-dialog[open] [data-next=next-shift]');await click(page,'#screen-dialog[open] [data-next=stay]');
    await tab(page,'result');await page.waitForSelector('[data-start-shift="2"]');await click(page,'[data-start-shift="2"]');await page.waitForTimeout(500);
    let g=await G(page);assert.equal(g.global.shift,2);assert.equal(g.id,careerId,'the next shift continues in the same save');
    ({ctx,page,shot}=await restartAndResume(ctx,page,'shift 2 start'));currentPage=page;
    await briefing(page);
    const res=await playShift(page,2,{hooks:{0:async page=>{await places(page,'hall');await shot('p6-s2-hall-two-customers.png');
      const s=await S(page);assert.equal(s.game.datacenter.gpuUsed,9);assert.equal(s.game.datacenter.powerUsed,9);
      await tab(page,'inbox');await click(page,'[data-filter=running]');assert.equal(await page.locator('[data-request-row]').count(),2,'filter: running jobs');await shot('p6-s2-inbox-filter.png');
      await page.selectOption('[data-sort]','due');await settle(page);await click(page,'[data-filter=all]');}}});
    assert.ok(res.cleared);assert.equal(res.counts.on_time,6);
    const blr=res.rows.find(r=>r.site==='IN-BLR'),iad=res.rows.find(r=>r.site==='US-IAD');
    assert.equal(blr.consent,'고객 동의 대안');assert.equal(blr.proposal,'accepted');assert.equal(iad.proposal,'rejected');assert.equal(iad.consent,'원래 요청 조건');
    await shot('p6-s2-result.png');verifyAgainstEngine(careerId,res,'shift 2');
    await click(page,'#screen-dialog[open] [data-next=next-shift]');await page.waitForTimeout(400);await ctx.close();
  });
  await check('shift 3 (independent): no senior hints, original condition impossible on the servers, final global summary',async()=>{
    let {ctx,page,shot}=await open();await click(page,'#menu-open').catch(()=>{});await page.waitForSelector(`[data-resume="${careerId}"]`);await click(page,`[data-resume="${careerId}"]`);await page.waitForTimeout(600);
    const g=await G(page);assert.equal(g.global.shift,3);assert.equal(g.global.coaching,'none');
    assert.equal(await briefing(page),1,'one system page only');
    await read(page,await rid(page,'KR-DJN'));assert.equal(await page.locator('[data-hint]').count(),0,'no senior hint in the independent shift');
    const res=await playShift(page,3,{hooks:{60:async page=>{await places(page,'world');const l=await lit(page);assert.ok(l.length>=4,`${l.length} cities lit at once`);await shot('p6-s3-world-many.png');report.mapMany=l;}}});
    assert.ok(res.cleared);assert.equal((await S(page)).screens.open,'global-complete');await shot('p6-global-complete.png');
    verifyAgainstEngine(careerId,res,'shift 3');
    const total=report.shifts.filter(s=>s.save===careerId).reduce((n,s)=>n+s.total,0);assert.ok(total>=15,`${total} customer requests across the three shifts`);report.totalRequests=total;
    ({ctx,page,shot}=await restartAndResume(ctx,page,'after shift 3'));currentPage=page;await ctx.close();
  });
  await check('a failed shift: expiry, a late job and a justified rejection → shift failed → retry in a NEW slot (source unchanged)',async()=>{
    let {ctx,page,shot}=await open();await page.waitForSelector('[data-new=global]:not([disabled])');await click(page,'[data-new=global]');await page.waitForTimeout(800);
    const id=(await G(page)).id;await briefing(page);
    const bad={0:[['start','US-SFO','performance']],40:[['wait','US-SEA']],50:[['start','DE-FRA','performance']],70:[['start','US-SEA','performance']]};
    const start0=(await G(page)).clock.minute;
    for(let i=0;i<40;i++){const t=(await G(page)).clock.minute-start0;
      if(t===0){await reject(page,await rid(page,'KR-SEL'),'오전 색인 갱신 시각까지 GPU를 비울 수 없어 정중히 거절합니다');}
      for(const a of bad[t]||[])await doAction(page,a);
      if((await G(page)).global.done)break;const sc=await advance(page,10);if(sc&&sc!=='job-done')break;}
    await page.waitForSelector('#screen-dialog[open]');const r=(await G(page)).global.result;
    assert.equal(r.cleared,false);assert.equal((await S(page)).screens.open,'shift-failed');
    const o=Object.fromEntries(r.rows.map(x=>[x.site,x.outcome]));assert.equal(o['JP-OSA'],'expired');assert.equal(o['DE-FRA'],'late');assert.equal(o['KR-SEL'],'rejected');
    await shot('p6-shift-failed.png');verifyAgainstEngine(id,r,'failed shift 1');report.shifts.push({save:id,shift:1,failed:true,outcomes:o,feedback:r.feedback});
    assert.equal(await page.locator('#screen-dialog[open] [data-next=next-shift]').count(),0,'no next shift after a failed shift');
    const before=records(savePath(id));
    await click(page,'#screen-dialog[open] [data-next=retry-shift]');await page.waitForTimeout(800);
    const g=await G(page);assert.notEqual(g.id,id);assert.equal(g.global.shift,1);assert.equal(g.global.briefed,false);assert.equal(g.clock.label,'D1 09:00');
    assert.equal(records(savePath(id)),before,'the failed save keeps every game record (only the display flag of the closed screen is added)');report.retry={from:id,to:g.id};await ctx.close();
  });
  await check('global free operations: requests keep arriving from many cities; save → engine restart → resume',async()=>{
    let {ctx,page,shot}=await open();await page.waitForSelector('[data-new=global_free]');await click(page,'[data-new=global_free]');await page.waitForTimeout(800);
    for(let i=0;i<8;i++){
      const g=await G(page);
      for(const r of g.requests.filter(x=>x.stage==='incoming')){await read(page,r.id);await planTab(page,r.id);
        const opt=await page.locator('[data-plan-option]').first();if(await opt.count()){await opt.click();await settle(page);await startHall(page,r.id);}}
      await advance(page,30);
    }
    const g=await G(page),sites=[...new Set(g.requests.map(r=>r.code))];assert.ok(sites.length>=5,`${sites.length} cities`);
    assert.ok(g.requests.every(r=>r.catalog?.version===1));report.free={id:g.id,requests:g.requests.length,sites};
    await places(page,'world');await shot('p6-free-world.png');
    ({ctx,page,shot}=await restartAndResume(ctx,page,'global free'));await ctx.close();
  });
  await check('earlier modes still resume: graduated story save, a new tutorial / free / practice save after an engine restart',async()=>{
    let {ctx,page}=await open();
    const made=[];for(const sel of ['[data-new=tutorial]','[data-new=free]','[data-practice="2"]']){if(!(await page.evaluate(()=>!document.querySelector('#menu').hidden)))await click(page,'#menu-open');await page.waitForSelector(sel);await click(page,sel);await page.waitForTimeout(700);made.push((await G(page)).id);}
    await ctx.close();await stack.restartEngine();
    ({ctx,page}=await open());
    for(const id of [...made,report.graduated]){if(!(await page.evaluate(()=>!document.querySelector('#menu').hidden)))await click(page,'#menu-open');
      await page.waitForSelector(`[data-resume="${id}"]`);await click(page,`[data-resume="${id}"]`);await page.waitForTimeout(700);
      const g=await G(page);assert.equal(g.id,id,`${id} resumed from the menu`);report.resumes.push({label:'earlier mode',id,mode:g.mode,kind:g.kind,clock:g.clock.label});}
    await page.waitForSelector('#screen-dialog[open]');assert.equal((await S(page)).screens.open,'graduation','the graduated story save reopens at its graduation');
    await ctx.close();
  });
  for(const [w,h,dpr,label]of [[1366,768,1,'1366x768'],[911,512,1.5,'1366x768 at 150% (emulated, full screen)'],[911,430,1.5,'1366x768 at 150% inside a browser window (emulated)'],[1280,720,1.5,'1920x1080 at 150% (emulated)'],[1920,1080,1,'1920x1080']]){
    await check(`layout ${label}: inbox filter, request rows, read/wait/reject, plan, time, world city list reachable without page scroll`,async()=>{
      const {ctx,page,shot}=await open({width:w,height:h,dpr});await page.waitForSelector('[data-new=global_free]');await click(page,'[data-new=global_free]');await page.waitForTimeout(700);
      const id=(await G(page)).requests[0].id;await tab(page,'inbox');
      const inView=async sel=>page.evaluate(sel=>{const e=document.querySelector(sel);if(!e)return {sel,found:false};const r=e.getBoundingClientRect();return {sel,found:true,ok:r.width>0&&r.top>=0&&r.left>=0&&r.bottom<=innerHeight+1&&r.right<=innerWidth+1,top:Math.round(r.top),bottom:Math.round(r.bottom)};},sel);
      const rows=[];for(const sel of ['[data-filter=open]','[data-sort]',`[data-request-row="${id}"]`,`[data-read-request="${id}"]`,`[data-wait="${id}"]`,'[data-ws-tab=plan]','[data-advance="10"]'])rows.push(await inView(sel));
      await tab(page,'plan');await page.waitForSelector('[data-plan-list]');rows.push(await inView('[data-plan-list] .mode-card .mode-head'));rows.push(await inView('[data-plan-option], [data-propose]'));
      await places(page,'world');rows.push(await inView('[data-site]'));
      const scroll=await page.evaluate(()=>({doc:document.scrollingElement.scrollHeight>innerHeight+1,body:document.body.scrollHeight>innerHeight+1}));
      await shot(`p6-layout-${w}x${h}@${dpr}.png`);report.layout.push({label,rows,scroll});
      for(const r of rows)assert.ok(r.found&&r.ok,`${label}: ${r.sel} visible without scrolling (${JSON.stringify(r)})`);
      assert.equal(scroll.doc,false,'no page scroll');await ctx.close();
    });
  }
  await check('reduced motion: lit routes stay lit with packets frozen',async()=>{
    const {ctx,page}=await open({reducedMotion:true});await page.waitForSelector('[data-new=global_free]');await click(page,'[data-new=global_free]');await page.waitForTimeout(600);
    await places(page,'world');const v=(await S(page)).network;assert.ok(v.lit.length>=1);assert.equal(v.packetsMoving,false);await ctx.close();
  });
  await check('WebGL resources and heap stay flat across 10 cycles of every space',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=global_free]');await click(page,'[data-new=global_free]');await page.waitForTimeout(600);
    for(let i=0;i<10;i++){for(const r of ['world','campus','noc','hall'])await places(page,r);const s=await S(page);report.resources.push({cycle:i+1,geometries:s.renderer.geometries,textures:s.renderer.textures,heapMiB:s.heap?+(s.heap.used/1048576).toFixed(1):null});}
    const geo=report.resources.map(r=>r.geometries),tex=report.resources.map(r=>r.textures);
    assert.ok(Math.max(...geo.slice(1))-Math.min(...geo.slice(1))<=2,`geometries ${geo}`);assert.ok(Math.max(...tex.slice(1))-Math.min(...tex.slice(1))<=2,`textures ${tex}`);
    await perf(page,'after 10 cycles (hall)');await places(page,'world');await perf(page,'world with lit cities');await ctx.close();
  });
}finally{
  report.finishedAt=new Date().toISOString();report.pass=report.checks.filter(c=>c.pass).length;report.fail=report.checks.filter(c=>!c.pass).length;
  await writeFile(resolve(out,report.seeded||only?'phase6-qa-dev.json':'phase6-qa.json'),JSON.stringify(report,null,2));
  console.log(`\n${report.pass} PASS / ${report.fail} FAIL · page errors ${report.errors.length} · console errors ${report.consoleErrors.length}`);
  await browser?.close();await stack?.stop();
}
